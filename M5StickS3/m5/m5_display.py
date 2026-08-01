"""ST7789 LCD driver + minimal bitmap font for the StickS3's built-in screen."""

from machine import Pin, SPI
from time import sleep_ms
from m5 import m5_power

PANEL_W, PANEL_H = 135, 240
OFFSET_X, OFFSET_Y = 52, 40  # this panel's visible area sits inset in GRAM
GRAM_H = 320  # the ST7789's physical GRAM is 240x320; OFFSET_X/Y center our
              # 135x240 window within it (confirmed: 240-135=105 -> 52/53
              # split, 320-240=80 -> 40/40 split, matching OFFSET_X/Y exactly)

WHITE = 0xFFFF
BLACK = 0x0000

# Minimal 8x8 bitmap font (public-domain font8x8_basic, subset covering
# what the sample scripts in this folder need to print).
FONT_8X8 = {
    ' ': bytes([0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
    '.': bytes([0x00, 0x00, 0x00, 0x00, 0x00, 0x0C, 0x0C, 0x00]),
    '-': bytes([0x00, 0x00, 0x00, 0x3F, 0x00, 0x00, 0x00, 0x00]),
    '%': bytes([0x00, 0x63, 0x33, 0x18, 0x0C, 0x66, 0x63, 0x00]),
    '0': bytes([0x3E, 0x63, 0x73, 0x7B, 0x6F, 0x67, 0x3E, 0x00]),
    '1': bytes([0x0C, 0x0E, 0x0C, 0x0C, 0x0C, 0x0C, 0x3F, 0x00]),
    '2': bytes([0x1E, 0x33, 0x30, 0x1C, 0x06, 0x33, 0x3F, 0x00]),
    '3': bytes([0x1E, 0x33, 0x30, 0x1C, 0x30, 0x33, 0x1E, 0x00]),
    '4': bytes([0x38, 0x3C, 0x36, 0x33, 0x7F, 0x30, 0x78, 0x00]),
    '5': bytes([0x3F, 0x03, 0x1F, 0x30, 0x30, 0x33, 0x1E, 0x00]),
    '6': bytes([0x1C, 0x06, 0x03, 0x1F, 0x33, 0x33, 0x1E, 0x00]),
    '7': bytes([0x3F, 0x33, 0x30, 0x18, 0x0C, 0x0C, 0x0C, 0x00]),
    '8': bytes([0x1E, 0x33, 0x33, 0x1E, 0x33, 0x33, 0x1E, 0x00]),
    '9': bytes([0x1E, 0x33, 0x33, 0x3E, 0x30, 0x18, 0x0E, 0x00]),
    'C': bytes([0x3C, 0x66, 0x03, 0x03, 0x03, 0x66, 0x3C, 0x00]),
    'H': bytes([0x33, 0x33, 0x33, 0x3F, 0x33, 0x33, 0x33, 0x00]),
    'P': bytes([0x3F, 0x66, 0x66, 0x3E, 0x06, 0x06, 0x0F, 0x00]),
    'V': bytes([0x33, 0x33, 0x33, 0x33, 0x33, 0x1E, 0x0C, 0x00]),
    'W': bytes([0x63, 0x63, 0x63, 0x6B, 0x7F, 0x77, 0x63, 0x00]),
    'X': bytes([0x63, 0x63, 0x36, 0x1C, 0x1C, 0x36, 0x63, 0x00]),
    'Y': bytes([0x33, 0x33, 0x33, 0x1E, 0x0C, 0x0C, 0x1E, 0x00]),
    'Z': bytes([0x7F, 0x63, 0x31, 0x18, 0x4C, 0x66, 0x7F, 0x00]),
    'a': bytes([0x00, 0x00, 0x1E, 0x30, 0x3E, 0x33, 0x6E, 0x00]),
    'd': bytes([0x38, 0x30, 0x30, 0x3E, 0x33, 0x33, 0x6E, 0x00]),
    'e': bytes([0x00, 0x00, 0x1E, 0x33, 0x3F, 0x03, 0x1E, 0x00]),
    'g': bytes([0x00, 0x00, 0x6E, 0x33, 0x33, 0x3E, 0x30, 0x1F]),
    'h': bytes([0x07, 0x06, 0x36, 0x6E, 0x66, 0x66, 0x67, 0x00]),
    'l': bytes([0x0E, 0x0C, 0x0C, 0x0C, 0x0C, 0x0C, 0x1E, 0x00]),
    'm': bytes([0x00, 0x00, 0x33, 0x7F, 0x7F, 0x6B, 0x63, 0x00]),
    'o': bytes([0x00, 0x00, 0x1E, 0x33, 0x33, 0x33, 0x1E, 0x00]),
    'r': bytes([0x00, 0x00, 0x3B, 0x6E, 0x66, 0x06, 0x0F, 0x00]),
}


class Display:
    """Drives the StickS3's ST7789 panel: fill, and simple bitmap text."""

    WIDTH = PANEL_W
    HEIGHT = PANEL_H

    def __init__(self):
        m5_power.power_on_lcd()

        self._rst = Pin(21, Pin.OUT)
        self._dc = Pin(45, Pin.OUT)
        self._cs = Pin(41, Pin.OUT)
        self._spi = SPI(1, baudrate=20_000_000, polarity=0, phase=0,
                         sck=Pin(40), mosi=Pin(39))
        self._cs.value(1)

        self._rst.value(0)
        sleep_ms(10)
        self._rst.value(1)
        sleep_ms(120)

        self._write_cmd(0x01)  # SWRESET
        sleep_ms(150)
        self._write_cmd(0x11)  # SLPOUT
        sleep_ms(120)
        self._write_cmd(0x3A)  # COLMOD
        self._write_data(bytes([0x55]))  # 16 bits/pixel, RGB565
        self._write_cmd(0x36)  # MADCTL
        self._write_data(bytes([0x00]))
        self._write_cmd(0x21)  # INVON (this panel needs color inversion enabled)
        self._write_cmd(0x13)  # NORON
        self._write_cmd(0x29)  # DISPON
        sleep_ms(10)

        self._backlight = Pin(38, Pin.OUT)
        self._backlight.value(1)

    def _write_cmd(self, cmd):
        self._dc.value(0)
        self._cs.value(0)
        self._spi.write(bytes([cmd]))
        self._cs.value(1)

    def _write_data(self, data):
        self._dc.value(1)
        self._cs.value(0)
        self._spi.write(data)
        self._cs.value(1)

    def _set_window(self, x0, y0, x1, y1):
        x0 += OFFSET_X
        x1 += OFFSET_X
        y0 += OFFSET_Y
        y1 += OFFSET_Y
        self._write_cmd(0x2A)  # CASET
        self._write_data(bytes([x0 >> 8, x0 & 0xFF, x1 >> 8, x1 & 0xFF]))
        self._write_cmd(0x2B)  # RASET
        self._write_data(bytes([y0 >> 8, y0 & 0xFF, y1 >> 8, y1 & 0xFF]))
        self._write_cmd(0x2C)  # RAMWR

    def fill(self, color565):
        self._set_window(0, 0, PANEL_W - 1, PANEL_H - 1)
        line = bytes([color565 >> 8, color565 & 0xFF]) * PANEL_W
        self._dc.value(1)
        self._cs.value(0)
        for _ in range(PANEL_H):
            self._spi.write(line)
        self._cs.value(1)

    def draw_char(self, x, y, ch, color, bg, scale=1):
        glyph = FONT_8X8.get(ch, FONT_8X8[' '])
        size = 8 * scale
        self._set_window(x, y, x + size - 1, y + size - 1)
        fg_hi, fg_lo = color >> 8, color & 0xFF
        bg_hi, bg_lo = bg >> 8, bg & 0xFF
        self._dc.value(1)
        self._cs.value(0)
        for row_byte in glyph:
            row = bytearray(size * 2)
            for col in range(8):
                on = (row_byte >> col) & 1
                hi, lo = (fg_hi, fg_lo) if on else (bg_hi, bg_lo)
                for s in range(scale):
                    idx = (col * scale + s) * 2
                    row[idx] = hi
                    row[idx + 1] = lo
            for _ in range(scale):
                self._spi.write(row)
        self._cs.value(1)

    def draw_text(self, x, y, text, color, bg, scale=1, spacing=2):
        cell = 8 * scale + spacing
        for i, ch in enumerate(text):
            self.draw_char(x + i * cell, y, ch, color, bg, scale)

    def text_width(self, text, scale=1, spacing=2):
        cell = 8 * scale + spacing
        return len(text) * cell - spacing

    # --- Hardware vertical scroll (ST7789 VSCRDEF/VSCSAD) -----------------
    # Lets a scrolling strip-chart/oscilloscope trace redraw just one new
    # row per frame instead of repainting the whole plot area every time.

    def set_scroll_region(self, top, height):
        """Define a scrolling band `height` rows tall, starting `top` rows
        down from the top of the window (window-relative pixels). Rows
        outside the band are left alone (e.g. for static text above it)."""
        self._scroll_gram_top = OFFSET_Y + top
        self._scroll_height = height
        tfa = self._scroll_gram_top
        vsa = height
        bfa = GRAM_H - tfa - vsa
        self._write_cmd(0x33)  # VSCRDEF
        self._write_data(bytes([tfa >> 8, tfa & 0xFF, vsa >> 8, vsa & 0xFF,
                                 bfa >> 8, bfa & 0xFF]))

    def write_scroll_row(self, row, pixel_row):
        """Write one row of raw RGB565 bytes (WIDTH*2 long) into the scroll
        band at 0-based `row`, addressed directly in GRAM regardless of
        the current scroll offset."""
        gram_y = self._scroll_gram_top + row
        x0, x1 = OFFSET_X, OFFSET_X + PANEL_W - 1
        self._write_cmd(0x2A)  # CASET
        self._write_data(bytes([x0 >> 8, x0 & 0xFF, x1 >> 8, x1 & 0xFF]))
        self._write_cmd(0x2B)  # RASET
        self._write_data(bytes([gram_y >> 8, gram_y & 0xFF, gram_y >> 8, gram_y & 0xFF]))
        self._write_cmd(0x2C)  # RAMWR
        self._write_data(pixel_row)

    def scroll_to(self, row):
        """Show scroll-band row `row` (0-based) at the top of the band."""
        addr = self._scroll_gram_top + row
        self._write_cmd(0x37)  # VSCSAD
        self._write_data(bytes([addr >> 8, addr & 0xFF]))
