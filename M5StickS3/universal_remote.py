"""Generic consumer-IR remote protocols: NEC, Sony SIRC, and Philips
RC5 - the "big three" protocols most non-LEGO IR remotes speak (TVs,
AV receivers, universal remotes), distinct from the LEGO-specific
protocols in rcx_ir.py and power_functions.py.

Bit encoding and timing for all three are ported from Peter Hinch's
long-established MicroPython IR library
(github.com/peterhinch/micropython_ir, ir_tx/{nec,sony,philips}.py and
ir_rx/{nec,sony}.py) rather than reconstructed from memory. NEC and
Sony's encode/decode round-trip is self-verified against known
(address, command) pairs in pure Python with no hardware involved -
see this file's accompanying test, run separately since m5.m5_ir isn't
importable off-device.

What's implemented:
  - NEC: encode (send) and decode (from m5_ir.IRReceiver's raw
    pulses). The most common protocol - most "generic" universal
    remotes and a huge range of consumer electronics use it.
  - Sony SIRC: encode and decode, 12-bit form only (7-bit command +
    5-bit address, the original/most common variant - the 15- and
    20-bit extended forms aren't implemented). Needs a 40kHz carrier,
    not the usual 38kHz.
  - Philips RC5: encode (send) only. Its biphase/Manchester encoding
    needs each bit's first half-period to sometimes merge into the
    previous segment rather than always start a new one (see
    _rc5_durations, ported line-for-line from the reference's
    append()/add() array-mutation approach) - decoding that back out
    of a noisy real-world pulse capture is more intricate than NEC/
    Sony's simpler pulse-distance/pulse-width schemes, so RC5 receive
    isn't implemented here. Port ir_rx/philips.py if you need it.
"""

from m5.m5_ir import IRTransmitter, IRReceiver
import time

# --- NEC ---------------------------------------------------------------

_NEC_BURST_US = 563
_NEC_ONE_SPACE_US = 1687
_NEC_ZERO_SPACE_US = 563


def _nec_durations(addr, data):
    """addr: 8-bit address (its complement is sent automatically), or
    a 16-bit value to send as a raw "extended" address with no
    complement check, for devices that use those."""
    if addr < 256:
        addr16 = addr | ((addr ^ 0xFF) << 8)
    else:
        addr16 = addr
    data16 = data | ((data ^ 0xFF) << 8)

    durations = [9000, 4500]
    for value in (addr16, data16):
        for _ in range(16):
            durations.append(_NEC_BURST_US)
            durations.append(_NEC_ONE_SPACE_US if value & 1 else _NEC_ZERO_SPACE_US)
            value >>= 1
    durations.append(_NEC_BURST_US)
    return durations


def send_nec(addr, data):
    IRTransmitter().send(_nec_durations(addr, data))


def decode_nec(durations):
    """durations: as returned by IRReceiver.read(). Returns (addr,
    data), or None if this isn't a valid NEC data frame (also None for
    repeat codes, which carry no address/data of their own)."""
    if len(durations) < 2 + 64 or durations[0] < 7000 or durations[1] < 3000:
        return None

    bits = []
    idx = 2
    for _ in range(32):
        bits.append(1 if durations[idx + 1] > 1120 else 0)
        idx += 2

    def byte_from(bit_slice):
        v = 0
        for i, b in enumerate(bit_slice):
            v |= b << i
        return v

    addr = byte_from(bits[0:8])
    addr_comp = byte_from(bits[8:16])
    data = byte_from(bits[16:24])
    data_comp = byte_from(bits[24:32])
    if data != (data_comp ^ 0xFF):
        return None
    if addr != (addr_comp ^ 0xFF):
        addr |= addr_comp << 8  # 16-bit extended address
    return addr, data


class NECReceiver:
    """Blocking NEC receiver on the onboard IR receiver."""

    def __init__(self):
        self._rx = IRReceiver()

    def read(self, timeout_ms=5000):
        return decode_nec(self._rx.read(timeout_ms=timeout_ms))


# --- Sony SIRC (12-bit) --------------------------------------------------

SONY_CARRIER_HZ = 40000


def _sony_durations(addr, cmd):
    """addr: 0-31 (5 bits), cmd: 0-127 (7 bits) - the standard 12-bit
    SIRC form used by most Sony TV/AV remotes."""
    value = (cmd & 0x7F) | ((addr & 0x1F) << 7)
    durations = [2400, 600]
    for _ in range(12):
        durations.append(1200 if value & 1 else 600)
        durations.append(600)
        value >>= 1
    return durations


def send_sony(addr, cmd, repeats=3, gap_ms=30):
    tx = IRTransmitter(carrier_hz=SONY_CARRIER_HZ)
    durations = _sony_durations(addr, cmd)
    for _ in range(repeats):
        tx.send(durations)
        time.sleep_ms(gap_ms)


def decode_sony(durations):
    """durations: as returned by IRReceiver.read(). Returns (addr,
    cmd) for the standard 12-bit form, or None if not a valid frame."""
    if len(durations) < 2 + 24 or durations[0] < 1800:
        return None

    bits = []
    idx = 2
    for _ in range(12):
        bits.append(1 if durations[idx] > 900 else 0)
        idx += 2

    def byte_from(bit_slice):
        v = 0
        for i, b in enumerate(bit_slice):
            v |= b << i
        return v

    cmd = byte_from(bits[0:7])
    addr = byte_from(bits[7:12])
    return addr, cmd


class SonyReceiver:
    """Blocking Sony SIRC (12-bit) receiver on the onboard IR receiver."""

    def __init__(self):
        self._rx = IRReceiver()

    def read(self, timeout_ms=5000):
        return decode_sony(self._rx.read(timeout_ms=timeout_ms))


# --- Philips RC5 (send only) ---------------------------------------------

RC5_CARRIER_HZ = 36000
_RC5_HALFBIT_US = 889


def _rc5_durations(addr, cmd, toggle=0):
    """addr: 0-31 (5 bits), cmd: 0-127 (7 bits - RC5X extended range;
    standard RC5 commands are 0-63), toggle: 0 or 1 - flip this on
    each new (non-repeat) button press, same idea as rcx_ir.py's
    opcode-repeat toggle bit.

    Ported line-for-line from the reference's append()/add() array-
    mutation approach (see module docstring) rather than reformulated,
    since the "sometimes merge into the previous segment instead of
    appending a new one" logic is easy to get subtly wrong by
    reasoning about it fresh.
    """
    d = (
        (cmd & 0x3F)
        | ((addr & 0x1F) << 6)
        | (((cmd & 0x40) ^ 0x40) << 6)
        | ((toggle & 1) << 11)
    )
    durations = []
    carrier = [False]  # mutable cell so the closures below can flip it

    def append(*times):
        for t in times:
            durations.append(t)
            carrier[0] = not carrier[0]

    def add(t):
        durations[-1] += t

    mask = 0x2000
    while mask:
        if mask == 0x2000:
            append(_RC5_HALFBIT_US)  # S1: always a mark, always logical 1
        else:
            bit = bool(d & mask)
            if bit ^ carrier[0]:
                add(_RC5_HALFBIT_US)
                append(_RC5_HALFBIT_US)
            else:
                append(_RC5_HALFBIT_US, _RC5_HALFBIT_US)
        mask >>= 1
    return durations


def send_rc5(addr, cmd, toggle=0):
    IRTransmitter(carrier_hz=RC5_CARRIER_HZ).send(_rc5_durations(addr, cmd, toggle))


if __name__ == "__main__":
    print("Sending NEC addr=0x04 data=0x08 (a common 'power' code)...")
    send_nec(0x04, 0x08)
    time.sleep_ms(200)
    print("Sending Sony addr=1 cmd=21 (a common Sony TV 'power' code)...")
    send_sony(1, 21)
    time.sleep_ms(200)
    print("Sending RC5 addr=0 cmd=12 (a common Philips TV 'power' code)...")
    send_rc5(0, 12)
