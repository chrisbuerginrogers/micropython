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
- `draw_text(x, y, text, color, bg, scale=1, spacing=2)` / `draw_char(...)` —
  text using the built-in 8×8 font (covers digits, `%`, `.`, `-`, and the
  letters used by this repo's example scripts — not a full ASCII set).
- `text_width(text, scale=1, spacing=2)` — for centering text.
- `set_scroll_region(top, height)` / `write_scroll_row(row, pixel_row)` /
  `scroll_to(row)` — hardware vertical scroll, for a strip-chart/oscilloscope
  style display that only has to redraw one new row per frame instead of the
  whole plot area (see `Grove_accelerometer.py` for an example).

Colors are plain RGB565 ints — `WHITE = 0xFFFF`, `BLACK = 0x0000` are the only
two exported; build others yourself (e.g. `0xF800` red, `0x07E0` green,
`0x001F` blue).
