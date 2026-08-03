# M5Stack StickS3 — hardware notes

This folder is a MicroPython hardware library for the M5Stack StickS3
(ESP32-S3-PICO-1-N8R8, 8MB flash, 8MB **octal** PSRAM). Everything here
was reverse-engineered/ported by reading M5Stack's own open-source
firmware source (not guessed), and cross-checked live against this
repo's actual StickS3 unit wherever noted "confirmed live."

Firmware: flash the **Octal-SPIRAM** build from
https://micropython.org/download/ESP32_GENERIC_S3/ (not the plain/quad
build — this board needs the octal variant). See the repo root
README's Firmware section for the exact `esptool.py` erase/write
commands.

## Primary sources (all verified against, not recalled from memory)

- `github.com/m5stack/uiflow-micropython` — board_init.c, the ES8311
  driver, the BMI270 driver, the IR hardware wrapper and pin map, the
  StickS3 board manifest/mpconfigboard files.
- `github.com/m5stack/M5Unified` — `Power_Class.cpp`,
  `M5PM1_Class.cpp/.hpp`, `M5Unified.cpp` (per-board pin tables and
  `case board_t::board_M5StickS3:` blocks), `Button_Class.cpp`.
- `github.com/m5stack/M5PM1` — standalone PMIC register-map reference.
- `github.com/BrickBot/nqc` — `rcxlib/RCX_PipeTransport.cpp`, the real
  RCX IR transport implementation (not a written protocol description).
- `docs.m5stack.com` — StickS3 core/spec pages, per-peripheral pages.

## M5PM1 power-management IC (m5_power.py)

I2C address `0x6E`, on the **internal** I2C bus: `I2C(1, scl=Pin(48),
sda=Pin(47))`. This same bus also carries the onboard IMU (`0x68`) and
the audio codec (`0x18`) — `m5_power.internal_i2c()` returns the shared
bus object for all three.

Register map actually used here:

| Reg | Name | Notes |
|---|---|---|
| `0x04` | `PWR_SRC` | Read-only. **Bitmask, not an exclusive enum** despite M5Stack's own register comment implying 0/1/2 — confirmed live: reading `5` (`USB\|BATTERY`) with both bits set at once. bit0=USB/5VIN present, bit1=5VINOUT present, bit2=battery present. |
| `0x06` | `PWR_CFG` | bit0=`CHG_EN` (charging), bit1=`DCDC_EN`, bit2=`LDO_EN` (3.3V LDO), bit3=`BOOST_EN` (Grove 5V / 5VINOUT / "ext output" — all the same physical rail). **Auto-clears on every reset/download** — must be re-asserted every boot. |
| `0x10` | `GPIO_MODE` | direction (input/output), one bit per PMIC GPIO0-3 |
| `0x11` | `GPIO_OUT` | output value, one bit per PMIC GPIO0-3 |
| `0x12` | `GPIO_IN` | input read, one bit per PMIC GPIO0-3 (unused here so far) |
| `0x13` | `GPIO_DRV` | drive type (push-pull vs open-drain), one bit per PMIC GPIO0-3 |
| `0x16` | `GPIO_FUNC0` | function select (plain GPIO vs alt function), one bit per PMIC GPIO0-3 |

PMIC **GPIO2** gates the LCD block; PMIC **GPIO3** gates the AW8737
speaker amp. Both need the same 4-register function/mode/drive/output
dance (see `power_on_lcd()` / `power_on_speaker()` / `power_off_speaker()`).

`isCharging()` has **no real hardware signal** on this chip — M5Stack's
own official driver's `isCharging()` is a hardcoded `return false`
stub. `get_power_source()`'s presence bitmask is the closest available
proxy.

## LCD (m5_display.py)

ST7789, 135×240, offset (52,40) within the panel's actual 240×320 GRAM.
SPI1: `sck=40, mosi=39`; `dc=45, cs=41, rst=21`; backlight=`Pin(38)`.
Needs `m5_power.power_on_lcd()` first (PMIC GPIO2) — the LCD has no
power without it. This panel needs `INVON` for correct colors.

## Battery (m5_battery.py)

M5PM1 `VBAT_L`/`VBAT_H` (`0x22`/`0x23`), 12-bit ADC in mV, register
map ported from M5Stack's official M5PM1 driver. Confirmed live
(~4076mV on a charged cell). Percentage is a rough linear estimate,
not a fuel-gauge curve.

## Grove port

I2C: `scl=Pin(10), sda=Pin(9)` (different bus from the internal one
above). 5V power needs `m5_power.power_on_grove_5v()` — `PWR_CFG`
bit3/`BOOST_EN`. Same bit *number* as the speaker amp's "GPIO3" above,
but a completely different register (`0x06` vs `0x16/0x10/0x13/0x11`)
controlling a different rail — don't confuse the two. Devices already
wired up against this bus: BMP280 env sensor (`0x76`), SK6812
RGB LED (data on G9), MMA7660FC Grove accelerometer (`0x4C`,
`Grove_accelerometer.py`/`m5_accel.py`), potentiometer (wiper on G10,
analog — **can't share the bus with an I2C hub**, the hub's pull-ups
swamp the pot's analog signal; see `rgb_env.py`'s notes).

## RFID2 Unit — WS1850S (m5_rfid.py)

Grove I2C address `0x28`. The WS1850S is an MFRC522 work-alike: same
register map, same command set, reached over I2C instead of the
MFRC522's usual SPI. Ported from M5Stack's own driver
(`uiflow-micropython`, `m5stack/libs/driver/mfrc522/` + `libs/unit/rfid.py`),
itself a port of the Arduino MFRC522 library.

`VersionReg` (`0x37`) reads **`0x15`** — not one of the MFRC522's
documented `0x90`/`0x91`/`0x92` values, so the upstream
`pcd_perform_self_test()` firmware-checksum comparison can never pass on
this chip. It isn't ported here; `version()` is only good as an "is the
unit answering" check.

**Confirmed live**: a 7-byte-UID Ultralight/NTAG tag read as
`04F686A2CC2190`, SAK `0x00`, through the two-cascade-level select path.
Cross-checked independently — pages 0-3 of that tag read back
`04F686 FC A2CC2190`, i.e. UID[0:3], BCC0, UID[3:7], which is exactly
the UID `select()` assembled. MIFARE Classic block reads are ported but
**never tested against a Classic tag** (none available); only the
Ultralight path is hardware-verified.

Three upstream bugs found and fixed in this port:

- `pcd_read_bytes()`'s RxAlign merge is written
  `(data[0] & ~mask) | (data[0] & mask)`, which is just `data[0]` — a
  no-op that drops the already-known UID bits. Only matters
  mid-anticollision, i.e. with two or more tags in the field, which is
  presumably why it survived. Fixed by merging against the destination
  buffer the way the Arduino original does, which meant giving
  `_communicate()` a caller-supplied receive buffer instead of a freshly
  allocated one.
- Timeout loops subtract raw `ticks_us()` values rather than using
  `ticks_diff()`, so they read negative across the counter's ~17.9
  minute wrap. Benign in practice (the hardware TimerIRq still fires)
  but wrong; uses `ticks_diff()` here.
- The UID length is never tracked — `read_card_uid()` hands back all 10
  bytes regardless, so a 4-byte UID comes out padded with leftovers from
  the previous read. Tracked as `uid_size` here (3 × cascade level + 1).

Also unfixed-but-avoided: their `UID` class holds `uid`/`sak` as *class*
attributes, so every instance shares one bytearray; `__len__` returns a
`self.size` that's never assigned; `__str__` prints instead of
returning; and `RFIDUnit.wakeup_all()` passes an empty buffer into a
function that rejects anything not exactly 2 bytes, so it can only ever
return False. None of these are reachable in this port's API.

Writing blocks, the UID-changeable-card backdoor and the sector-dump
pretty-printer were deliberately left out — the ask was reading.

## Onboard IMU — BMI270 (m5_imu.py)

6-axis (accel+gyro, no magnetometer — StickS3 doesn't carry a BMM150).
I2C address `0x68`, on the **internal** bus. Needs Bosch's mandatory
~8KB `CONFIG_DATA` init blob uploaded before it'll produce data (ported
verbatim from the upstream driver — not hand-editable).

**Bug found and fixed here**: the upstream M5Stack driver
unconditionally calls `aux_senser_init()` (magnetometer-aux setup) at
the end of `BMI270.__init__`, even for the BMI270-only case. On this
board that call clobbers `PWR_CONF`/`PWR_CTRL` right after
`accel_gyro_odr()` sets them up, and `STATUS_REG` never sets
`DRDY_ACC`/`DRDY_GYR` afterward — `accel()`/`gyro()` silently read
`(0, 0, 0)` forever, no exception. Fix: don't call it. Confirmed live:
`accel()` now reads ~1g on Z at rest as expected.

This is the *internal* IMU — a different chip from the external Grove
MMA7660FC in `m5_accel.py`/`Grove_accelerometer.py`.

## Buttons (m5_buttons.py)

BtnA = `GPIO11` (the large front button), BtnB = `GPIO12`. Both
active-low with internal pull-up (`Pin.PULL_UP`), raw state read as
`not pin.value()`. Debounced `Button`/`Buttons` classes.

## Audio — ES8311 codec + AW8737 amp (m5_audio.py)

I2S: `BCLK=17, WS=15, DOUT=14, DIN=16` (mic in, unused so far). I2C
control: internal bus, codec address `0x18` (chip ID registers
`0xFD=0x83, 0xFE=0x11` — the documented ES8311 identity). Amp enable
is PMIC GPIO3 (`power_on_speaker()`/`power_off_speaker()`).

MicroPython's `machine.I2S` can't drive a separate MCLK pin (unlike the
ESP-IDF driver M5Stack's own firmware uses), so the codec has to derive
its master clock from BCLK instead. The exact "MCLK=BCLK" register
sequence (`0x01=0xB5, 0x02=0x18, ...`) is ported from
`M5Unified.cpp:_speaker_enabled_cb_sticks3()` — StickS3's own
proven-working way to do this. Sample rate is fixed at 16000Hz stereo
to match that exact bring-up; general M5Unified docs default to
44100Hz, but that's for their MCLK-pin-based setup, not this one.

**Confirmed live: a 440Hz tone played and was actually heard.** But
also observed live: the codec's I2C connection has been **flaky** —
across extensive earlier testing in one session, `Speaker()` reliably
raised `OSError: [Errno 19] ENODEV` (nothing acknowledged at `0x18` no
matter what power/clock condition was tried), then after several
unrelated power cycles/USB reconnects it started working perfectly.
Likely a marginal physical connection, not a code bug — but treat
`ENODEV` from `Speaker()` as an expected possible failure, not a
regression. Catch it (see `tilt_tone.py`) rather than assume it'll
always construct cleanly.

**Cross-peripheral gotcha**: M5Stack's docs state the speaker amp must
be off for the IR receiver to work reliably (switching noise). Call
`m5_power.power_off_speaker()` before using `IRReceiver` if audio was
used earlier in the same script.

## IR (m5_ir.py, rcx_ir.py)

TX pin `GPIO46`, RX pin `GPIO42`, 38kHz carrier. This is a *raw
pulse-train* transmitter/receiver, not a NEC decoder. MicroPython's
stock `esp32.RMT` only supports transmit, not capture, so
`IRReceiver` bit-bangs pulse timing off the RX pin instead.

`rcx_ir.py` talks to a **LEGO Mindstorms RCX** brick: 2400 baud, 8
data bits, odd parity, 1 stop bit, UART-over-IR. Framing (`0x55 0xFF
0x00` header, each data byte followed by its bitwise complement,
trailing checksum + its complement) and opcodes are ported from NQC's
real RCX transport source, not reconstructed from a description — high
confidence there. What's **not** independently verified: which carrier
state (on vs off) represents which UART bit — this repo assumes the
standard on-off-keying convention every consumer IR link uses, flagged
via `SPACE_IS_CARRIER_ON` at the top of the file if it needs flipping.
**Never tested against a real RCX brick** (none available) — only
verified that construction and the RMT transmit path run without
crashing.

`power_functions.py` talks **LEGO Power Functions** — the protocol
that replaced RCX's IR link from 2007 onward (Technic/train motors and
lights). Simpler than RCX: pulse-distance encoded nibbles (156us mark,
260/546/1014us spaces), no UART framing. Ported from a verified
working Arduino library (`TheJarOS/LegoPowerFunctions-Arduino-Library`).
Implements `SingleOutput` (single-motor PWM speed, with LEGO's
auto-toggle-per-command bit) and `ComboPWM` (both outputs of a channel
at once); `SinglePin`/`ComboMode` aren't implemented. LRC checksum
invariant and live transmission verified on hardware; **never tested
against a real PF receiver** (none available).

`universal_remote.py` implements the non-LEGO "big three" consumer IR
protocols — **NEC**, **Sony SIRC** (12-bit only), and **Philips RC5**
— ported from Peter Hinch's `micropython_ir` reference library. NEC
and Sony carry both encode *and* decode, self-verified via round-trip
against known (address, data) pairs (host-side pure Python and
on-device). RC5's biphase/Manchester encoder is a line-for-line port
of the reference's `append()`/`add()` array-mutation approach (some
bits need merging into the previous pulse segment rather than starting
a new one) — cross-checked against an independent simulation of that
same algorithm across several inputs, but **send-only, no decoder**
(Manchester decode is more failure-prone to get right without real
hardware to test against, so it was deliberately left out rather than
guessed at). Sony needs a 40kHz carrier and RC5 needs 36kHz — both
differ from NEC/PF's 38kHz, so `IRTransmitter(carrier_hz=...)` gets
overridden per-protocol. All three confirmed to transmit without error
on hardware; none tested against a real receiving device.

## Dev workflow gotchas (not hardware, but will burn time)

- VS Code's MicroPico extension (`micropico.openOnStart` in this
  workspace's `.vscode/settings.json`) auto-connects to the board's
  serial port whenever a StickS3 file is open/focused. That's
  exclusive access — `mpremote` (or anything else) can't talk to the
  board until that connection is dropped. Symptom: `could not enter
  raw repl`. Check `lsof /dev/tty.usbmodem*` for a `Code Helper`
  process holding it.
- The board uses **native USB CDC**, not a separate UART-USB bridge
  chip. A firmware hang can wedge the USB stack until a physical reset
  (button press or unplug/replug) — host-side retries won't fix it.
