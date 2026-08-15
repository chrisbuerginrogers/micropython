'''
DriveFromController.py — tap a card on the Stick to pick the motors, then
drive them from ANY Controller heard on the air, whatever card that
Controller carries -- or none at all.

  >>> Runs ON the M5StickS3, not the Mac. <<<
  Needs on the Stick: m5/ (2026-08 or later), picolib.py, lego_card.py,
  stick_ui.py -- from the sibling SimpleLE repo's card_mode/pico tests/.
  Install once from the Mac:
      import pico_lelib; pico_lelib.install()

Stock LEGO card mode only lets a Controller drive a motor tapped with its
OWN card. This decouples the two: tap any card on the Stick's reader once
-- and tap that same card on every Double Motor that should obey it, the
usual LEGO pairing step -- and from then on this listens for stick
positions from whichever Controller is on the air, regardless of ITS card,
and re-broadcasts them as the TAPPED card. So the paired motors obey a
Controller that was never tapped with their card, or never tapped with
any card at all.

This replaces an earlier version of this file that ran on the Mac and
related an already-known Controller's card to a matching Motor over USB to
the Stick -- that version could only drive motors sharing the Controller's
own card. Reading a card tap needs the Stick's own RFID reader, which the
Mac has no way to ask for over the existing pico_lelib/pico_server
protocol, so this now runs entirely on the Stick, the same way
manyControllers.py does, and does not need the Mac at all once started.

As in manyControllers.py, there is one radio, so this alternates: a scan
window listening for a Controller, then a burst driving the tapped card.
It has not been run against real hardware -- treat the first run as a
test, the way you would any new radio code.

Ctrl-C (through the raw REPL, e.g. via mac_run_on_stick.py) stops cleanly.
'''

import time

import bluetooth
# These four live on the M5StickS3 (lego_card.py/picolib.py/stick_ui.py come
# from the sibling SimpleLE repo's card_mode/pico tests/, m5 from this repo's
# own M5StickS3/m5/) -- Pylance has no stub path to them from this Mac-side
# workspace, but they are present at runtime on the board.
import lego_card  # type: ignore[reportMissingImports]
import picolib  # type: ignore[reportMissingImports]
import stick_ui  # type: ignore[reportMissingImports]
from m5.m5_rfid import RFID, ReadError  # type: ignore[reportMissingImports]

SCAN_MS = 300             # how long each scan window listens for a controller
BURST_MS = 250            # how long each burst keeps the motors' beacon fresh
STALE_MS = 1000           # stop the motors if no controller heard this long

_IRQ_SCAN_RESULT = 5
_IRQ_SCAN_DONE = 6

DEVICE_TYPE_CONTROLLER = picolib.DEVICE_TYPE_CONTROLLER


def _find_fd02(adv_data):
    '''The 12-byte FD02 service-data payload inside a raw advertisement, or
    None. Same decode as manyControllers.py -- see there for the byte
    layout, which mirrors picolib.build_beacon()'s framing in reverse.'''
    i = 0
    n = len(adv_data)
    while i < n:
        length = adv_data[i]
        if length == 0 or i + 1 + length > n:
            return None
        ad_type = adv_data[i + 1]
        if ad_type == 0x16 and length >= 3 and \
                adv_data[i + 2] == 0x02 and adv_data[i + 3] == 0xFD:
            return bytes(adv_data[i + 4:i + 1 + length])
        i += 1 + length
    return None


def _signed_nibble(b):
    '''Decode one stick byte exactly as a motor does. Matches
    cardlib._signed_nibble on the Mac side of the same protocol.'''
    nibble = b & 0x0F
    return nibble - 16 if nibble >= 8 else nibble


def read_any_controller(ble, duration_ms=SCAN_MS):
    '''(left_step, right_step) from the first Controller heard, whatever its
    card, or None if none was heard. Deliberately not filtered by color or
    serial -- that is the whole point of this file.'''
    reading = None
    done = False

    def irq(event, data):
        nonlocal reading, done
        if event == _IRQ_SCAN_RESULT:
            if reading is not None:
                return
            _addr_type, _addr, _adv_type, _rssi, adv_data = data
            svc = _find_fd02(adv_data)
            if svc is None or len(svc) < 8 or svc[0] != DEVICE_TYPE_CONTROLLER:
                return
            reading = (_signed_nibble(svc[6]), _signed_nibble(svc[5]))
        elif event == _IRQ_SCAN_DONE:
            done = True

    ble.irq(irq)
    ble.gap_scan(duration_ms, 30000, 30000)
    deadline = time.ticks_add(time.ticks_ms(), duration_ms + 300)
    while not done and time.ticks_diff(deadline, time.ticks_ms()) > 0:
        time.sleep_ms(10)
    try:
        ble.gap_scan(None)   # in case it somehow did not stop on its own
    except OSError:
        pass
    return reading


def wait_for_tap(ui, rfid):
    '''(app_color, serial, b2, b7) for the first LEGO card tapped.'''
    ui.looking('TAP A CARD', 'pick the motors')
    print('tap the card the motors are wearing')
    while True:
        try:
            found = lego_card.read_card(rfid)
        except ReadError as e:
            print('read failed ({}), will retry'.format(e))
            rfid.halt()
            time.sleep_ms(150)
            continue
        except lego_card.NotALegoCard as e:
            ui.problem('NOT A CARD', str(e)[:20])
            rfid.halt()
            time.sleep_ms(1000)
            continue
        if found is None:
            time.sleep_ms(150)
            continue
        uid, (app_color, serial) = found
        b2, b7 = lego_card.card_hash(uid)
        return app_color, serial, b2, b7


def main():
    ui = stick_ui.UI()
    rfid = RFID()
    app_color, serial, b2, b7 = wait_for_tap(ui, rfid)

    card = picolib.Card(color=app_color, serial=serial, b2=b2, b7=b7)
    name = stick_ui.color_name(app_color)
    ui.card(app_color, serial)
    ui.status('any controller drives')
    print('{} #{} chosen -- tap this same card on every motor to drive, '
         'then steer with any Controller (any card, or none)'
         .format(name, serial))

    motor = picolib.Motor(card)
    ble = bluetooth.BLE()   # the one radio; Motor already switched it on

    sent = (0, 0)
    last_heard_ms = time.ticks_ms()
    stale_warned = False

    try:
        while True:
            ble.gap_advertise(None)  # type: ignore[reportArgumentType]
            sticks = read_any_controller(ble)
            now_ms = time.ticks_ms()

            if sticks is not None:
                last_heard_ms = now_ms
                stale_warned = False
                left_pct = picolib.SPEED_STEPS[sticks[0] + 3]
                right_pct = picolib.SPEED_STEPS[sticks[1] + 3]
            elif time.ticks_diff(now_ms, last_heard_ms) > STALE_MS:
                left_pct, right_pct = 0, 0
                if not stale_warned:
                    print('no controller heard -- stopping until one is back')
                    stale_warned = True
            else:
                left_pct, right_pct = sent   # a single missed window; keep going

            if (left_pct, right_pct) != sent:
                print('L {:+4d}%  R {:+4d}%'.format(left_pct, right_pct))
            sent = (left_pct, right_pct)

            motor.set_tank(left_pct, right_pct)
            ui.status('L{:+4d} R{:+4d}'.format(left_pct, right_pct))
            motor.drive(BURST_MS / 1000.0)
    finally:
        motor.close()
        ui.status('stopped')
        ui.close()
        print('stopped')


main()
