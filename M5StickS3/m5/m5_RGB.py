"""SK6812 RGB LED strip on the Grove port's data line (G9)."""

from machine import Pin
import neopixel
from m5 import m5_power

GROVE_SDA_PIN = 9


class Sk6812:
    def __init__(self, num_leds, pin=GROVE_SDA_PIN):
        m5_power.power_on_grove_5v()
        self.pin = pin
        self.num_leds = num_leds

    def fill(self, color):
        # Re-created on every call: if G9 is also being used as Grove I2C
        # SDA elsewhere in the script (e.g. m5_bmp280), the NeoPixel driver
        # can't hold that pin open between writes - see rgb_env.py.
        strip = neopixel.NeoPixel(Pin(self.pin), self.num_leds)
        for i in range(self.num_leds):
            strip[i] = color
        strip.write()
