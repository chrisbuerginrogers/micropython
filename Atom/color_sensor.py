"""AtomS3 + Grove Color Sensor V3.0 (VEML6040 RGBW sensor) on the Grove port.

GPIO1 = SCL, GPIO2 = SDA (confirmed by I2C scan -- opposite of the yellow/
white = SDA/SCL Grove convention you'd guess from the schematic alone).
The Grove port's 5V is wired straight to the board's raw USB input with
no PMIC gate, so there's no power-on step needed here (unlike the
StickS3's Grove port -- see M5StickS3/m5/m5_power.py).
"""

from machine import I2C, Pin
from time import sleep_ms

ADDR = 0x10
CONF_REG = 0x00
R_DATA, G_DATA, B_DATA, W_DATA = 0x08, 0x09, 0x0A, 0x0B

IT_40MS, IT_80MS, IT_160MS, IT_320MS, IT_640MS, IT_1280MS = 0x00, 0x10, 0x20, 0x30, 0x40, 0x50

# Lux-per-count at 1x gain, keyed by integration time -- halves as the
# integration time doubles (Vishay "Designing the VEML6040 RGBW Color
# Sensor Into an Application" app note).
GREEN_SENSITIVITY = {
    IT_40MS: 0.25168,
    IT_80MS: 0.12584,
    IT_160MS: 0.06292,
    IT_320MS: 0.03146,
    IT_640MS: 0.01573,
    IT_1280MS: 0.007865,
}


class VEML6040:
    def __init__(self, i2c, integration_time=IT_160MS):
        self.i2c = i2c
        self.it = integration_time
        self.i2c.writeto_mem(ADDR, CONF_REG, bytes([integration_time, 0x00]))
        sleep_ms(200)  # let the first conversion at this integration time finish

    def _read16(self, reg):
        return int.from_bytes(self.i2c.readfrom_mem(ADDR, reg, 2), 'little')

    def read(self):
        """Return (red, green, blue, white, lux) -- raw 16-bit counts + lux."""
        r = self._read16(R_DATA)
        g = self._read16(G_DATA)
        b = self._read16(B_DATA)
        w = self._read16(W_DATA)
        lux = g * GREEN_SENSITIVITY[self.it]
        return r, g, b, w, lux


i2c = I2C(0, scl=Pin(1), sda=Pin(2), freq=100000)
sensor = VEML6040(i2c)

while True:
    r, g, b, w, lux = sensor.read()
    print('R={:5d} G={:5d} B={:5d} W={:5d}  {:6.1f} lux'.format(r, g, b, w, lux))
    sleep_ms(200)
