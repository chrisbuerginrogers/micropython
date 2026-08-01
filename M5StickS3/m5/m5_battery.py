"""Battery voltage/charge readout via the M5PM1 power-management IC.

Register ported from M5Stack's official driver (github.com/m5stack/M5PM1,
M5PM1_REG_VBAT_L/H): a 12-bit ADC reading in millivolts, packed low byte
first. Confirmed live on M5StickS3 hardware (read back ~4076mV on a
charged battery).

The percentage is only a rough linear estimate of a single-cell LiPo's
usable range, not a true fuel-gauge curve - good enough for an
at-a-glance readout, not for precise capacity tracking.
"""

from m5 import m5_power

_VBAT_L_REG = 0x22

_FULL_MV = 4200
_EMPTY_MV = 3300


class Battery:
    def read_mv(self):
        data = m5_power.read_reg(_VBAT_L_REG, 2)
        return data[0] | (data[1] << 8)

    def read_percent(self):
        mv = self.read_mv()
        pct = (mv - _EMPTY_MV) * 100 // (_FULL_MV - _EMPTY_MV)
        if pct < 0:
            return 0
        if pct > 100:
            return 100
        return pct
