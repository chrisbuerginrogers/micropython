"""Tap a LEGO connection card - its color decides what happens
  >>> Runs ON the M5StickS3. Needs m5/ and the Grove RFID2 Unit. <<<

PURPLE   double motor + controller     one joystick per wheel
GREEN    single motor + color sensor   reflected light drives it

Tap a card and the stick waits for that color's two bricks to turn up,
then runs them. BtnA stops; tapping another card switches straight to
it. Everything the bricks understand is in `m5/m5_wand.py`; see
`docs/m5_wand.md`.
"""

import time

from m5.m5_buttons import Buttons
from m5.m5_rfid import RFID
import m5.m5_wand as Wand


# The two big readout lines, remembered so they are only repainted when
# they change: redrawing two scale-2 lines every time round the loop is
# enough SPI traffic to make the sticks feel laggy.
_shown = [None]                     # type: list[tuple | None]


def show(ui, line0, line1):
    """Put the two live-readout lines up, if they have changed."""
    if (line0, line1) != _shown[0]:
        ui.big(0, line0)
        ui.big(1, line1)
        _shown[0] = (line0, line1)

def stick(percent):
    """A centred joystick still reads a few percent; call that zero."""
    if -Wand.STICK_DEADZONE < percent < Wand.STICK_DEADZONE:
        return 0
    return percent

def wait_for(ui, watcher, color, serial, *classes):
    """Connect to each kind of brick in turn, waiting for each to show up.
    Waits indefinitely, so switching a brick on after the tap is all it
    takes. BtnA and another card both arrive here as Cancelled.
    """
    bricks = []
    try:
        for slot, cls in enumerate(classes):
            bricks.append(
                Wand.connect_brick(ui, cls, slot, color, serial, watcher))
    except BaseException:
        Wand.shut_down(bricks)
        raise
    return bricks

def keep_going(ui, watcher, *bricks):
    """Refresh every brick, and say whether the drive loop runs again.
    """
    if watcher.should_stop():
        return False
    for brick in bricks:
        brick.update()
        if not brick.connected:
            ui.problem('BRICK LOST', 'check the power')
            print('a brick disconnected')
            time.sleep_ms(1500)
            return False
    return True

def purple_card(ui, watcher, color, serial):
    """PURPLE: the controller's two sticks drive the two wheels."""
    print('waiting for a DOUBLE MOTOR and a CONTROLLER')
    motor, ctrl = wait_for(ui, watcher, color, serial,
                           Wand.DoubleMotor, Wand.Controller)
    print('got the double motor and the controller -- BtnA stops')
    ui.go()
    try:
        while keep_going(ui, watcher, motor, ctrl):
            left = stick(ctrl.left_percent)
            right = stick(ctrl.right_percent)
            motor.tank(left, right)
            show(ui, 'L {:>4}'.format(left), 'R {:>4}'.format(right))
            time.sleep_ms(50)
    finally:
        Wand.shut_down((motor, ctrl))

def green_card(ui, watcher, color, serial):
    """GREEN: reflected light drives the motor -- brighter is faster."""
    print('waiting for a SINGLE MOTOR and a COLOR SENSOR')
    motor, sensor = wait_for(ui, watcher, color, serial,
                             Wand.SingleMotor, Wand.ColorSensor)
    print('got the single motor and the color sensor -- BtnA stops')
    ui.go()
    try:
        while keep_going(ui, watcher, motor, sensor):
            # Reflection is 0..255 and set_speed() wants -100..100, so
            # this conversion is not optional.
            speed = Wand.light_to_speed(sensor.reflection)
            motor.set_speed(speed)
            show(ui, 'LIT{:>4}'.format(sensor.reflection),
                 'SPD{:>4}'.format(speed))
            time.sleep_ms(50)
    finally:
        Wand.shut_down((motor, sensor))

def other_card(ui, watcher, color):
    """A color with no rule. Say so about the rule, not about the room.
    """
    ui.problem('NO RULE FOR', Wand.color_name(color))
    print('no rule for {} -- try purple or green'
          .format(Wand.color_name(color)))
    while not watcher.should_stop():
        time.sleep_ms(50)

def run_card(ui, buttons, rfid, color, serial):
    """What to do when tapped  """
    watcher = Wand.Watcher(buttons, rfid, (color, serial))
    ui.card(color, serial)
    ui.hint('BtnA stops')
    _shown[0] = None                # ui.card() just repainted over them

    try:
        if color == Wand.PURPLE:
            purple_card(ui, watcher, color, serial)
        elif color == Wand.GREEN:
            green_card(ui, watcher, color, serial)
        else:
            other_card(ui, watcher, color)
    except Wand.Cancelled:
        pass
    return watcher.next_card

def main():
    """Tap cards and run whichever bricks answer to them."""
    ui = Wand.UI()
    ui.looking('STARTING', '')
    buttons = Buttons()
    try:
        rfid = RFID()
    except OSError as exc:
        # The Grove 5V boost has already been given six tries -the reader being absent or unplugged
        ui.problem('NO READER', 'check the grove')
        print('RFID2 unit did not answer: {}'.format(exc))
        ui.close()
        raise

    card = None
    try:
        while True:
            if card is None:
                card = Wand.wait_for_card(ui, rfid)
            color, serial = card
            print()
            print('got {} #{}'.format(Wand.color_name(color), serial))
            card = run_card(ui, buttons, rfid, color, serial)
    except KeyboardInterrupt:
        print('stopped')
    finally:
        Wand.close_radio()
        ui.close()

if __name__ == '__main__':
    main()
