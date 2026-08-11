# MicroPython Projects

A collection of MicroPython projects for ESP32-based boards and the Raspberry Pi Pico. Development is primarily done through the [MicroPico](https://marketplace.visualstudio.com/items?itemName=paulober.pico-w-go) VS Code extension (see `.vscode/extensions.json`), which is why each project folder contains a `.micropico` marker file.

## Boards

| Folder | Board | MCU | Notes |
|---|---|---|---|
| [M5StickS3/](M5StickS3/) | M5Stack StickS3 | ESP32-S3 | Primary development target for this repo |
| [Atom/](Atom/) | M5Stack AtomS3 | ESP32-S3 | Plain generic MicroPython, no vendor library -- see notes below |
| [M5StickCPlusSE/](M5StickCPlusSE/) | M5Stack StickC PlusSE | ESP32 (PICO-D4) | Small `m5/` library + a button-driven example menu -- see notes below |
| [wand/](wand/) | Seeed XIAO ESP32-C6 | ESP32-C6 | NFC/BLE/ESP-NOW wand firmware (see `main.py` docstring) |
| [ws_screen/](ws_screen/) | AMOLED touchscreen boards (Waveshare / LILYGO), see `config/` | ESP32-S3 | Screen driver + game controller code |
| [Pico_Test/](Pico_Test/) | Raspberry Pi Pico | RP2040 | Simple test/scratch project |

## Firmware

The M5StickS3 (and other ESP32-S3 boards in this repo) was flashed with the generic ESP32-S3 MicroPython build:
[https://micropython.org/download/ESP32_GENERIC_S3/](https://micropython.org/download/ESP32_GENERIC_S3/)

The StickS3 has octal SPIRAM, so grab the **Octal-SPIRAM** `.bin` variant from that page (not the plain/quad-SPIRAM build). Erase the flash first, then write the `.bin` with `esptool`:

```sh
esptool.py --chip esp32s3 erase_flash
esptool.py --chip esp32s3 write_flash 0 ESP32_GENERIC_S3-SPIRAM_OCT-<date>-v<version>.bin
```

The AtomS3 has no PSRAM, so it takes the plain (non-SPIRAM) `.bin` from the same page instead:

```sh
esptool.py --chip esp32s3 erase_flash
esptool.py --chip esp32s3 write_flash 0 ESP32_GENERIC_S3-<date>-v<version>.bin
```

The StickC PlusSE uses the classic ESP32 (not S3) generic build, since it's an ESP32-PICO-D4:
[https://micropython.org/download/ESP32_GENERIC/](https://micropython.org/download/ESP32_GENERIC/)

```sh
esptool.py --chip esp32 erase_flash
esptool.py --chip esp32 write_flash -z 0x1000 ESP32_GENERIC-<date>-v<version>.bin
```

The Pico project uses the standard Raspberry Pi Pico MicroPython firmware from [micropython.org/download](https://micropython.org/download/).

## M5StickS3 library & examples

`M5StickS3/m5/` is a small hardware library covering the board's LCD, PMIC
(power/battery/charging), buttons, onboard IMU, Grove port (including the RFID2
tag reader), speaker, and IR.
See **[M5StickS3/docs/](M5StickS3/docs/)** for a short usage doc per module,
and **[M5StickS3/m5/CLAUDE.md](M5StickS3/m5/CLAUDE.md)** for the deeper
hardware-archaeology notes (register maps, what was tried and failed, sources)
behind it.

Example scripts at the `M5StickS3/` project root, built on that library:

| Script | What it shows |
|---|---|
| `hello_world.py`, `blink.py` | Bare-minimum LCD/GPIO starting points |
| `IMU.py` | All onboard IMU outputs (accel/gyro/temp); BtnA pauses/resumes |
| `battery_status.py` | Battery mV/%, power source, BtnA toggles charging |
| `tilt_tone.py` | Tilt (Y-axis) controls a played tone's pitch |
| `Grove_accelerometer.py`, `potentiometer.py`, `rgb_env.py` | External Grove device examples |
| `rfid_reader.py` | Reads 13.56MHz RFID tag UIDs with the Grove RFID2 unit |
| `rcx_ir.py` | Talks to a LEGO Mindstorms RCX brick over IR |
| `power_functions.py` | Drives LEGO Power Functions motors/lights over IR |
| `universal_remote.py` | Sends/receives NEC and Sony SIRC, sends Philips RC5 |
| `Wand_driving.py` | Tap a LEGO connection card, drive that card's bricks over BLE (below) |

## Driving LEGO Education bricks from the StickS3

[`M5StickS3/Wand_driving.py`](M5StickS3/Wand_driving.py) turns the Stick into a
LEGO connection-card wand. Tap any card on the RFID2 Unit and it listens for
the bricks advertising under that card, connects to them, and wires them
together — a Controller drives a Double Motor one joystick per wheel, a Color
Sensor drives a motor from its reflected-light reading, and the mixed pairs
work too. The card's color is only its address, not a choice of behavior. It
waits for the bricks rather than giving up, naming what is still missing; BtnA
stops, and another card switches over.

It is a short file — the tap-and-drive loop and nothing else. Everything under
it lives in [`M5StickS3/m5/m5_wand.py`](M5StickS3/m5/m5_wand.py): the card
decode, the screen, and a BLE central whose `Controller`, `ColorSensor`,
`SingleMotor` and `DoubleMotor` classes are usable on their own, connecting by
card color and serial — which is how the bricks identify themselves in their
advertisements. See [docs/m5_wand.md](M5StickS3/docs/m5_wand.md).

These bricks also talk to each other *connectionlessly*, by broadcasting under
the same FD02 UUID with no pairing at all. That is a different protocol —
reverse-engineered in the sibling `SimpleLE` repo under `card_mode/` — and
`m5_wand` deliberately does not implement it: it carries seven speed steps per
stick and neither joystick angle nor reflected light.

## AtomS3

Unlike the StickS3, `Atom/` is plain stock MicroPython with no vendor
hardware library -- scripts talk to the chip's pins directly. Confirmed by
testing on real hardware:

| Peripheral | Pin(s) | Notes |
|---|---|---|
| RGB LED (single SK6812/WS2812) | G35 | Drive with the stock `neopixel` module |
| Front button | G41 (`MTDI`), active-low | Needs `Pin.PULL_UP`; there's only one code-readable button |
| Reset button | n/a | Wired straight to the chip's `EN` line, not a GPIO -- can't be read in code |
| Grove I2C port | SCL=G1, SDA=G2 | Confirmed by I2C scan; note this is the *opposite* of the yellow/white = SDA/SCL guess the Grove connector convention would suggest |
| IR emitter | G4 | Not yet used by any example script |
| LCD (0.85", 128x128) | SPI, see schematic | Not yet used by any example script -- no driver written for it here |

No PMIC on this board (unlike the StickS3's M5PM1) -- the Grove port's 5V
pin is wired straight to the raw USB 5V input, so there's no power-on step
needed before using a Grove device.

Example scripts at the `Atom/` project root:

| Script | What it shows |
|---|---|
| `button_led.py` | Press the front button to step the RGB LED through colors |
| `color_sensor.py` | Reads a Grove Color Sensor V3.0 (VEML6040 RGBW sensor) over I2C -- raw R/G/B/W counts plus a lux estimate |

## StickC PlusSE

`M5StickCPlusSE/m5/` is a small hardware library (AXP192 power/battery,
ST7789 LCD, BM8563 RTC) -- pure stock MicroPython, no vendor firmware.
The SE variant of the StickC Plus has **no onboard IMU** (removed for
cost -- confirmed by a revision note printed right on M5Stack's own
schematic) and swaps the microphone in as a new addition; everything
else matches the older StickC Plus. Confirmed by testing on real
hardware:

| Peripheral | Pin(s) / addr | Notes |
|---|---|---|
| Button A (front) | G37, active-low | Input-only pin on classic ESP32 -- no internal pull-up, relies on the board's own external pull-up resistor |
| Button B (side) | G39, active-low | Same input-only caveat as Button A |
| Power key | AXP192 I2C, reg `0x46` | A third physical button with **no GPIO at all** -- read via the PMU's press-status register, not `machine.Pin`. Holding it can reset/power-cycle the board through the AXP192, so treat long-holds carefully when testing |
| AXP192 PMU | I2C addr `0x34`, `scl=G22, sda=G21` | Gates the LCD's power (LDO2=backlight, LDO3=logic) and reads battery/VBUS voltage + charge/discharge current |
| BM8563 RTC | I2C addr `0x51`, same bus as AXP192 | PCF8563-register-compatible; keeps time across runs on its own -- don't reset it every script, just read it |
| LCD (ST7789v2, 135x240) | SPI: `sck=G13, mosi=G15`; `dc=G23, cs=G5, rst=G18` | Same panel/GRAM offset (52,40 into a 240x320 GRAM) as the StickS3's screen |
| Buzzer (passive) | G2 | Drive with `machine.PWM`, any audible frequency |
| Status LED (red) | G10 | Plain GPIO output |
| IR emitter | G9, 38kHz carrier | Raw pulse transmit only, via `esp32.RMT` -- no IR receiver on this board to confirm reception |
| Grove I2C port | `scl=G33, sda=G32` | Confirmed by I2C scan |
| Microphone (SPM1423) | G0=CLK, G34=DATA | **Not usable from stock MicroPython** -- it's a PDM mic (clock + data, no word-select line) and `machine.I2S` only exposes standard I2S, which needs a WS pin this mic doesn't have |

Example scripts at the `M5StickCPlusSE/` project root all share one
interface -- `NAME` (a string) and `run(display, should_stop)`, where
`should_stop()` returns `True` once it's time to stop:

| Script | What it shows |
|---|---|
| `ex_buttons.py` | Live A/B/power-key state |
| `ex_battery.py` | Battery + VBUS voltage, charge/discharge current |
| `ex_buzzer.py` | Sweeps the buzzer through an audible pitch range |
| `ex_rtc.py` | Displays the RTC's stored date/time, ticking |
| `ex_status_led.py` | Blinks the red status LED |
| `ex_ir.py` | Fires a raw NEC-shaped IR pulse train once a second |
| `ex_grove.py` | Scans the Grove I2C port and lists what answers |

[`main.py`](M5StickCPlusSE/main.py) ties them into a menu: Button B
steps through the list, Button A starts the selected example and stops
whatever's currently running.

## Getting started

1. Install the [MicroPico](https://marketplace.visualstudio.com/items?itemName=paulober.pico-w-go) VS Code extension.
2. Flash the appropriate firmware above onto your board.
3. Open the relevant project folder and use MicroPico to upload files to the device.
4. Create any missing secrets files listed below before running code that depends on them — they are intentionally excluded from git (see `.gitignore`) and must be created locally.

## Missing secrets files

These files are `.gitignore`d because they hold Wi-Fi credentials / BLE bonding keys, so they won't exist after a fresh clone. Create them locally in the exact paths and formats below.

### `ws_screen/utilities/secrets.py`

Required by [`ws_screen/utilities/wifi.py`](ws_screen/utilities/wifi.py) to connect to Wi-Fi. Create the file with:

```python
SSID = "your-wifi-ssid"
PASS = "your-wifi-password"
```

### `wand/ble_secrets.json`

Used by the `aioble` BLE stack (`wand/lib/aioble/`) to store BLE bonding keys. Unlike the file above, you don't need to hand-write this one — it's created/updated automatically by `aioble` the first time the wand successfully pairs and bonds with a peer device. If it's missing, just re-pair; it will be regenerated in this format:

```json
[[10, "<base64 device id>", "<base64 bonding key>"]]
```

## Advanced: powering the LCD and Grove port on the StickS3

Both the StickS3's built-in LCD and its Grove connector's 5V pin are gated through the **M5PM1** power-management IC (I2C address `0x6E` on I2C bus 1, `scl=Pin(48)`, `sda=Pin(47)`) — not through the ESP32 directly. See [`M5StickS3/m5/m5_power.py`](M5StickS3/m5/m5_power.py).

M5Stack's public M5PM1 driver ([github.com/m5stack/M5PM1](https://github.com/m5stack/M5PM1)) documents the battery-ADC registers (used in [`m5_battery.py`](M5StickS3/m5/m5_battery.py)), but it doesn't spell out the registers that gate the LCD and Grove 5V rails — those were found by reading through M5Stack's open-source UIFlow MicroPython firmware ([github.com/m5stack/uiflow-micropython](https://github.com/m5stack/uiflow-micropython)), which implements StickS3's multi-level power-switch design on top of the same M5PM1, and pulling out the specific GPIO2/BOOST_EN register writes it uses.

**LCD power-on** — the LCD block is fed by an M5PM1 GPIO ("GPIO2" / "L3B") that has to be explicitly configured as a push-pull output and driven high before the ST7789 will respond to anything:

```python
gpio2_bit = 1 << 2
set_bit(0x16, gpio2_bit, False)  # gpio2 -> plain GPIO function (not alt function)
set_bit(0x10, gpio2_bit, True)   # gpio2 -> output mode
set_bit(0x13, gpio2_bit, False)  # gpio2 -> push-pull drive (not open-drain)
set_bit(0x11, gpio2_bit, True)   # gpio2 -> output high
```

**Grove 5V power-on** — the Grove connector's 5V pin is fed by a boost converter that's disabled by default. Setting the `BOOST_EN` bit (bit 3) in the power-config register (`0x06`) enables it:

```python
pwr_cfg_reg = 0x06
boost_en_bit = 1 << 3
set_bit(pwr_cfg_reg, boost_en_bit, True)
```

`BOOST_EN` auto-clears on every reset and USB re-download, so `power_on_grove_5v()` needs to run again on every boot — any script that talks to a Grove device (`m5_RGB.py`, `m5_EnvSensor.py`, `m5_accel.py`, `m5_potentiometer.py`, `m5_rfid.py`) calls it on init, so you don't need to call it yourself if you're using those helpers.
