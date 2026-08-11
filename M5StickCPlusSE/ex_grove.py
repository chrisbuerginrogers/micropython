"""Scans the Grove I2C port (SDA=G32, SCL=G33) and lists what answers."""

from machine import I2C, Pin
from m5 import m5_display
import time

NAME = "Grove Scan"


def run(display, should_stop):
    i2c = I2C(1, scl=Pin(33), sda=Pin(32), freq=100000)
    last = None
    while not should_stop():
        addrs = i2c.scan()
        if addrs != last:
            display.fill(m5_display.BLACK)
            display.draw_text_centered(10, 'Grove I2C', m5_display.WHITE, m5_display.BLACK)
            display.draw_text_centered(24, 'scan', m5_display.WHITE, m5_display.BLACK)
            if addrs:
                for i, addr in enumerate(addrs):
                    display.draw_text(10, 60 + i * 26, '0x{:02X}'.format(addr),
                                       m5_display.WHITE, m5_display.BLACK, scale=2)
            else:
                display.draw_text_centered(90, 'nothing found', m5_display.WHITE, m5_display.BLACK)
            last = addrs
        time.sleep_ms(500)
