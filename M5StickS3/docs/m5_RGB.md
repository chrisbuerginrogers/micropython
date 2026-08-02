# m5_RGB

Grove SK6812 RGB LED strip, data line on G9.

```python
from m5.m5_RGB import Sk6812

led = Sk6812(num_leds=3)
led.fill((40, 0, 0))  # (r, g, b), 0-255 each
```

`fill()` re-creates the underlying `NeoPixel` driver on every call rather than
holding it open — necessary if G9 is also being used as Grove I2C SDA
elsewhere in the same script (e.g. alongside [m5_EnvSensor.md](m5_EnvSensor.md)
through a passive hub), since only one driver can own the pin at a time. See
`rgb_env.py` for the full pattern of interleaving this with an I2C device on
the same hub.
