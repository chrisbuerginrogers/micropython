"""LEGO Power Functions (PF) IR remote control - the protocol that
replaced the RCX's UART-over-IR scheme (see rcx_ir.py) across LEGO's
Technic/train motor and light IR receivers, 2007 onward.

Bit encoding, message layout, and PWM step values are ported from a
verified working Arduino implementation
(github.com/TheJarOS/LegoPowerFunctions-Arduino-Library,
legopowerfunctions.cpp) rather than reconstructed from a written spec.
That library's timing constants (156us mark, 260/546/1014us spaces)
were tuned against a real receiver with an oscilloscope per its own
comments, and are close to (but not identical to - likely measurement
vs. nominal-spec rounding) LEGO's published nominal values (~158us
mark, ~421/711/1184us total bit periods).

PF is transmit-only from a remote's perspective - the IR receiver
electronics don't talk back, so there's no equivalent of rcx_ir.py's
send_and_receive(). Two of the protocol's four message types are
implemented:
  - SingleOutput: PWM speed on one output (RED or BLUE) of one
    channel - the common case for driving a single motor.
  - ComboPWM: both outputs of a channel in one message - handy for
    differential-drive (tank steering) builds.
SinglePin and ComboMode (discrete clear/set/toggle-style control, less
commonly needed than PWM speed control) aren't implemented - see the
reference source above to add them.

Simplified relative to the reference: real PF remotes vary their
repeat interval based on how many times the same message has been sent
in a row (a bandwidth-sharing courtesy for multiple controllers
sharing a channel). This just sends a fixed number of repeats at a
fixed gap instead - correct at the bit level, just not the same
timing courtesy.

Never tested against a real PF receiver (none available) - verified
here: the bit/nibble encoding matches the reference source exactly,
and transmission runs without error on this repo's hardware.
"""

from m5.m5_ir import IRTransmitter
import time

_MARK_US = 156
_SPACE_LOW_US = 260
_SPACE_HIGH_US = 546
_SPACE_START_STOP_US = 1014

CH1, CH2, CH3, CH4 = 0x0, 0x1, 0x2, 0x3
RED, BLUE = 0x0, 0x1

PWM_FLT = 0x0
PWM_FWD1, PWM_FWD2, PWM_FWD3, PWM_FWD4 = 0x1, 0x2, 0x3, 0x4
PWM_FWD5, PWM_FWD6, PWM_FWD7 = 0x5, 0x6, 0x7
PWM_BRK = 0x8
PWM_REV7, PWM_REV6, PWM_REV5, PWM_REV4 = 0x9, 0xA, 0xB, 0xC
PWM_REV3, PWM_REV2, PWM_REV1 = 0xD, 0xE, 0xF

_MODE_PWM = 0x0


def _nibbles_to_durations(nib1, nib2, nib3, nib4):
    code1 = (nib1 << 4) | nib2
    code2 = (nib3 << 4) | nib4
    durations = [_MARK_US, _SPACE_START_STOP_US]
    for byte in (code1, code2):
        bit = 128
        while bit:
            durations.append(_MARK_US)
            durations.append(_SPACE_HIGH_US if byte & bit else _SPACE_LOW_US)
            bit >>= 1
    durations.append(_MARK_US)
    durations.append(_SPACE_START_STOP_US)
    return durations


class PowerFunctions:
    """Sends LEGO Power Functions IR commands. channel is 0-3
    (CH1-CH4, printed as 1-4 on the physical receiver's channel dial)."""

    def __init__(self):
        self._tx = IRTransmitter()
        self._toggle = [0, 0, 0, 0]

    def set_speed(self, channel, output, pwm_step, repeats=3, gap_ms=80):
        """Set one output (RED or BLUE) of a channel to a PWM_* step.
        Toggles automatically per LEGO's spec, so the receiver treats
        each call as a fresh command rather than a retransmit of the
        last one."""
        nib1 = self._toggle[channel] | channel
        nib2 = 0x4 | _MODE_PWM | output
        nib3 = pwm_step
        nib4 = 0xF ^ nib1 ^ nib2 ^ nib3
        self._toggle[channel] = 0 if self._toggle[channel] else 8

        durations = _nibbles_to_durations(nib1, nib2, nib3, nib4)
        for _ in range(repeats):
            self._tx.send(durations)
            time.sleep_ms(gap_ms)

    def set_combo_speed(self, channel, blue_step, red_step, repeats=3, gap_ms=80):
        """Set both outputs of a channel at once. No toggle bit - this
        message type is meant to be sent repeatedly while a value is
        held, same code each time."""
        nib1 = 0x4 | channel
        nib2 = blue_step
        nib3 = red_step
        nib4 = 0xF ^ nib1 ^ nib2 ^ nib3

        durations = _nibbles_to_durations(nib1, nib2, nib3, nib4)
        for _ in range(repeats):
            self._tx.send(durations)
            time.sleep_ms(gap_ms)


if __name__ == "__main__":
    pf = PowerFunctions()
    print("Driving CH1 RED forward (step 4) for 2s, then stopping...")
    pf.set_speed(CH1, RED, PWM_FWD4)
    time.sleep_ms(2000)
    pf.set_speed(CH1, RED, PWM_FLT)
    print("Done.")
