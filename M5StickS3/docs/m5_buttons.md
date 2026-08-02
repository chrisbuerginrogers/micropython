# m5_buttons

Debounced BtnA (the large front button, GPIO11) and BtnB (GPIO12).

```python
from m5.m5_buttons import Buttons

buttons = Buttons()

if buttons.a.is_pressed():
    ...

buttons.a.wait_for_press()
buttons.a.wait_for_release()
```

- `Buttons()` gives you `.a` and `.b`, each a `Button`.
- `is_pressed()` — debounced (20ms), instantaneous state; call it every loop
  iteration, it's cheap.
- `wait_for_press()` / `wait_for_release()` — blocking helpers, useful for a
  "press to toggle, then wait until they let go before checking again" pattern
  (see `IMU.py`'s pause/resume or `battery_status.py`'s charge toggle).

Both buttons are active-low with an internal pull-up — you don't need to wire
anything or configure pull mode yourself.
