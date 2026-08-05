"""Read RFID tags with the RFID2 Unit (WS1850S) on the Grove port.

Shows each tag's UID and type on the LCD as it's tapped, and prints the
same to the serial console. While a tag is held on the reader, BtnA dumps
one data block: an authenticated MIFARE Classic block, or the equivalent
Ultralight/NTAG pages.
"""

from time import sleep_ms
from m5.m5_display import Display, WHITE, BLACK
from m5.m5_buttons import Buttons
from m5.m5_rfid import RFID, DEFAULT_KEY, ReadError

GREEN = 0x07E0
YELLOW = 0xFFE0
GREY = 0x8410

display = Display()
display.fill(BLACK)

buttons = Buttons()
rfid = RFID()

TITLE_Y = 4
UID_Y = 28
TYPE_Y = 66
COUNT_Y = 88
HINT_Y = 114
BLOCK_Y = 134
BLOCK_ADDR = 4  # MIFARE Classic sector 1 / Ultralight page 4 - first user data

def center(y, text, color, scale=1, spacing=2):
    """Draw text centered on a line, blanking whatever was there before.

    draw_text_centered() clips anything too wide for the panel by itself,
    so this doesn't need its own character budget.
    """
    blank = " " * display.max_chars(scale, spacing)
    display.draw_text(0, y, blank, color, BLACK, scale=scale, spacing=spacing)
    display.draw_text_centered(y, text, color, BLACK, scale=scale, spacing=spacing)


def as_hex(data):
    return "".join("{:02X}".format(b) for b in data)


def show_uid(uid):
    """A 4-byte UID fits big on one line; 7- and 10-byte ones need two."""
    if len(uid) <= 4:
        center(UID_Y, as_hex(uid), GREEN, scale=2, spacing=0)
        center(UID_Y + 20, "", GREEN)
    else:
        half = (len(uid) + 1) // 2
        center(UID_Y, as_hex(uid[:half]), GREEN)
        center(UID_Y + 12, as_hex(uid[half:]), GREEN)


def short_type(name):
    """card_type() names are written for the console; trim for 135px."""
    name = name.split(" / ")[0]
    return name[7:] if name.startswith("MIFARE ") else name


center(TITLE_Y, "RFID", GREY)
center(UID_Y, "tap a tag", WHITE)

taps = 0
last_uid = None
block_read = False

while True:
    uid = rfid.read_uid()

    if uid is None:
        # Field is empty, so the next tag counts as a fresh tap even if
        # it's the same one coming back.
        if last_uid is not None:
            last_uid = None
            center(HINT_Y, "", GREY)
            center(BLOCK_Y, "", GREY)
        sleep_ms(150)
        continue

    if uid == last_uid:
        # Same tag still sitting on the reader. read_uid() just selected
        # it, so it's ready for a data read.
        if buttons.a.is_pressed() and not block_read:
            # MIFARE Classic wants an authenticated block read;
            # Ultralight/NTAG (SAK 0x00) has no such auth and reads pages
            # directly. Branch rather than try both - a failed
            # authentication drops the tag out of ACTIVE state, so the
            # second attempt would fail even when it should work.
            try:
                if rfid.sak == 0x00:
                    data = rfid.read_pages(BLOCK_ADDR)
                else:
                    data = rfid.read_block(BLOCK_ADDR, DEFAULT_KEY)
            except ReadError as exc:
                # The read didn't finish - the tag probably moved. Leave
                # block_read False so the next pass tries again.
                center(BLOCK_Y, "read failed", YELLOW)
                print("block {}: {}".format(BLOCK_ADDR, exc))
            else:
                if data is None:
                    # The tag is fine, it just won't serve this read.
                    center(BLOCK_Y, "blk {} locked".format(BLOCK_ADDR), YELLOW)
                    print("block {}: wrong key or wrong tag type".format(BLOCK_ADDR))
                else:
                    center(BLOCK_Y, "b{}:{}".format(BLOCK_ADDR, as_hex(data[:4])), GREEN)
                    print("block {}: {}".format(BLOCK_ADDR, as_hex(data)))
                block_read = True
        rfid.halt()
        sleep_ms(150)
        continue

    taps += 1
    last_uid = uid
    block_read = False
    card = rfid.card_type()
    print("tag {}  uid {}  sak 0x{:02X}  {}".format(taps, as_hex(uid), rfid.sak, card))

    show_uid(uid)
    center(TYPE_Y, short_type(card), WHITE)
    center(COUNT_Y, "tap {}".format(taps), GREY)
    center(HINT_Y, "BtnA: blk {}".format(BLOCK_ADDR), GREY)
    center(BLOCK_Y, "", GREY)

    # Halting is what makes lifting the tag off and tapping again read as
    # a second tap instead of one long one.
    rfid.halt()
    sleep_ms(150)
