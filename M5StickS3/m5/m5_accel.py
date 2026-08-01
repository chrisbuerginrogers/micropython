"""3-axis +/-1.5g accelerometer (Seeed Grove MMA7660FC) on the Grove I2C bus.

Register map and conversion ported from Seeed's official driver
(github.com/mcauser/Grove-3Axis-Digital-Accelerometer-1.5g-MMA7660FC,
MMA7660.cpp/.h). Confirmed live on M5StickS3 hardware: this chip answers
at I2C address 0x4C on the Grove bus (G9=SDA, G10=SCL).

Each axis register packs a signed 6-bit acceleration count (bits 0-5)
plus an "alert" bit (bit 6) that's set while the register is mid-update;
reads while that bit is set are discarded and retried, same as the
original driver's retry loop.
"""

from machine import I2C, Pin
from m5 import m5_power

GROVE_SDA_PIN = 9
GROVE_SCL_PIN = 10


class MMA7660:
    ADDR = 0x4C

    _X_REG = 0x00
    _Y_REG = 0x01
    _Z_REG = 0x02
    _MODE_REG = 0x07
    _SR_REG = 0x08

    _STANDBY = 0x00
    _ACTIVE = 0x01
    _SR_120HZ = 0x00

    _ALERT_BIT = 1 << 6
    _SIGN_BIT = 1 << 5

    _COUNTS_PER_G = 21.0

    def __init__(self, i2c=None, addr=ADDR):
        m5_power.power_on_grove_5v()
        self.i2c = i2c or I2C(0, scl=Pin(GROVE_SCL_PIN), sda=Pin(GROVE_SDA_PIN), freq=100000)
        self.addr = addr
        self._write(self._MODE_REG, self._STANDBY)
        self._write(self._SR_REG, self._SR_120HZ)
        self._write(self._MODE_REG, self._ACTIVE)

    def _write(self, reg, val):
        self.i2c.writeto_mem(self.addr, reg, bytes([val]))

    def _read_axis(self, reg):
        for _ in range(10):
            raw = self.i2c.readfrom_mem(self.addr, reg, 1)[0]
            if not (raw & self._ALERT_BIT):
                break
        else:
            raise OSError("MMA7660 axis read stuck in alert state")
        value = raw & 0x3F
        if value & self._SIGN_BIT:
            value -= 0x40
        return value

    def read_raw(self):
        """Returns signed 6-bit counts (x, y, z), roughly -32..31."""
        return (self._read_axis(self._X_REG),
                self._read_axis(self._Y_REG),
                self._read_axis(self._Z_REG))

    def read_g(self):
        """Returns acceleration (x, y, z) in g, roughly -1.5..1.5."""
        x, y, z = self.read_raw()
        return x / self._COUNTS_PER_G, y / self._COUNTS_PER_G, z / self._COUNTS_PER_G
