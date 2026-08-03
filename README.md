# MicroPython Projects

A collection of MicroPython projects for ESP32-based boards and the Raspberry Pi Pico. Development is primarily done through the [MicroPico](https://marketplace.visualstudio.com/items?itemName=paulober.pico-w-go) VS Code extension (see `.vscode/extensions.json`), which is why each project folder contains a `.micropico` marker file.

## Boards

| Folder | Board | MCU | Notes |
|---|---|---|---|
| [M5StickS3/](M5StickS3/) | M5Stack StickS3 | ESP32-S3 | Primary development target for this repo |
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
