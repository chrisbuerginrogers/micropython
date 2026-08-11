"""BM8563 RTC: shows whatever time is currently stored on the chip,
ticking forward -- it keeps running across power cycles on its own, so
this doesn't touch/reset it. There's no WiFi/NTP credentials wired up in
this repo (see the root README's "Missing secrets files" section) to set
it automatically; set it yourself once with
m5_rtc.datetime((year, month, mday, hour, minute, second, weekday)).
"""

from m5 import m5_display, m5_rtc
import time

NAME = "RTC Clock"

_WEEKDAYS = ('Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun')


def run(display, should_stop):
    display.fill(m5_display.BLACK)
    display.draw_text_centered(20, 'RTC ticking', m5_display.WHITE, m5_display.BLACK)
    last = None
    while not should_stop():
        year, month, mday, hour, minute, second, weekday = m5_rtc.datetime()
        text = '{:04d}-{:02d}-{:02d}'.format(year, month, mday)
        time_text = '{:02d}:{:02d}:{:02d} {}'.format(hour, minute, second, _WEEKDAYS[weekday % 7])
        if (text, time_text) != last:
            display.fill(m5_display.BLACK)
            display.draw_text_centered(20, 'RTC ticking', m5_display.WHITE, m5_display.BLACK)
            display.draw_text_centered(80, text, m5_display.WHITE, m5_display.BLACK)
            display.draw_text_centered(100, time_text, m5_display.WHITE, m5_display.BLACK)
            last = (text, time_text)
        time.sleep_ms(100)
