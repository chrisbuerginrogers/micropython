# m5_display

Driver for the StickS3's built-in 1.14" ST7789 LCD (135×240), plus a minimal
bitmap font for text. Powers itself on via `m5_power.power_on_lcd()`.

```python
from m5.m5_display import Display, WHITE, BLACK

display = Display()
display.fill(BLACK)
display.draw_text(4, 4, "Hello", WHITE, BLACK, scale=2)
print(display.WIDTH, display.HEIGHT)  # 135, 240
```

- `fill(color565)` — solid fill.
- `draw_text(x, y, text, color, bg, scale=1, spacing=2, clip=True)` /
  `draw_char(...)` — text in the built-in 8×8 font, which covers the **full
  printable ASCII range** (`0x20`–`0x7E`: all letters both cases, digits and
  punctuation).
- `draw_text_centered(y, text, color, bg, scale=1, spacing=2, clip=True)` —
  centers horizontally and returns the x it used.
- `text_width(text, scale=1, spacing=2)` — rendered width in pixels.
- `max_chars(scale=1, spacing=2)` — how many characters fit across the panel
  (13 at scale 1, 7 at scale 2).

### Clipping

`clip=True` (the default) trims text that runs off any edge, and skips
characters entirely off-panel. Without it, `_set_window()` addresses GRAM
outside the visible window — past the right edge that corrupts the neighbouring
column range, and far enough past it the coordinate overflows a byte and raises
`ValueError: bytes value out of range`. Callers don't need to budget characters
themselves.

### Missing glyphs

Any character the font lacks draws as a hollow box (`MISSING_GLYPH`), not a
blank. The font previously held a 31-glyph subset and drew anything else as a
space, so a string like `"ORANGE"` — which had none of its letters — rendered as
nothing at all and looked like a dead panel rather than a font gap.
- `set_scroll_region(top, height)` / `write_scroll_row(row, pixel_row)` /
  `scroll_to(row)` — hardware vertical scroll, for a strip-chart/oscilloscope
  style display that only has to redraw one new row per frame instead of the
  whole plot area (see `Grove_accelerometer.py` for an example).

Colors are plain RGB565 ints — `WHITE = 0xFFFF`, `BLACK = 0x0000` are the only
two exported; build others yourself (e.g. `0xF800` red, `0x07E0` green,
`0x001F` blue).
