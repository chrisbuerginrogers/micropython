# m5_power

Shared driver for the **M5PM1** power-management IC (I2C `0x6E`, internal bus
`scl=48/sda=47`). Everything else that needs power on a rail — the LCD, the
Grove port, the speaker amp — goes through this module. Most other `m5_*`
modules call these functions for you; you'd mainly use this one directly for
battery/charge control or to grab the shared internal I2C bus.

```python
from m5 import m5_power

m5_power.power_on_lcd()          # required before m5_display will work
m5_power.power_on_grove_5v()     # required before most Grove devices work
m5_power.power_on_speaker()      # AW8737 amp on — see m5_audio
m5_power.power_off_speaker()     # ...and back off, for battery life / IR-rx

m5_power.set_charge_enable(True)
print(m5_power.get_power_source())  # bitmask: USB / 5VINOUT / BATTERY present
```

- `internal_i2c()` — the shared internal `I2C` bus object (PMIC + IMU +
  audio codec all live on it).
- `set_bit(reg, bit, value)` / `read_reg(reg, n=1)` — raw register access, if
  you need a control bit this module doesn't already expose.
- `POWER_SOURCE_USB` / `POWER_SOURCE_5VINOUT` / `POWER_SOURCE_BATTERY` —
  OR-able bits returned by `get_power_source()`. It's a presence bitmask
  (which supplies have power right now), not an exclusive "which one is it
  using" selector — see the docstring for why.
- There's no real "is it charging" signal on this chip; `get_power_source()`
  is the closest available proxy.

**Gotcha**: `power_on_grove_5v()` and `set_charge_enable()` share one register
(`PWR_CFG`, different bits) that **auto-clears on every reset/download** — call
them again every boot if you need them on. `power_on_lcd()`/`power_on_speaker()`
use different registers that aren't known to auto-clear the same way.
