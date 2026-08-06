# M5StickS3 library docs

Short reference for each module in [`../m5/`](../m5/). These cover *how to use*
each module; for the hardware-archaeology behind them (register maps, what was
tried and failed, confirmed-live status per peripheral) see
[`../m5/CLAUDE.md`](../m5/CLAUDE.md).

Every module that touches the Grove port or an internal rail calls the
relevant `m5_power` power-on function itself, so you don't need to call those
manually — just construct the class you need.

| Module | What it drives |
|---|---|
| [m5_power.md](m5_power.md) | M5PM1 PMIC — LCD/Grove/speaker power rails, battery charging, power source |
| [m5_display.md](m5_display.md) | Built-in ST7789 LCD |
| [m5_battery.md](m5_battery.md) | Battery voltage / percentage |
| [m5_buttons.md](m5_buttons.md) | BtnA / BtnB |
| [m5_imu.md](m5_imu.md) | Onboard BMI270 6-axis accel/gyro |
| [m5_audio.md](m5_audio.md) | ES8311 codec + AW8737 speaker amp |
| [m5_ir.md](m5_ir.md) | Raw IR transmit/receive (built-in IR LED/receiver) |
| [m5_accel.md](m5_accel.md) | Grove MMA7660FC accelerometer (external unit) |
| [m5_EnvSensor.md](m5_EnvSensor.md) | Grove BMP280 pressure/temperature |
| [m5_RGB.md](m5_RGB.md) | Grove SK6812 RGB LED strip |
| [m5_potentiometer.md](m5_potentiometer.md) | Grove analog potentiometer |
| [m5_rfid.md](m5_rfid.md) | Grove RFID2 Unit (WS1850S) 13.56MHz tag reader |
| [m5_wand.md](m5_wand.md) | LEGO Education bricks over BLE, addressed by connection card |

Higher-level, device-specific code built on top of `m5_ir` lives at the
`M5StickS3/` project root, not in `m5/`: [`rcx_ir.py`](../rcx_ir.py) (LEGO
RCX), [`power_functions.py`](../power_functions.py) (LEGO Power Functions),
and [`universal_remote.py`](../universal_remote.py) (NEC/Sony/RC5). Likewise
[`Wand_driving.py`](../Wand_driving.py), the tap-a-card-and-drive program built
on [m5_wand.md](m5_wand.md) — see [Wand_driving.md](Wand_driving.md) for its
flow chart.
