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

def purple(ui, color, serial):
    """PURPLE: the controller's two sticks drive the two wheels."""
    print('waiting for a DOUBLE MOTOR and a CONTROLLER')
    motor = Wand.DoubleMotor()
    motor.connect(color, serial)
    ctrl = Wand.Controller()
    ctrl.connect(color, serial)
    print('driving -- Ctrl-C stops')
    ui.go()
    try:
        while True:
            ctrl.update()           # refresh the readings
            left = int(ctrl.left_percent / 10) * 10
            right = int(ctrl.right_percent / 10) * 10
            motor.tank(left, right)
            ui.big(0, '{:>4}{:>4}'.format(left, right))
            time.sleep_ms(50)
    finally:
        Wand.shut_down((motor, ctrl))

def green(ui, color, serial):
    """GREEN: reflected light drives the motor -- brighter is faster."""
    print('waiting for a SINGLE MOTOR and a COLOR SENSOR')
    motor = Wand.SingleMotor()
    motor.connect(color, serial)
    sensor = Wand.ColorSensor()
    sensor.connect(color, serial)
    print('driving -- Ctrl-C stops')
    ui.go()
    try:
        while True:
            sensor.update()
            speed = 2 * sensor.reflection - 100
            motor.set_speed(speed)
            ui.big(0, '{:>4}{:>4}'.format(sensor.reflection, speed))
            time.sleep_ms(50)
    finally:
        Wand.shut_down((motor, sensor))

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

        if color == Wand.PURPLE:
            purple(ui, color, serial)
        elif color == Wand.GREEN:
            green(ui, color, serial)
        else:
            ui.problem('NO RULE FOR', Wand.color_name(color))
            print('no rule for {} -- try purple or green'
                  .format(Wand.color_name(color)))
    except KeyboardInterrupt:
        print('stopped')
    finally:
        Wand.close_radio()
        ui.close()

if __name__ == '__main__':
    main()
