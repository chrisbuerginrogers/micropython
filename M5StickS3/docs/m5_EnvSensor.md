# m5_EnvSensor

Grove BMP280 barometric pressure/temperature sensor (I2C `0x76` on the Grove
bus).

```python
from m5.m5_EnvSensor import BMP280

bmp280 = BMP280()
temp_c, pressure_pa = bmp280.read()
altitude_m = BMP280.altitude(pressure_pa)  # optionally pass sea_level_hpa
```

Compensation constants are factory-trimmed per chip and read from the device
at construction time, not hardcoded — the algorithm itself is the standard
Bosch/Adafruit BMP280 formula.

**Grove-hub sharing gotcha**: if you're also using [m5_RGB.md](m5_RGB.md)'s
`Sk6812` through a passive Grove hub, both devices share the G9 signal wire
(I2C SDA here, NeoPixel data there) — you have to re-create the I2C object
before each read to reclaim the pin (`rgb_env.py` shows the pattern). Same hub
also breaks [m5_potentiometer.md](m5_potentiometer.md) entirely — see that
page.
