"""Sweeps the passive buzzer (GPIO2) up and down through an audible range."""

from machine import Pin, PWM
from m5 import m5_display
import time

NAME = "Buzzer"


def run(display, should_stop):
    buzzer = PWM(Pin(2))
    display.fill(m5_display.BLACK)
    display.draw_text_centered(100, 'BUZZING', m5_display.WHITE, m5_display.BLACK, scale=2)
    try:
        freq = 220
        rising = True
        while not should_stop():
            buzzer.freq(freq)
            buzzer.duty_u16(20000)  # square wave is all a passive buzzer needs
            freq += 8 if rising else -8
            if freq >= 1200:
                rising = False
            elif freq <= 220:
                rising = True
            time.sleep_ms(5)
    finally:
        buzzer.duty_u16(0)
        buzzer.deinit()
