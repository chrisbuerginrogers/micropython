"""Potentiometer on the Grove port's wiper pin (G10).

Only usable when the pot is plugged directly into the StickS3's own
Grove connector, not through a passive I2C hub - the hub's SDA/SCL
pull-up resistors swamp the pot's analog voltage-divider signal (see
rgb_env.py's notes for how this was confirmed on real hardware).
"""

from machine import Pin, ADC
from m5 import m5_power

GROVE_SCL_PIN = 10  # the pot's wiper is wired to this Grove signal pin


class Potentiometer:
    def __init__(self, pin=GROVE_SCL_PIN):
        m5_power.power_on_grove_5v()
        self.pin = pin

    def _adc(self):
        a = ADC(Pin(self.pin))
        a.atten(ADC.ATTN_11DB)  # full 0-3.3V range
        return a

    def read_raw(self):
        return self._adc().read_u16()  # 0-65535

    def read_percent(self):
        return self.read_raw() * 100 // 65535

    def read_volts(self):
        return self.read_raw() * 3.3 / 65535
