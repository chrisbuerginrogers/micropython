'''
manyControllers.py — tap a card to pick a color, then every Controller of
that color (any serial) currently on the air gets averaged into one tank
speed, broadcast to every Double Motor of that color.

  >>> Runs ON the M5StickS3, not the Mac. <<<
  Needs on the Stick: m5/ (2026-08 or later), picolib.py, lego_card.py,
  stick_ui.py -- the same files stick_tap_to_drive.py needs, from the
  sibling SimpleLE repo's card_mode/pico tests/. Install once from the Mac:
      import pico_lelib; pico_lelib.install()

Tap any card once to choose a color -- its own serial only picks the color,
it is not used as a filter afterward. From then on, in a loop:

  1. scan for a moment, collecting every Controller broadcasting under that
     color, whatever its serial -- that is "all listening" made concrete:
     a classroom's worth of purple controllers all pushed at once;
  2. average their left and right stick readings;
  3. broadcast that average, one short burst per distinct serial seen, so
     any Double Motor sharing one of those cards drives from the crowd
     average instead of its own controller.

A motor only obeys a beacon carrying its own card's tokens (b2/b7). Those
are read here off the very controller broadcasts being averaged, exactly
as pico_lelib.find_card() does from the Mac -- so this only reaches motors
whose card serial matches a controller that is currently on the air. A
motor whose controller was switched off is unreachable, same as it would
be for a lone controller-and-motor pair.

picolib.py has no on-device scanner (macOS does the listening in every
other example here) -- scan_controllers() below is new, decoding the same
FD02 service-data structure picolib.build_beacon() constructs, in reverse.

There is one radio, so driving several distinct serials "at once" is
really a fast round-robin, each getting its turn rather than a literal
simultaneous broadcast. Fine for a handful of cards; with many, each one's
packets arrive less often. This has not been run against real hardware --
the byte layout matches picolib/cardlib exactly, but treat the first run
as a test, the way you would any new radio code.

Ctrl-C (through the raw REPL, e.g. via mac_run_on_stick.py) stops cleanly.
'''

import time

import bluetooth
# These four live on the M5StickS3 (lego_card.py/picolib.py/stick_ui.py come
# from the sibling SimpleLE repo's card_mode/pico tests/, m5 from this repo's
# own M5StickS3/m5/) -- Pylance has no stub path to them from this Mac-side
# workspace, but they are present at runtime on the board. See the module
# docstring above for install instructions.
import lego_card  # type: ignore[reportMissingImports]
import picolib  # type: ignore[reportMissingImports]
import stick_ui  # type: ignore[reportMissingImports]
from m5.m5_rfid import RFID, ReadError  # type: ignore[reportMissingImports]

SCAN_MS = 500             # how long each scan window listens
BURST_MS = 200            # how long each cycle spends driving, total
STEP_MS = picolib.DEFAULT_STEP_MS

_IRQ_SCAN_RESULT = 5
_IRQ_SCAN_DONE = 6

DEVICE_TYPE_CONTROLLER = picolib.DEVICE_TYPE_CONTROLLER


def _find_fd02(adv_data):
    '''The 12-byte FD02 service-data payload inside a raw advertisement, or
    None. Mirrors picolib.build_beacon()'s own framing in reverse: a
    length-prefixed AD structure, type 0x16 (service data), UUID16 0xFD02
    little-endian (bytes 0x02, 0xFD), then the 12 payload bytes.'''
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


def scan_controllers(ble, wire_color, duration_ms=SCAN_MS):
    '''{serial: {'b2', 'b7', 'left', 'right'}} for every Controller of this
    firmware color heard in one scan window. left/right are steps, -3..+3.'''
    found = {}
    done = [False]

    def irq(event, data):
        if event == _IRQ_SCAN_RESULT:
            _addr_type, _addr, _adv_type, _rssi, adv_data = data
            svc = _find_fd02(adv_data)
            if svc is None or len(svc) < 8:
                return
            if svc[0] != DEVICE_TYPE_CONTROLLER or svc[1] != wire_color:
                return
            serial = svc[3] | (svc[4] << 8)
            found[serial] = {
                'b2': svc[2], 'b7': svc[7],
                'left': _signed_nibble(svc[6]),
                'right': _signed_nibble(svc[5]),
            }
        elif event == _IRQ_SCAN_DONE:
            done[0] = True

    ble.irq(irq)
    ble.gap_scan(duration_ms, 30000, 30000)
    deadline = time.ticks_add(time.ticks_ms(), duration_ms + 300)
    while not done[0] and time.ticks_diff(deadline, time.ticks_ms()) > 0:
        time.sleep_ms(10)
    try:
        ble.gap_scan(None)   # in case it somehow did not stop on its own
    except OSError:
        pass
    return found


def average_tank(controllers):
    '''(left_percent, right_percent) averaged across every controller found,
    rounded to the seven steps a beacon can carry.'''
    lefts = [picolib.SPEED_STEPS[c['left'] + 3] for c in controllers.values()]
    rights = [picolib.SPEED_STEPS[c['right'] + 3] for c in controllers.values()]
    avg_left = sum(lefts) / len(lefts)
    avg_right = sum(rights) / len(rights)
    return picolib.round_speed(avg_left), picolib.round_speed(avg_right)


def drive_burst(ble, cards, left_pct, right_pct, counters, duration_ms=BURST_MS):
    '''Round-robin one refreshed beacon per card, spread over duration_ms.

    counters is kept by the caller and passed in on every call, so each
    card's counter keeps climbing across cycles rather than resetting --
    a beacon whose counter goes backwards is what "not fresh" looks like
    to a motor.
    '''
    if not cards:
        return
    left_byte = picolib.step_to_byte(picolib.speed_to_step(left_pct))
    right_byte = picolib.step_to_byte(picolib.speed_to_step(right_pct))
    deadline = time.ticks_add(time.ticks_ms(), duration_ms)
    i = 0
    while time.ticks_diff(deadline, time.ticks_ms()) > 0:
        card = cards[i % len(cards)]
        counters[card.serial] = (counters.get(card.serial, 0)
                                 + picolib.COUNTER_STEP) & 0xFFFFFF
        ble.gap_advertise(None)
        ble.gap_advertise(
            picolib.ADV_INTERVAL_US,
            adv_data=picolib.build_beacon(card, DEVICE_TYPE_CONTROLLER,
                                          left_byte, right_byte,
                                          counters[card.serial]),
            connectable=False)
        time.sleep_ms(STEP_MS)
        i += 1
    ble.gap_advertise(None)


def wait_for_tap(ui, rfid):
    '''(app_color, serial) of the first LEGO card tapped on the reader.'''
    ui.looking('TAP A CARD', 'pick a color')
    print('tap a card to choose a color')
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
        _uid, (app_color, serial) = found
        return app_color, serial


def main():
    ui = stick_ui.UI()
    rfid = RFID()
    app_color, tapped_serial = wait_for_tap(ui, rfid)

    wire_color = picolib._wire_color(app_color)   # same conversion Card() uses
    name = stick_ui.color_name(app_color)
    ui.card(app_color, tapped_serial)
    ui.status('LISTENING')
    print('{} chosen (tapped #{}) -- averaging every {} controller heard'
         .format(name, tapped_serial, name))

    ble = bluetooth.BLE()
    ble.active(True)
    counters = {}

    try:
        while True:
            controllers = scan_controllers(ble, wire_color)
            if not controllers:
                ui.status('no {} heard'.format(name))
                continue

            left_pct, right_pct = average_tank(controllers)
            cards = [picolib.Card(color=app_color, serial=serial,
                                  b2=c['b2'], b7=c['b7'])
                     for serial, c in controllers.items()]

            ui.status('{} avg L{:+4d} R{:+4d}'.format(
                len(cards), left_pct, right_pct))
            print('{} controllers -> L{:+4d} R{:+4d}, driving {} card(s)'
                 .format(len(controllers), left_pct, right_pct, len(cards)))

            drive_burst(ble, cards, left_pct, right_pct, counters)
    finally:
        # gap_advertise(None) stops advertising -- the stub types interval_us
        # as plain int, but its own docstring confirms None is how you stop.
        ble.gap_advertise(None)  # type: ignore[reportArgumentType]
        ble.active(False)
        ui.status('stopped')
        ui.close()
        print('stopped')


main()
