"""AXP192 power-management IC (I2C addr 0x34) on the StickC PlusSE.

Unlike the StickS3's M5PM1 (which needed reverse-engineering from
M5Stack's firmware source), the AXP192 is a documented, widely-used
chip. This register map and the init() sequence are ported from
Sebastian Wicki's MIT-licensed micropython-m5stickc-plus
(github.com/gandro/micropython-m5stickc-plus, lib/axp192.py), itself
matching M5Stack's own Arduino AXP192 init for this board family.
Confirmed live: 0x34 answers on this board's internal I2C bus.

This same chip also gates the LCD's power (LDO2=backlight, LDO3=logic)
and carries the power key (a third physical button with no GPIO of its
own -- see power_button()) and the battery/RTC-backup charging.
"""

from machine import Pin, I2C

_ADDR = 0x34
_i2c = None


def internal_i2c():
    """The shared internal I2C bus (AXP192 PMU + BM8563 RTC both live here)."""
    global _i2c
    if _i2c is None:
        _i2c = I2C(0, scl=Pin(22), sda=Pin(21), freq=100000)
    return _i2c


def read_reg(reg, n=1):
    return internal_i2c().readfrom_mem(_ADDR, reg, n)


def write_reg(reg, value):
    internal_i2c().writeto_mem(_ADDR, reg, bytes([value & 0xFF]))


def set_bit(reg, bit, value):
    current = read_reg(reg)[0]
    write_reg(reg, (current | bit) if value else (current & ~bit))


def init():
    """Power on the LCD rails (LDO2/LDO3) and enable the battery/VBUS ADCs.

    Needed before Display() will show anything, and before
    read_battery_mv()/read_battery_ma() return live (non-stale) values.
    Safe to call every boot -- these settings aren't known to auto-clear,
    but every M5Stack init path re-asserts them anyway.
    """
    write_reg(0x28, 0xCC)  # LDO2 (backlight) and LDO3 (LCD logic) -> 3.0V
    set_bit(0x10, 1 << 2, True)  # EXTEN on
    set_bit(0x12, (1 << 3) | (1 << 2) | (1 << 0), True)  # LDO3, LDO2, DCDC1 on
    write_reg(0x84, 0b11000010)  # ADC sample 200Hz, TS pin 80uA, temp mon
    write_reg(0x82, 0xFF)  # ADC enable: battery, ACIN, VBUS, APS, TS
    write_reg(0x30, 0b01100010)  # VBUS hold 4.4V, limit 500mA
    write_reg(0x31, 0b0100)  # power off at 3.0V battery
    write_reg(0x33, 0b11000000)  # charge: enable, 4.2V, 10% threshold, 100mA
    write_reg(0x36, 0b00001100)  # PEK: 128ms short, 1.5s long -> power off, 4s off-time


def read_battery_mv():
    hi = read_reg(0x78)[0]
    lo = read_reg(0x79)[0]
    return ((hi << 4) | lo) * 1.1  # 1.1mV per LSB


def read_battery_charge_ma():
    hi = read_reg(0x7A)[0]
    lo = read_reg(0x7B)[0]
    return ((hi << 5) | lo) * 0.5  # 0.5mA per LSB


def read_battery_discharge_ma():
    hi = read_reg(0x7C)[0]
    lo = read_reg(0x7D)[0]
    return ((hi << 5) | lo) * 0.5  # 0.5mA per LSB


def read_vbus_mv():
    hi = read_reg(0x5A)[0]
    lo = read_reg(0x5B)[0]
    return ((hi << 4) | lo) * 1.7  # 1.7mV per LSB


_PEK_IRQ_STATUS_REG = 0x46
_PEK_SHORT_PRESS_BIT = 1 << 1
_PEK_LONG_PRESS_BIT = 1 << 0


def power_button():
    """Check + clear the power key's press flags. Returns (short, long) --
    the physical power button has no GPIO of its own, so this I2C
    register is the only way to read it.
    """
    status = read_reg(_PEK_IRQ_STATUS_REG)[0]
    short = bool(status & _PEK_SHORT_PRESS_BIT)
    long_ = bool(status & _PEK_LONG_PRESS_BIT)
    if short or long_:
        write_reg(_PEK_IRQ_STATUS_REG, _PEK_SHORT_PRESS_BIT | _PEK_LONG_PRESS_BIT)
    return short, long_


def power_off():
    set_bit(0x32, 1 << 7, True)
