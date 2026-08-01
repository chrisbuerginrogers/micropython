"""Talk to a LEGO Mindstorms RCX brick over IR.

Byte-level framing (0x55 0xFF 0x00 header, each data byte followed by
its bitwise complement, trailing checksum + its complement) and the
opcode values below are ported from the NQC compiler's actual RCX
transport implementation (github.com/BrickBot/nqc,
rcxlib/RCX_PipeTransport.cpp - the real, still-maintained tool RCX
hobbyists use to talk to their bricks), not reconstructed from a
written description. Serial parameters (2400 baud, 8 data bits, odd
parity, 1 stop bit) are LEGO's documented values, cross-checked against
that same source.

What ISN'T independently verified here: how that UART bit-stream gets
modulated onto the IR carrier. NQC and the official LEGO tower handle
that inside the tower's own hardware/firmware, so there's no software
reference for it to port. This uses the standard on-off-keying
convention nearly every consumer IR link uses - carrier PRESENT for an
active/"space" bit, carrier ABSENT for idle/"mark" - since idling with
the LED constantly blasting IR would be an odd design choice. If a real
RCX doesn't respond, flip SPACE_IS_CARRIER_ON below first; everything
else (framing, opcodes, bit timing) is the part with real confidence
behind it.
"""

from m5.m5_ir import IRTransmitter, IRReceiver

SPACE_IS_CARRIER_ON = True  # flip this first if a real RCX stays silent

BIT_US = 417  # 1 / 2400 baud, rounded to the microsecond

# A handful of RCX opcodes, cross-checked between NQC's rcxlib and the
# community opcode reference at mralligator.com/rcx/opcodes.html. The
# RCX's reply opcode is the request's bitwise complement; NQC also
# toggles bit 0x08 on repeated identical commands so the RCX can tell a
# fresh command from an echo of the last one - not needed for one-shot
# use here, so it's always sent clear.
OP_ALIVE = 0x10
OP_GET_VERSIONS = 0x15
OP_GET_VALUE = 0x12
OP_GET_BATTERY_POWER = 0x30
OP_SET_MOTOR_POWER = 0x13
OP_PLAY_TONE = 0x23
OP_POWER_OFF = 0x60


def _is_on(uart_bit):
    return (uart_bit == 0) == SPACE_IS_CARRIER_ON


def _bits_for_byte(byte):
    bits = [0]  # start bit
    ones = 0
    for i in range(8):
        b = (byte >> i) & 1
        bits.append(b)
        ones += b
    bits.append(0 if (ones % 2 == 1) else 1)  # odd parity: total ones must be odd
    bits.append(1)  # stop bit
    return bits


def _encode_bits(raw_bytes):
    """UART-encodes raw_bytes (2400/8/odd/1) and returns a durations
    list (microseconds) ready for IRTransmitter.send()."""
    bits = []
    for byte in raw_bytes:
        bits.extend(_bits_for_byte(byte))

    runs = []  # (is_on, run_length_in_bits)
    prev = bits[0]
    run = 1
    for b in bits[1:]:
        if b == prev:
            run += 1
        else:
            runs.append((_is_on(prev), run))
            prev = b
            run = 1
    runs.append((_is_on(prev), run))

    if not runs[0][0]:
        # Leading idle before the first real edge - doesn't matter how
        # long we wait to start, so just drop it rather than send it.
        runs = runs[1:]

    return [length * BIT_US for _, length in runs]


def _decode_bits(durations):
    """Inverse of _encode_bits: durations (as returned by
    IRReceiver.read(), where durations[0] is always the first active
    period) back to a raw UART byte stream."""
    on_bit = 0 if SPACE_IS_CARRIER_ON else 1
    bits = []
    value = on_bit
    for dur in durations:
        n = max(1, round(dur / BIT_US))
        bits.extend([value] * n)
        value = 1 - value

    out = bytearray()
    i = 0
    while i + 11 <= len(bits):
        if bits[i] != 0:
            i += 1
            continue
        frame = bits[i:i + 11]
        data_bits, parity, stop = frame[1:9], frame[9], frame[10]
        if stop != 1:
            i += 1
            continue
        byte = 0
        for pos, b in enumerate(data_bits):
            byte |= b << pos
        ones = bin(byte).count("1")
        expected_parity = 0 if (ones % 2 == 1) else 1
        if parity != expected_parity:
            i += 1
            continue
        out.append(byte)
        i += 11
    return bytes(out)


def _build_message(opcode, args=b""):
    payload = bytes([opcode & 0xFF]) + bytes(args)
    checksum = sum(payload) & 0xFF

    out = bytearray(b"\x55\xff\x00")
    for b in payload:
        out.append(b)
        out.append((~b) & 0xFF)
    out.append(checksum)
    out.append((~checksum) & 0xFF)
    return bytes(out)


def _parse_reply(raw_bytes):
    """raw_bytes: a decoded literal UART byte stream. Finds the sync
    header, verifies every byte against its complement and the trailing
    checksum, and returns just the payload (opcode + args) - or None if
    nothing valid was found."""
    idx = raw_bytes.find(b"\x55\xff\x00")
    if idx < 0:
        return None
    body = raw_bytes[idx + 3:]
    if len(body) < 4 or len(body) % 2 != 0:
        return None

    data_bytes = bytearray()
    for i in range(0, len(body), 2):
        b, comp = body[i], body[i + 1]
        if (b ^ comp) != 0xFF:
            return None
        data_bytes.append(b)

    if len(data_bytes) < 2:
        return None
    payload, checksum = bytes(data_bytes[:-1]), data_bytes[-1]
    if (sum(payload) & 0xFF) != checksum:
        return None
    return payload


class RCX:
    def __init__(self):
        self._tx = IRTransmitter()
        self._rx = IRReceiver()

    def send(self, opcode, args=b""):
        """Sends a command; doesn't wait for a reply."""
        message = _build_message(opcode, args)
        self._tx.send(_encode_bits(message))

    def send_and_receive(self, opcode, args=b"", timeout_ms=500):
        """Sends a command and waits for the RCX's reply payload
        (opcode byte + argument bytes; complement/checksum already
        verified and stripped). Returns None on timeout or a framing
        failure."""
        self.send(opcode, args)
        durations = self._rx.read(timeout_ms=timeout_ms)
        if not durations:
            return None
        return _parse_reply(_decode_bits(durations))

    def alive(self, timeout_ms=500):
        """Pings the RCX. Returns True if it replied at all."""
        return self.send_and_receive(OP_ALIVE, timeout_ms=timeout_ms) is not None

    def play_tone(self, freq_hz, duration_1_100s):
        args = bytes([freq_hz & 0xFF, (freq_hz >> 8) & 0xFF, duration_1_100s & 0xFF])
        return self.send_and_receive(OP_PLAY_TONE, args)

    def get_battery_mv(self):
        reply = self.send_and_receive(OP_GET_BATTERY_POWER)
        if reply is None or len(reply) < 3:
            return None
        return reply[1] | (reply[2] << 8)


if __name__ == "__main__":
    rcx = RCX()
    print("Pinging RCX...")
    if rcx.alive():
        print("RCX responded!")
        mv = rcx.get_battery_mv()
        if mv is not None:
            print("Battery: {} mV".format(mv))
    else:
        print("No reply. Point the StickS3's IR window at the RCX's IR")
        print("window from a few inches away. If it still fails, try")
        print("flipping SPACE_IS_CARRIER_ON at the top of this file.")
