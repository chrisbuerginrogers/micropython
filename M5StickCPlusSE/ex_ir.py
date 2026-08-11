"""Sends a raw 38kHz-carrier IR pulse train (GPIO9) once a second.

This is a raw pulse burst, not a decoded consumer-electronics protocol
(NEC/Sony/RC5) -- see M5StickS3/universal_remote.py for that. There's no
IR receiver on this board to confirm reception; this only confirms the
transmitter fires without error. Most phone camera sensors can see
850-950nm IR LEDs light up (the human eye can't), which is a quick way
to sanity-check it's actually pulsing.
"""

from machine import Pin
from esp32 import RMT
from m5 import m5_display
import time

NAME = "IR Blaster"

TX_PIN = 9
CARRIER_HZ = 38000

# A generic NEC-shaped burst: 9ms leader, 4.5ms space, then 8 bit-cells
# (560us mark + 560/1690us space for 0/1) -- not tied to any real remote.
_LEADER = [9000, 4500]
_BIT0 = [560, 560]
_BIT1 = [560, 1690]
_STOP = [560]


def _nec_pulses(byte):
    pulses = list(_LEADER)
    for i in range(8):
        pulses += _BIT1 if (byte >> i) & 1 else _BIT0
    pulses += _STOP
    return pulses


def run(display, should_stop):
    rmt = RMT(0, pin=Pin(TX_PIN), resolution_hz=1_000_000,
              idle_level=False, tx_carrier=(CARRIER_HZ, 33, True))
    pulses = _nec_pulses(0xA5)

    display.fill(m5_display.BLACK)
    display.draw_text_centered(90, 'IR', m5_display.WHITE, m5_display.BLACK, scale=2)
    display.draw_text_centered(115, 'sending', m5_display.WHITE, m5_display.BLACK, scale=2)
    while not should_stop():
        rmt.write_pulses(pulses, True)
        rmt.wait_done(timeout=200)
        time.sleep_ms(1000)
