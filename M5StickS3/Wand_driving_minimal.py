"""Tap one card, drive until you pull the plug - the stripped-down version
  >>> Runs ON the M5StickS3. Needs m5/ and the Grove RFID2 Unit. <<<

PURPLE   double motor + controller     one joystick per wheel
GREEN    single motor + color sensor   reflected light drives it

Reads one card, runs one behavior, and keeps going until the Stick is
switched off or Ctrl-C stops it. No BtnA, no swapping cards mid-run, no
error handling, no reconnecting -- see `Wand_driving.py` for the version
that does all of that, and `docs/Wand_driving.md` for its flow chart.
"""

import time

from m5.m5_rfid import RFID
import m5.m5_wand as Wand

def purple(ctrl):
    """PURPLE: turn the controller's two sticks into tank-drive speeds."""
    ctrl.update()
    left = int(ctrl.left_percent / 10) * 10
    right = int(ctrl.right_percent / 10) * 10
    return left, right

def green(sensor):
    """GREEN: turn reflected light into a motor speed -- brighter is faster."""
    sensor.update()
    speed = 2 * sensor.reflection - 100
    return sensor.reflection, speed

def connectUp(color, serial):
    """Connect the bricks for this color and return a step() that drives
    them one tick and returns the display text -- or None for no rule.
    """
    if color == Wand.PURPLE:
        print('waiting for a DOUBLE MOTOR and a CONTROLLER')
        motor = Wand.DoubleMotor()
        motor.connect(color, serial)
        ctrl = Wand.Controller()
        ctrl.connect(color, serial)
        bricks = (motor, ctrl)

        def step():
            left, right = purple(ctrl)
            motor.tank(left, right)
            return '{:>4}{:>4}'.format(left, right)
    elif color == Wand.GREEN:
        print('waiting for a SINGLE MOTOR and a COLOR SENSOR')
        motor = Wand.SingleMotor()
        motor.connect(color, serial)
        sensor = Wand.ColorSensor()
        sensor.connect(color, serial)
        bricks = (motor, sensor)

        def step():
            lit, speed = green(sensor)
            motor.set_speed(speed)
            return '{:>4}{:>4}'.format(lit, speed)
    else:
        return None

    step.bricks = bricks
    return step

def main():
    """Read one card and run whatever its color means."""
    ui = Wand.UI()
    try:
        ui.looking()
        rfid = RFID()
        print('tap a card')
        card = None
        while card is None:
            card = Wand.read_card(rfid)
            time.sleep_ms(150)
        _uid, color, serial = card
        print('got {} #{}'.format(Wand.color_name(color), serial))
        ui.card(color, serial)

        step = connectUp(color, serial)
        if step is None:
            ui.problem('NO RULE FOR', Wand.color_name(color))
            print('no rule for {} -- try purple or green'
                  .format(Wand.color_name(color)))
            return

        print('driving -- Ctrl-C stops')
        ui.go()
        try:
            while True:
                message = step()
                ui.big(0, message)
                time.sleep_ms(50)
        finally:
            Wand.shut_down(step.bricks)
    except KeyboardInterrupt:
        print('stopped')
    finally:
        Wand.close_radio()
        ui.close()

if __name__ == '__main__':
    main()
