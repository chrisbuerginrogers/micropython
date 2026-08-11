"""Blinks the small red status LED (GPIO10)."""

from machine import Pin
from m5 import m5_display
import time

NAME = "Status LED"


def run(display, should_stop):
    led = Pin(10, Pin.OUT)
    display.fill(m5_display.BLACK)
    display.draw_text_centered(90, 'LED', m5_display.WHITE, m5_display.BLACK, scale=2)
    display.draw_text_centered(115, 'blinking', m5_display.WHITE, m5_display.BLACK)
    try:
        on = False
        while not should_stop():
            on = not on
            led.value(on)
            time.sleep_ms(300)
    finally:
        led.value(0)
