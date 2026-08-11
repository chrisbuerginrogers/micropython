"""BM8563 real-time clock (I2C addr 0x51, shares the AXP192's internal bus).

The BM8563 is a PCF8563 register-compatible clone. Register map ported
from Mika Tuupola's MIT-licensed tuupola/pcf8563 (via Sebastian Wicki's
micropython-m5stickc-plus port) -- confirmed live: 0x51 answers on this
board's internal I2C bus alongside the AXP192.
"""

from m5 import m5_power

_ADDR = 0x51
_SECONDS = 0x02
_TIME_SIZE = 7
_CENTURY_BIT = 1 << 7


def _dec2bcd(dec):
    hi, lo = divmod(dec, 10)
    return (hi << 4) | lo


def _bcd2dec(bcd):
    return ((bcd >> 4) * 10) + (bcd & 0x0F)


def datetime(value=None):
    """With no argument, returns (year, month, mday, hour, minute, second,
    weekday). With a 7-tuple in that same shape, sets the clock.
    """
    i2c = m5_power.internal_i2c()

    if value is None:
        data = i2c.readfrom_mem(_ADDR, _SECONDS, _TIME_SIZE)
        second = _bcd2dec(data[0] & 0x7F)
        minute = _bcd2dec(data[1] & 0x7F)
        hour = _bcd2dec(data[2] & 0x3F)
        mday = _bcd2dec(data[3] & 0x3F)
        weekday = _bcd2dec(data[4] & 0x07)
        month = _bcd2dec(data[5] & 0x1F)
        century = 100 if (data[5] & _CENTURY_BIT) else 0
        year = _bcd2dec(data[6]) + century + 1900
        return (year, month, mday, hour, minute, second, weekday)

    year, month, mday, hour, minute, second, weekday = value
    data = bytearray(_TIME_SIZE)
    data[0] = _dec2bcd(second) & 0x7F
    data[1] = _dec2bcd(minute) & 0x7F
    data[2] = _dec2bcd(hour) & 0x3F
    data[3] = _dec2bcd(mday) & 0x3F
    data[4] = _dec2bcd(weekday) & 0x07
    data[5] = _dec2bcd(month) & 0x1F
    if year >= 2000:
        data[5] |= _CENTURY_BIT
    data[6] = _dec2bcd(year % 100)
    i2c.writeto_mem(_ADDR, _SECONDS, data)
