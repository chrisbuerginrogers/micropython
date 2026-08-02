# m5_battery

Battery voltage/percentage via the M5PM1's ADC.

```python
from m5.m5_battery import Battery

battery = Battery()
print(battery.read_mv())        # e.g. 4076
print(battery.read_percent())   # 0-100
```

`read_percent()` is a straight linear map between 3300mV (0%) and 4200mV
(100%) — a rough single-cell LiPo estimate for an at-a-glance readout, not a
true fuel-gauge curve.

For charge control (turning charging on/off) and figuring out what's
currently supplying power, see [m5_power.md](m5_power.md) —
`set_charge_enable()` and `get_power_source()` live there since they're PMIC
config, not battery readout.
