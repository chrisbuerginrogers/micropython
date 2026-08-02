# m5_potentiometer

Analog potentiometer on the Grove port's wiper pin (G10).

```python
from m5.m5_potentiometer import Potentiometer

pot = Potentiometer()
raw = pot.read_raw()        # 0-65535
percent = pot.read_percent()  # 0-100
volts = pot.read_volts()      # 0.0-3.3
```

**Only works plugged directly into the StickS3's own Grove connector** — not
through a passive I2C hub. The hub's SDA/SCL pull-up resistors swamp the pot's
analog voltage-divider signal on G10, so readings pin to one extreme instead
of tracking the knob (confirmed on real hardware — see `rgb_env.py`'s notes).
With only one physical Grove port on this board, it's this module or an I2C
hub's worth of devices, not both at once.
