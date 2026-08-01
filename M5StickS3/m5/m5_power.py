"""Shared helper for the M5PM1 power-management IC (I2C addr 0x6E).

StickS3 gates both the LCD block and the Grove connector's 5V pin through
this chip rather than through the ESP32 itself.
"""

from machine import Pin, I2C

_ADDR = 0x6E
_i2c = None


def _get_i2c():
    global _i2c
    if _i2c is None:
        _i2c = I2C(1, scl=Pin(48), sda=Pin(47), freq=100000)
    return _i2c


def set_bit(reg, bit, value):
    i2c = _get_i2c()
    current = i2c.readfrom_mem(_ADDR, reg, 1)[0]
    updated = (current | bit) if value else (current & ~bit)
    i2c.writeto_mem(_ADDR, reg, bytes([updated & 0xFF]))


def read_reg(reg, n=1):
    return _get_i2c().readfrom_mem(_ADDR, reg, n)


def power_on_lcd():
    """Enable the GPIO2 ("L3B") rail that feeds the ST7789 LCD block."""
    gpio2_bit = 1 << 2
    set_bit(0x16, gpio2_bit, False)  # gpio2 -> plain GPIO function
    set_bit(0x10, gpio2_bit, True)  # gpio2 -> output mode
    set_bit(0x13, gpio2_bit, False)  # gpio2 -> push-pull drive
    set_bit(0x11, gpio2_bit, True)  # gpio2 -> output high


def power_on_grove_5v():
    """Enable BOOST_EN, which feeds the Grove connector's 5V pin.

    Auto-clears on every reset/download, so this needs calling every boot.
    """
    pwr_cfg_reg = 0x06
    boost_en_bit = 1 << 3
    set_bit(pwr_cfg_reg, boost_en_bit, True)
