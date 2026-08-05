# m5_wand

The library behind [`Wand_driving.py`](../Wand_driving.py) — everything needed
to tap a LEGO Education connection card and drive the bricks carrying it: the
card decode, a BLE central for the bricks' GATT protocol, the screen, and the
pieces a driving loop is built from.

**Run `Wand_driving.py`**, at the project root. This module does nothing on its
own.

The card's **color is only its address** — it does not pick a behavior. Tap any
card and the Stick listens for whatever is advertising under it, then wires the
first sender to the first motor it hears:

| Sender | Motor | What it does |
|---|---|---|
| Controller | Double Motor | one joystick per wheel |
| Controller | Single Motor | the left stick drives it |
| Color Sensor | Double Motor | reflected light drives both wheels |
| Color Sensor | Single Motor | reflected light drives it |

If a card carries more than one of a kind, `SENDERS` and `ACTUATORS` set the
preference order — Controller over Color Sensor, Double over Single.

It waits indefinitely, naming what is still missing (`NO SENDER` / `NO MOTOR`)
so switching a brick on after the tap is all it takes. BtnA stops; tapping a
different card switches straight over.

> Earlier versions keyed behavior off the card color, with purple driving and
> green following the light. Tapping any other color printed *"no bricks are
> wired to ORANGE"* — a statement about the lookup table that read as a claim
> about the room, while the orange bricks sat there blinking. Asking the air
> cannot be wrong in that way.

`Wand_driving.py` is the loop that does all of the above, and it is short on
purpose — `run_card()` and `main()` are the whole program, so it is the file to
copy and change when you want different behavior. The parts it leans on are
here: `wait_for_card()`, `find_pair()`, `connect_brick()`, `Watcher`,
`sender_speeds()`, `apply_speeds()`, `readout()`, `shut_down()` and `UI`.

## The BLE half, on its own

Four classes speak the bricks' FD02 GATT protocol. They are the reusable part
of the file.

```python
from m5.m5_wand import Controller, DoubleMotor, PURPLE

ctrl  = Controller();  ctrl.connect(PURPLE, 6055)
drive = DoubleMotor(); drive.connect(PURPLE, 6055)
while True:
    ctrl.update()                    # nothing else refreshes the readings
    drive.tank(ctrl.left_percent, ctrl.right_percent)
```

| Class | Product | Reads | Commands |
|---|---|---|---|
| `Controller` | 515 | `left_percent`, `right_percent` (−100..100), `left_angle`, `right_angle` | — |
| `ColorSensor` | 514 | `color` (App code), `reflection` (0–255), `red`/`green`/`blue`, `hue`, `saturation`, `value` | — |
| `SingleMotor` | 512 | `speed`, `position`, `power` | `set_speed(-100..100)`, `run()`, `stop()` |
| `DoubleMotor` | 513 | same | `tank(left, right)`, `set_speed(left, right)`, `run()`, `stop()` |

All four also carry `battery`, `usb`, `button`, `card_color`, `card_serial`, and
share:

- `connect(color, serial, timeout_ms=None, update_ms=100, on_wait=None)` —
  waits indefinitely by default; `on_wait()` is called every ~20 ms so you can
  animate or bail out by raising.
- `update()` — unpacks everything reported since the last call. **Call it every
  loop**; readings do not refresh on their own.
- `set_update_rate(delay_ms)` — 0 = off, otherwise 15–1000.
- `connected`, `disconnect()`, and module-level `close_radio()`.

`central().discover(color, serial, ready=..., on_wait=...)` is the other half:
instead of stopping at the first match it returns a bit mask of *which product
types* are advertising under a card, which is how a tap works out what it has
to work with. `product_bit(product)` reads the mask.

`SingleMotor.set_speed()` is the whole interface for a "keep turning" loop:
setting a speed on a stopped motor does nothing visible, so the first call also
sends the run command, and a speed of 0 stops rather than idling at zero.
`DoubleMotor.tank()` sets both wheels in one command so they change together
instead of one lurching a packet ahead of the other.

## Addressing by card, not by name

A brick tapped with a connection card advertises that card in LEGO
manufacturer data (company ID `0x0397`):

```
[product_group, product_device, card_color, serial_lo, serial_hi]
```

so `connect(color, serial)` is a scan filter. **Match on both.** Serials are
allocated per color, so RED #1126 and PURPLE #1126 are different cards and a
filter on serial alone silently collides.

## Two color numbering schemes

The card and the wire carry *firmware* color codes; everything above
`firmware_to_app()` uses *App* codes (`PURPLE = 6`, matching the `legoeducation`
package and `lelib`). Firmware 2 is purple and App 2 is yellow, so skipping the
conversion yields plausible-looking wrong answers rather than an error.

## Reading the card

```python
from m5.m5_rfid import RFID
from m5.m5_wand import read_card, decode_pages, NotALegoCard

uid, color, serial = read_card(RFID())
```

The cards are NTAG/Ultralight (SAK `0x00`) and carry the color and serial in the
clear from page 4 — `4C334730 00<color><serial hi><lo>`, where `L3G0` is the
magic marker. `decode_pages()` is pure and testable off-hardware.
`NotALegoCard` means the tag answered and was not one of these; `ReadError`
from the driver means the read did not complete and is worth retrying.

The serial is **big-endian on the card and little-endian in the
advertisement**. `decode_pages()` hands back an integer so callers never see
it, but don't copy raw bytes from one to the other.

## Things that will bite

- **A brick the LEGO app is connected to will not be found.** Connected devices
  stop advertising, and discovery only sees what is on the air — so a brick you
  can see blinking in the app never turns up here. Disconnect it there first.
  This is the most likely reason a card sits on `NO SENDER` / `NO MOTOR`.
- **One connection slot per brick.** The reverse also holds: while this runs the
  Stick holds the slot, so the LEGO app cannot see the brick. And if a real
  controller is driving that motor over the broadcast protocol, both are
  commanding it and the last packet wins.
- **The MTU is raised to 128 and exchanged.** At the default 23 a motor's
  notification (two motors + battery + button + card) overruns the 20-byte
  payload and the tail is dropped by the radio — which looks like a brick that
  stopped reporting, not a truncated packet.
- **This is not the broadcast protocol.** These bricks also drive each other
  connectionlessly under the same FD02 UUID (reverse-engineered in the sibling
  `SimpleLE` repo under `card_mode/`). That path carries seven speed steps per
  stick and neither joystick angle nor reflection, so none of the above is
  reachable through it. Non-connectable advertisements are filtered out during
  the scan for exactly that reason.
- **The speaker is optional.** Constructing a `Speaker` has been seen to raise
  `ENODEV` on this board's codec, so `UI` catches it and runs without beeps
  rather than refusing to start.
- **Subscribing is the fragile step.** Notifications need the notify
  characteristic's CCCD, and descriptor discovery has been seen live to return
  it for neither of two reasons: a brick reporting a service end handle that
  stops at the notify value (so the CCCD falls outside any range derived from
  it), and an IRQ tuple shape that does not match the unpack — which fails
  *inside* the callback, printing only `Unhandled exception in IRQ callback
  handler` and leaving discovery looking empty. Both are handled: the search
  covers the whole service, the handler indexes rather than unpacks, and if
  nothing turns up it falls back to `notify_value + 1` with a printed notice.
  The subscribe write is then checked, so a wrong guess says
  `handle N refused the subscribe (ATT error ...)` instead of surfacing two
  steps later as a brick that never answers.

## When something connects but does nothing

Set `m5_wand.VERBOSE = True` near the top of `Wand_driving.py`. It prints the
discovered service range and the tx/rx handles at connect time, plus unknown
packet types and dropped writes while running.
