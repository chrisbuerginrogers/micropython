# m5_accel

External Grove accelerometer (Seeed MMA7660FC, ±1.5g, I2C `0x4C` on the Grove
bus). Not the onboard IMU — see [m5_imu.md](m5_imu.md) for that.

```python
from m5.m5_accel import MMA7660

accel = MMA7660()
x_raw, y_raw, z_raw = accel.read_raw()  # signed 6-bit counts, ~-32..31
x_g, y_g, z_g = accel.read_g()          # g, ~-1.5..1.5
```

Requires the physical MMA7660FC Grove unit plugged into the StickS3's Grove
port. `Grove_accelerometer.py` at the project root is the example script that
uses this module.
