"""Barometric pressure/temperature sensor (Bosch BMP280) on the Grove port.

Register map and compensation formula ported from M5Stack's official
driver (github.com/m5stack/M5Unit-ENV, src/BMP280.cpp) - itself the
standard Bosch/Adafruit BMP280 algorithm. The compensation constants are
factory-trimmed per chip, so they're read from the device, not hardcoded.

Confirmed live on M5StickS3 hardware: this chip (id 0x58) answers at
0x76 on the Grove I2C bus (G9=SDA, G10=SCL); no separate humidity chip
is present on this particular ENV unit.
"""

from machine import I2C, Pin
from m5 import m5_power

GROVE_SDA_PIN = 9
GROVE_SCL_PIN = 10


def _cdiv(n, d):
    # C-style truncate-toward-zero integer division (Python's // floors)
    q = n // d
    if (n % d != 0) and ((n < 0) != (d < 0)):
        q += 1
    return q


class BMP280:
    ADDR = 0x76
    _CONTROL_REG = 0xF4
    _CONFIG_REG = 0xF5
    _PRESSURE_REG = 0xF7
    _TEMP_REG = 0xFA

    def __init__(self, i2c=None, addr=ADDR):
        m5_power.power_on_grove_5v()
        self.i2c = i2c or I2C(0, scl=Pin(GROVE_SCL_PIN), sda=Pin(GROVE_SDA_PIN), freq=400000)
        self.addr = addr
        self.t_fine = 0
        self._read_calibration()
        self._write8(self._CONFIG_REG, 0x00)  # standby 1ms, filter off
        # normal mode, 16x oversampling on both temperature and pressure
        self._write8(self._CONTROL_REG, (5 << 5) | (5 << 2) | 0x03)

    def _write8(self, reg, val):
        self.i2c.writeto_mem(self.addr, reg, bytes([val & 0xFF]))

    def _read_u16_le(self, reg):
        data = self.i2c.readfrom_mem(self.addr, reg, 2)
        return (data[1] << 8) | data[0]

    def _read_s16_le(self, reg):
        v = self._read_u16_le(reg)
        return v - 0x10000 if v & 0x8000 else v

    def _read24(self, reg):
        data = self.i2c.readfrom_mem(self.addr, reg, 3)
        return (data[0] << 16) | (data[1] << 8) | data[2]

    def _read_calibration(self):
        self.dig_T1 = self._read_u16_le(0x88)
        self.dig_T2 = self._read_s16_le(0x8A)
        self.dig_T3 = self._read_s16_le(0x8C)
        self.dig_P1 = self._read_u16_le(0x8E)
        self.dig_P2 = self._read_s16_le(0x90)
        self.dig_P3 = self._read_s16_le(0x92)
        self.dig_P4 = self._read_s16_le(0x94)
        self.dig_P5 = self._read_s16_le(0x96)
        self.dig_P6 = self._read_s16_le(0x98)
        self.dig_P7 = self._read_s16_le(0x9A)
        self.dig_P8 = self._read_s16_le(0x9C)
        self.dig_P9 = self._read_s16_le(0x9E)

    def read(self):
        """Returns (temp_c, pressure_pa)."""
        adc_t = self._read24(self._TEMP_REG) >> 4
        var1 = (((adc_t >> 3) - (self.dig_T1 << 1)) * self.dig_T2) >> 11
        var2 = ((((adc_t >> 4) - self.dig_T1) * ((adc_t >> 4) - self.dig_T1)) >> 12) * self.dig_T3 >> 14
        self.t_fine = var1 + var2
        temp_c = ((self.t_fine * 5 + 128) >> 8) / 100.0

        adc_p = self._read24(self._PRESSURE_REG) >> 4
        var1 = self.t_fine - 128000
        var2 = var1 * var1 * self.dig_P6
        var2 = var2 + ((var1 * self.dig_P5) << 17)
        var2 = var2 + (self.dig_P4 << 35)
        var1 = ((var1 * var1 * self.dig_P3) >> 8) + ((var1 * self.dig_P2) << 12)
        var1 = (((1 << 47) + var1) * self.dig_P1) >> 33
        if var1 == 0:
            return temp_c, 0.0
        p = 1048576 - adc_p
        p = _cdiv(((p << 31) - var2) * 3125, var1)
        var1 = (self.dig_P9 * (p >> 13) * (p >> 13)) >> 25
        var2 = (self.dig_P8 * p) >> 19
        p = ((p + var1 + var2) >> 8) + (self.dig_P7 << 4)
        pressure_pa = p / 256.0
        return temp_c, pressure_pa

    @staticmethod
    def altitude(pressure_pa, sea_level_hpa=1013.25):
        pressure_hpa = pressure_pa / 100.0
        return 44330 * (1.0 - pow(pressure_hpa / sea_level_hpa, 0.1903))
