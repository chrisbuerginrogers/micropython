"""Live state of Button A (front), Button B (side), and the power key.

Button A is GPIO37, Button B is GPIO39 -- both active-low, both input-only
pins on the classic ESP32 (no internal pull-up available), which is why
the board carries its own pull-up resistors and these are opened as plain
Pin.IN with no pull requested. The power key has no GPIO of its own; it's
read through the AXP192 over I2C (see m5_power.power_button()).
"""

from machine import Pin
from m5 import m5_display, m5_power
import time

NAME = "Buttons"


_FLASH_MS = 500  # how long a power-key press stays shown as YES


def run(display, should_stop):
    a = Pin(37, Pin.IN)
    b = Pin(39, Pin.IN)

    display.fill(m5_display.BLACK)
    last = None
    short_until = 0
    long_until = 0
    while not should_stop():
        short, long_ = m5_power.power_button()
        now = time.ticks_ms()
        if short:
            short_until = time.ticks_add(now, _FLASH_MS)
        if long_:
            long_until = time.ticks_add(now, _FLASH_MS)
        short_shown = time.ticks_diff(short_until, now) > 0
        long_shown = time.ticks_diff(long_until, now) > 0

        state = (a.value(), b.value(), short_shown, long_shown)
        if state != last:
            display.fill(m5_display.BLACK)
            display.draw_text(4, 30, 'A: ' + ('DOWN' if a.value() == 0 else 'up'),
                               m5_display.WHITE, m5_display.BLACK, scale=2)
            display.draw_text(4, 60, 'B: ' + ('DOWN' if b.value() == 0 else 'up'),
                               m5_display.WHITE, m5_display.BLACK, scale=2)
            display.draw_text(4, 100, 'PWR short:', m5_display.WHITE, m5_display.BLACK)
            display.draw_text(4, 112, 'YES' if short_shown else 'no', m5_display.WHITE, m5_display.BLACK)
            display.draw_text(4, 132, 'PWR long:', m5_display.WHITE, m5_display.BLACK)
            display.draw_text(4, 144, 'YES' if long_shown else 'no', m5_display.WHITE, m5_display.BLACK)
            last = state
        time.sleep_ms(30)
