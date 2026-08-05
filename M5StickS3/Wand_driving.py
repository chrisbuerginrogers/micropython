"""Tap a LEGO connection card, and drive whatever answers to it.

  >>> Runs ON the M5StickS3. Needs m5/ and the Grove RFID2 Unit. <<<

Tap any card on the reader. The Stick listens for the bricks carrying
that card, connects to them, and wires them together:

    Controller   + Double Motor    one joystick per wheel
    Controller   + Single Motor    the left stick drives it
    Color Sensor + Double Motor    reflected light drives both wheels
    Color Sensor + Single Motor    reflected light drives it

The card's *color* is only its address -- it does not pick a behavior.
Purple, green, orange or any other card all work the same way: whatever
answers to that card is what runs.

The bricks have to be switched on and carrying the card. This waits for
them rather than giving up, naming what is still missing on screen; BtnA
stops, and tapping a different card switches straight over.

**A brick that something else is already connected to is not
advertising**, so it cannot be found. If a brick is blinking away and
never turns up, disconnect it from the LEGO app first -- each brick has
exactly one connection slot.

Everything this leans on -- the BLE central, the card decode, the screen
-- lives in `m5/m5_wand.py`; see `docs/m5_wand.md`. This file is just
the loop that joins them, so it is the one to copy and change when you
want a different behavior. Set `m5_wand.VERBOSE = True` below the
imports if a brick connects and then does nothing.
"""

import time

from m5.m5_buttons import Buttons
from m5.m5_rfid import RFID
from m5.m5_wand import (
    LOOP_MS, REFRESH_MS, Cancelled, UI, Watcher, apply_speeds, close_radio,
    color_name, connect_brick, find_pair, readout, sender_speeds, shut_down,
    wait_for_card,
)


def run_card(ui, buttons, rfid, color, serial):
    """Find this card's bricks, wire them together, and run until stopped.

    Returns the card that interrupted it, or None if BtnA did.
    """
    watcher = Watcher(buttons, rfid, (color, serial))
    ui.card(color, serial)
    ui.hint('BtnA stops')
    sender = None
    actuator = None
    try:
        sender_cls, actuator_cls = find_pair(ui, color, serial, watcher)
        sender = connect_brick(ui, sender_cls, 0, color, serial, watcher)
        actuator = connect_brick(ui, actuator_cls, 1, color, serial, watcher)
        ui.go()
        print('running -- BtnA or another card stops')

        sent = None
        sent_at = time.ticks_ms()
        shown = None
        while not watcher.should_stop():
            sender.update()
            actuator.update()
            if not (sender.connected and actuator.connected):
                ui.problem('BRICK LOST', 'check the power')
                print('a brick disconnected')
                time.sleep_ms(1500)
                break

            left, right = sender_speeds(sender)
            stale = time.ticks_diff(time.ticks_ms(), sent_at) > REFRESH_MS
            if (left, right) != sent or stale:
                apply_speeds(actuator, left, right)
                sent = (left, right)
                sent_at = time.ticks_ms()

            # Redrawn only on change: repainting two scale-2 lines every
            # 50 ms is enough SPI traffic to make the sticks feel laggy.
            lines = readout(sender, actuator, left, right)
            if lines != shown:
                ui.big(0, lines[0])
                ui.big(1, lines[1])
                shown = lines

            time.sleep_ms(LOOP_MS)
    except Cancelled:
        pass
    finally:
        shut_down((actuator, sender))
    return watcher.next_card


def main():
    """Tap cards and run whichever bricks answer to them."""
    ui = UI()
    ui.looking('STARTING', '')
    buttons = Buttons()
    try:
        rfid = RFID()
    except OSError as exc:
        # The Grove 5V boost has already been given six tries to come up
        # by the driver, so this is the reader being absent or unplugged,
        # not a race worth retrying here.
        ui.problem('NO READER', 'check the grove')
        print('RFID2 unit did not answer: {}'.format(exc))
        ui.close()
        raise

    card = None
    try:
        while True:
            if card is None:
                card = wait_for_card(ui, rfid)
            color, serial = card
            print()
            print('{} #{}'.format(color_name(color), serial))
            # run_card hands back the card that interrupted it, so tapping
            # a second card switches straight over without a trip through
            # wait_for_card().
            card = run_card(ui, buttons, rfid, color, serial)
    except KeyboardInterrupt:
        print('stopped')
    finally:
        close_radio()
        ui.close()


if __name__ == '__main__':
    main()
