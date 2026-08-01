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
