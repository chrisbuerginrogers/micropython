# m5_imu

The onboard 6-axis IMU (Bosch BMI270 — accelerometer + gyroscope, no
magnetometer). This is the *internal* chip on the shared internal I2C bus —
different from the external Grove accelerometer in
[m5_accel.md](m5_accel.md).

```python
from m5.m5_imu import IMU

imu = IMU()
x_g, y_g, z_g = imu.accel()          # g, one axis reads ~1.0 at rest (gravity)
x_dps, y_dps, z_dps = imu.gyro()     # degrees/sec
temp_c = imu.temperature()           # die temperature, not ambient
```

Construction runs the BMI270's mandatory init sequence (including uploading
Bosch's ~8KB config blob) — this takes a moment and will raise `OSError` if
the chip doesn't answer on I2C. First `accel()`/`gyro()` call right after
construction may read `(0,0,0)` before the first ODR conversion completes;
subsequent reads settle to real values.

`IMU(accel_odr=100, accel_scale=4, gyro_odr=100, gyro_scale=2000)` — defaults
are 100Hz output rate, ±4g / ±2000dps range; pass different values if you need
a different range or update rate.

Confirmed live: reads ~1g on Z at rest after a fix for an inherited driver bug
(see `m5_imu.py`'s docstring / `CLAUDE.md` if you're curious what broke).
