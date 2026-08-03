"""M5Stack RFID2 Unit (WS1850S) - 13.56MHz ISO/IEC 14443-A reader on the Grove bus.

The WS1850S is an MFRC522 work-alike: same register map, same command
set, but reached over I2C at address 0x28 rather than the MFRC522's usual
SPI. Ported from M5Stack's own driver
(github.com/m5stack/uiflow-micropython, `m5stack/libs/driver/mfrc522/`
plus `m5stack/libs/unit/rfid.py`), which is in turn a port of the Arduino
MFRC522 library everything in this space descends from.

Scope: reading. UID enumeration (including multi-card anticollision and
4/7/10-byte cascaded UIDs) and authenticated MIFARE Classic block reads
are here; writing blocks, the UID-changeable-card backdoor and the
sector-dump pretty-printer are not.

Confirmed live on M5StickS3 hardware - see the "Confirmed live" note in
`m5/CLAUDE.md` for what was actually read back.
"""

from machine import I2C, Pin
from time import sleep_ms, ticks_us, ticks_diff
from m5 import m5_power

GROVE_SDA_PIN = 9
GROVE_SCL_PIN = 10

# --- MFRC522 registers (datasheet ch. 9); only the ones used here ---
_COMMAND_REG = 0x01
_COMIRQ_REG = 0x04
_DIVIRQ_REG = 0x05
_ERROR_REG = 0x06
_STATUS2_REG = 0x08
_FIFODATA_REG = 0x09
_FIFOLEVEL_REG = 0x0A
_CONTROL_REG = 0x0C
_BITFRAMING_REG = 0x0D
_COLL_REG = 0x0E
_MODE_REG = 0x11
_TXCONTROL_REG = 0x14
_TXASK_REG = 0x15
_CRCRESULT_REGH = 0x21
_CRCRESULT_REGL = 0x22
_RFCFG_REG = 0x26
_TMODE_REG = 0x2A
_TPRESCALER_REG = 0x2B
_TRELOAD_REGH = 0x2C
_TRELOAD_REGL = 0x2D
_VERSION_REG = 0x37

# --- PCD (reader-side) commands (datasheet ch. 10) ---
_PCD_IDLE = 0x00
_PCD_CALCCRC = 0x03
_PCD_TRANSCEIVE = 0x0C
_PCD_MFAUTHENT = 0x0E
_PCD_SOFTRESET = 0x0F

# --- PICC (card-side) commands (ISO 14443-3 Type A, and MIFARE Classic) ---
_PICC_REQA = 0x26  # 7-bit short frame; wakes cards in IDLE only
_PICC_WUPA = 0x52  # 7-bit short frame; wakes cards in IDLE *and* HALT
_PICC_CT = 0x88  # cascade tag, marks a UID longer than this level carries
_PICC_SEL_CL1 = 0x93
_PICC_SEL_CL2 = 0x95
_PICC_SEL_CL3 = 0x97
_PICC_HLTA = 0x50
_PICC_AUTH_KEY_A = 0x60
_PICC_AUTH_KEY_B = 0x61
_PICC_MF_READ = 0x30

#: Factory key for a blank MIFARE Classic - every sector, both A and B.
DEFAULT_KEY = b"\xff\xff\xff\xff\xff\xff"

# Status codes, same numbering as the driver this came from.
STATUS_OK = 1
STATUS_ERROR = 2
STATUS_COLLISION = 3
STATUS_TIMEOUT = 4
STATUS_NO_ROOM = 5
STATUS_INTERNAL_ERROR = 6
STATUS_INVALID = 7
STATUS_CRC_WRONG = 8
STATUS_MIFARE_NACK = 9

STATUS_NAMES = {
    STATUS_OK: "ok",
    STATUS_ERROR: "communication error",
    STATUS_COLLISION: "collision",
    STATUS_TIMEOUT: "timeout",
    STATUS_NO_ROOM: "buffer too small",
    STATUS_INTERNAL_ERROR: "internal error",
    STATUS_INVALID: "invalid argument",
    STATUS_CRC_WRONG: "CRC mismatch",
    STATUS_MIFARE_NACK: "card sent NAK",
}

# Receiver gain settings for set_antenna_gain(), RFCfgReg RxGain[6:4]
# (datasheet table 98). Higher = longer read range, more noise.
GAIN_18DB = 0x00 << 4
GAIN_23DB = 0x01 << 4
GAIN_33DB = 0x04 << 4
GAIN_38DB = 0x05 << 4
GAIN_43DB = 0x06 << 4
GAIN_48DB = 0x07 << 4

# SAK byte -> card type, from NXP AN10833.
_SAK_TYPES = {
    0x00: "MIFARE Ultralight / Ultralight C",
    0x01: "MIFARE TNP3XXX",
    0x08: "MIFARE Classic 1K",
    0x09: "MIFARE Mini",
    0x10: "MIFARE Plus",
    0x11: "MIFARE Plus",
    0x18: "MIFARE Classic 4K",
}


class RFID:
    ADDR = 0x28

    def __init__(self, i2c=None, addr=ADDR):
        m5_power.power_on_grove_5v()
        self.i2c = i2c or I2C(0, scl=Pin(GROVE_SCL_PIN), sda=Pin(GROVE_SDA_PIN), freq=100000)
        self.addr = addr

        #: UID of the card selected by the last successful select(), and
        #: how many of these 10 bytes are real (4, 7 or 10).
        self.uid = bytearray(10)
        self.uid_size = 0
        #: SAK byte from that same select(), which card_type() decodes.
        self.sak = 0

        self._crc = bytearray(2)
        self._buf1 = bytearray(1)
        self._atqa = bytearray(2)
        self._auth_buf = bytearray(12)
        self._sel_buf = bytearray(9)

        self.reset()

    # ------------------------------------------------------------------
    # Reader (PCD) setup and raw register access
    # ------------------------------------------------------------------

    def reset(self):
        """Soft-reset the reader and reapply the ISO 14443-A settings.

        Called by __init__; only needed by hand if the reader wedges.
        """
        self._write(_COMMAND_REG, _PCD_SOFTRESET)
        sleep_ms(50)
        while self._read(_COMMAND_REG) & (1 << 4):
            pass  # PowerDown still set - the reset hasn't finished

        # Timer: TAuto, so it starts by itself the moment transmission
        # ends. Prescaler 0xA9 = 169 gives f_timer 40kHz, and a reload of
        # 0x03E8 = 1000 ticks makes that a 25ms answer timeout.
        self._write(_TMODE_REG, 0x80)
        self._write(_TPRESCALER_REG, 0xA9)
        self._write(_TRELOAD_REGH, 0x03)
        self._write(_TRELOAD_REGL, 0xE8)

        self._write(_TXASK_REG, 0x40)  # force 100% ASK modulation
        self._write(_MODE_REG, 0x3D)  # CRC preset 0x6363 (ISO 14443-3 6.2.4)
        self.antenna_on()

    def version(self):
        """VersionReg. Useful only as an "is the unit answering" check -
        the WS1850S does not report one of the MFRC522's documented
        0x90/0x91/0x92 values.
        """
        return self._read(_VERSION_REG)

    def antenna_on(self):
        """Enable antenna drivers TX1/TX2 - the reset turns them off."""
        value = self._read(_TXCONTROL_REG)
        if (value & 0x03) != 0x03:
            self._write(_TXCONTROL_REG, value | 0x03)

    def antenna_off(self):
        """Drop the RF field. Worth doing between polls on battery."""
        self._clear_bits(_TXCONTROL_REG, 0x03)

    def set_antenna_gain(self, gain):
        """Set receiver gain to one of the GAIN_* constants.

        The reset default is GAIN_33DB. Raising it to GAIN_48DB is the
        usual fix when a card only reads while touching the unit.
        """
        self._clear_bits(_RFCFG_REG, 0x07 << 4)
        self._set_bits(_RFCFG_REG, gain & (0x07 << 4))

    def _read(self, reg):
        return self.i2c.readfrom_mem(self.addr, reg, 1)[0]

    def _write(self, reg, val):
        self.i2c.writeto_mem(self.addr, reg, bytes([val]))

    def _write_bytes(self, reg, data):
        self.i2c.writeto_mem(self.addr, reg, data)

    def _set_bits(self, reg, mask):
        self._write(reg, self._read(reg) | mask)

    def _clear_bits(self, reg, mask):
        self._write(reg, self._read(reg) & ~mask & 0xFF)

    def _read_fifo(self, buf, n, rx_align):
        """Read n bytes out of the FIFO into buf[0:n].

        FIFODataReg does not auto-increment - reading it repeatedly pops
        successive FIFO bytes, so one address write plus an n-byte read
        is the whole transfer.

        rx_align means the first received byte only carries bits
        rx_align..7, and buf[0]'s lower bits are UID bits we already knew
        and must keep. (M5Stack's port writes that merge as
        `(data[0] & ~mask) | (data[0] & mask)`, which is just `data[0]` -
        a no-op that drops the known bits. It never bites them because it
        only matters mid-anticollision, i.e. with two or more cards in
        the field. This does the merge the Arduino original does.)
        """
        first = buf[0]
        self.i2c.writeto(self.addr, bytes([_FIFODATA_REG]))
        self.i2c.readfrom_into(self.addr, memoryview(buf)[0:n])
        if rx_align:
            mask = (0xFF << rx_align) & 0xFF
            buf[0] = (first & ~mask & 0xFF) | (buf[0] & mask)

    def _calculate_crc(self, data, result):
        """CRC_A over `data` into the 2-byte `result`, low byte first."""
        self._write(_COMMAND_REG, _PCD_IDLE)
        self._write(_DIVIRQ_REG, 0x04)  # clear CRCIRq
        self._set_bits(_FIFOLEVEL_REG, 0x80)  # flush FIFO
        self._write_bytes(_FIFODATA_REG, data)
        self._write(_COMMAND_REG, _PCD_CALCCRC)

        start = ticks_us()
        while not (self._read(_DIVIRQ_REG) & 0x04):
            if ticks_diff(ticks_us(), start) > 89000:
                return STATUS_TIMEOUT

        self._write(_COMMAND_REG, _PCD_IDLE)
        result[0] = self._read(_CRCRESULT_REGL)
        result[1] = self._read(_CRCRESULT_REGH)
        return STATUS_OK

    # ------------------------------------------------------------------
    # Card (PICC) transport
    # ------------------------------------------------------------------

    def _communicate(self, command, wait_irq, send_data, valid_bits=0,
                     rx_align=0, check_crc=False, back_data=None):
        """Run one reader command. Returns (status, n_received, valid_bits).

        `valid_bits` in is how many bits of send_data's last byte to
        transmit (0 = all 8); out it is how many bits of the last
        received byte are valid. Received bytes land in `back_data`, which
        must be big enough for the whole answer - pass None to discard it.
        """
        self._write(_COMMAND_REG, _PCD_IDLE)  # stop whatever is running
        self._write(_COMIRQ_REG, 0x7F)  # clear all interrupt request bits
        self._set_bits(_FIFOLEVEL_REG, 0x80)  # flush FIFO
        self._write_bytes(_FIFODATA_REG, send_data)
        self._write(_BITFRAMING_REG, (rx_align << 4) + valid_bits)
        self._write(_COMMAND_REG, command)
        if command == _PCD_TRANSCEIVE:
            self._set_bits(_BITFRAMING_REG, 0x80)  # StartSend

        # reset() set TAuto, so the 25ms answer timer runs itself.
        start = ticks_us()
        while True:
            n = self._read(_COMIRQ_REG)
            if n & wait_irq:
                break
            if n & 0x01:  # TimerIRq - no card answered in time
                return (STATUS_TIMEOUT, 0, valid_bits)
            if ticks_diff(ticks_us(), start) >= 37500:
                # Emergency break at ~1.5 timer periods: if TimerIRq
                # itself never arrived, the reader has stopped talking.
                # (M5Stack's port subtracts raw ticks_us() values here
                # rather than using ticks_diff, which reads negative
                # across the counter's ~17.9 minute wrap.)
                return (STATUS_TIMEOUT, 0, valid_bits)

        error = self._read(_ERROR_REG)
        if error & 0x13:  # BufferOvfl | ParityErr | ProtocolErr
            return (STATUS_ERROR, 0, valid_bits)

        n_back = 0
        if back_data is not None:
            n_back = self._read(_FIFOLEVEL_REG)
            if n_back > len(back_data):
                return (STATUS_NO_ROOM, 0, valid_bits)
            if n_back:
                self._read_fifo(back_data, n_back, rx_align)
                valid_bits = self._read(_CONTROL_REG) & 0x07

        if error & 0x08:  # CollErr - more than one card answered
            return (STATUS_COLLISION, n_back, valid_bits)

        if n_back and check_crc:
            if n_back == 1 and valid_bits == 4:
                return (STATUS_MIFARE_NACK, n_back, valid_bits)
            if n_back < 2 or valid_bits != 0:
                return (STATUS_CRC_WRONG, n_back, valid_bits)
            status = self._calculate_crc(memoryview(back_data)[0:n_back - 2], self._crc)
            if status != STATUS_OK:
                return (status, n_back, valid_bits)
            if back_data[n_back - 2] != self._crc[0] or back_data[n_back - 1] != self._crc[1]:
                return (STATUS_CRC_WRONG, n_back, valid_bits)

        return (STATUS_OK, n_back, valid_bits)

    def _transceive(self, send_data, valid_bits=0, rx_align=0,
                    check_crc=False, back_data=None):
        # 0x30 = RxIRq | IdleIRq, either of which means "answer arrived".
        return self._communicate(_PCD_TRANSCEIVE, 0x30, send_data,
                                 valid_bits=valid_bits, rx_align=rx_align,
                                 check_crc=check_crc, back_data=back_data)

    def _reqa_or_wupa(self, command):
        """Send REQA/WUPA and check the 2-byte ATQA answer."""
        self._clear_bits(_COLL_REG, 0x80)  # ValuesAfterColl=1
        self._buf1[0] = command
        status, n, valid_bits = self._transceive(self._buf1, valid_bits=7,
                                                 back_data=self._atqa)
        if status != STATUS_OK:
            return status
        if n != 2 or valid_bits != 0:  # ATQA is exactly 2 whole bytes
            return STATUS_ERROR
        return STATUS_OK

    # ------------------------------------------------------------------
    # Selecting a card
    # ------------------------------------------------------------------

    def request(self, wake_halted=True):
        """Ask any card in the field to identify itself.

        Returns a status code; STATUS_OK or STATUS_COLLISION both mean at
        least one card is there. `wake_halted` retries with WUPA, which a
        card that has already been halt()ed will answer and REQA won't.
        """
        status = self._reqa_or_wupa(_PICC_REQA)
        if status in (STATUS_OK, STATUS_COLLISION) or not wake_halted:
            return status
        return self._reqa_or_wupa(_PICC_WUPA)

    def is_card_present(self):
        """True if a card answered. Cheap enough to poll in a loop."""
        return self.request() in (STATUS_OK, STATUS_COLLISION)

    def select(self):
        """Run anticollision + SELECT, filling in .uid/.uid_size/.sak.

        The card must already be in READY state, so call request() first
        (read_uid() does both). Returns a status code.
        """
        buf = self._sel_buf
        mv = memoryview(buf)
        cascade_level = 1
        uid_index = 0
        uid_complete = False

        # ValuesAfterColl=1: bits received after a collision are cleared.
        self._clear_bits(_COLL_REG, 0x80)

        while not uid_complete:
            # Each cascade level carries 4 more UID bytes; levels past the
            # first spend one of those on the cascade tag instead, hence
            # UIDs of 4, 7 and 10 bytes rather than 4, 8 and 12.
            if cascade_level == 1:
                buf[0] = _PICC_SEL_CL1
                uid_index = 0
            elif cascade_level == 2:
                buf[0] = _PICC_SEL_CL2
                uid_index = 3
            elif cascade_level == 3:
                buf[0] = _PICC_SEL_CL3
                uid_index = 6
            else:
                return STATUS_INTERNAL_ERROR

            # We start each level knowing nothing, and let ANTICOLLISION
            # tell us the bits; a collision moves this forward one bit at
            # a time until all 32 are known and we can SELECT.
            known_bits = 0
            select_done = False
            while not select_done:
                if known_bits >= 32:
                    # SELECT: all 4 UID bytes plus their BCC, CRC'd.
                    buf[1] = 0x70  # NVB: 7 valid bytes
                    buf[6] = buf[2] ^ buf[3] ^ buf[4] ^ buf[5]
                    status = self._calculate_crc(mv[0:7], mv[7:9])
                    if status != STATUS_OK:
                        return status
                    tx_last_bits = 0
                    buffer_used = 9
                    response = mv[6:9]  # SAK + its 2 CRC bytes
                else:
                    # ANTICOLLISION: send what we know, card sends the rest.
                    tx_last_bits = known_bits % 8
                    index = 2 + known_bits // 8
                    buf[1] = (index << 4) + tx_last_bits  # NVB
                    buffer_used = index + (1 if tx_last_bits else 0)
                    response = mv[index:]

                rx_align = tx_last_bits
                self._write(_BITFRAMING_REG, (rx_align << 4) + tx_last_bits)

                status, n, tx_last_bits = self._transceive(
                    mv[0:buffer_used], valid_bits=tx_last_bits,
                    rx_align=rx_align, back_data=response)

                if status == STATUS_COLLISION:
                    coll = self._read(_COLL_REG)
                    if coll & 0x20:  # CollPosNotValid
                        return STATUS_COLLISION
                    position = coll & 0x1F
                    position = 32 if position == 0 else position
                    if position <= known_bits:
                        return STATUS_INTERNAL_ERROR  # no progress
                    # Two cards differ at this bit; take the one with a 1
                    # there and let the other drop out of the loop.
                    known_bits = position
                    bit = (known_bits - 1) % 8
                    index = 1 + (known_bits // 8) + (1 if bit else 0)
                    buf[index] |= 1 << bit
                elif status != STATUS_OK:
                    return status
                elif known_bits >= 32:
                    select_done = True  # that was the SELECT
                else:
                    known_bits = 32  # anticollision filled the rest in

            # BCC came from us, so only the 4 (or 3 + cascade tag) UID
            # bytes are worth copying out.
            index = 3 if buf[2] == _PICC_CT else 2
            count = 3 if buf[2] == _PICC_CT else 4
            self.uid[uid_index:uid_index + count] = buf[index:index + count]

            if n != 3 or tx_last_bits != 0:  # SAK is 1 byte + 2 CRC bytes
                return STATUS_ERROR
            status = self._calculate_crc(response[0:1], mv[2:4])
            if status != STATUS_OK:
                return status
            if buf[2] != response[1] or buf[3] != response[2]:
                return STATUS_CRC_WRONG

            if response[0] & 0x04:  # cascade bit - more UID to come
                cascade_level += 1
            else:
                uid_complete = True
                self.sak = response[0]

        # 1 level -> 4 bytes, 2 -> 7, 3 -> 10. M5Stack's driver never
        # tracks this and hands back all 10 bytes regardless, so a 4-byte
        # UID comes out padded with whatever was left from last time.
        self.uid_size = 3 * cascade_level + 1
        return STATUS_OK

    def read_uid(self):
        """Wake and select one card; returns its UID as bytes, or None.

        4 bytes for a MIFARE Classic, 7 for an Ultralight/NTAG.
        """
        if self.request() not in (STATUS_OK, STATUS_COLLISION):
            return None
        if self.select() != STATUS_OK:
            return None
        return bytes(self.uid[:self.uid_size])

    def card_type(self):
        """Card type of the last select(), decoded from its SAK byte."""
        if self.sak & 0x04:
            return "incomplete UID"
        name = _SAK_TYPES.get(self.sak)
        if name:
            return name
        if self.sak & 0x20:
            return "ISO/IEC 14443-4"
        if self.sak & 0x40:
            return "ISO/IEC 18092 (NFC)"
        return "unknown"

    def halt(self):
        """Put the selected card back to sleep and end the crypto session.

        Do this when you're done with a card, otherwise it keeps answering
        and you cannot tell "still there" from "tapped again". A halted
        card ignores REQA but still answers WUPA, which request() sends.
        """
        buf = bytearray(4)
        buf[0] = _PICC_HLTA
        buf[1] = 0
        status = self._calculate_crc(memoryview(buf)[0:2], memoryview(buf)[2:4])
        if status == STATUS_OK:
            # Per ISO 14443-3, a card that stays silent has accepted the
            # HLTA - so a timeout here is the success case.
            self._transceive(buf)
        self._clear_bits(_STATUS2_REG, 0x08)  # clear MFCrypto1On

    # ------------------------------------------------------------------
    # MIFARE Classic block reads
    # ------------------------------------------------------------------

    def authenticate(self, block, key=DEFAULT_KEY, use_key_b=False):
        """Open a crypto session on the sector containing `block`.

        Stays open until halt(), and every later block in that same
        sector can be read without re-authenticating.
        """
        if len(key) != 6:
            return STATUS_INVALID
        buf = self._auth_buf
        buf[0] = _PICC_AUTH_KEY_B if use_key_b else _PICC_AUTH_KEY_A
        buf[1] = block
        buf[2:8] = key
        buf[8:12] = self.uid[0:4]  # the crypto1 nonce uses the low 4 bytes
        status, _, _ = self._communicate(_PCD_MFAUTHENT, 0x10, buf)  # IdleIRq
        return status

    def read_block(self, block, key=DEFAULT_KEY, use_key_b=False):
        """Read one 16-byte MIFARE Classic block; None if it fails.

        Authenticates the sector first, so this works standalone after a
        read_uid(). Block 0 is the manufacturer block and every 4th block
        (3, 7, 11, ...) is a sector trailer holding keys, not user data -
        key A always reads back as zeros there.

        Ultralight/NTAG tags do not use this authentication and will
        always return None here; read_pages() is their equivalent.
        """
        if self.authenticate(block, key, use_key_b) != STATUS_OK:
            return None
        return self._mifare_read(block)

    def read_pages(self, page):
        """Read 4 Ultralight/NTAG pages (16 bytes) starting at `page`.

        Same 0x30 command as read_block(), minus the authentication that
        those tags don't implement - the read rolls over the end of tag
        memory back to page 0 rather than stopping. Returns None on a
        MIFARE Classic tag, which won't answer 0x30 unauthenticated.
        """
        return self._mifare_read(page)

    def _mifare_read(self, addr):
        buf = bytearray(18)  # 16 data bytes + 2 CRC bytes
        buf[0] = _PICC_MF_READ
        buf[1] = addr
        mv = memoryview(buf)
        if self._calculate_crc(mv[0:2], mv[2:4]) != STATUS_OK:
            return None
        # Sending from and receiving into one buffer is safe: the command
        # is already in the reader's FIFO before the answer comes back.
        status, n, _ = self._transceive(mv[0:4], check_crc=True, back_data=buf)
        if status != STATUS_OK or n != 18:
            return None
        return bytes(buf[:16])
