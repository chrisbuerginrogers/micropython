from m5.m5_display import Display, WHITE, BLACK

display = Display()
display.fill(BLACK)

SCALE = 2
line1, line2 = "Hello", "World"
x1 = (display.WIDTH - display.text_width(line1, SCALE)) // 2
x2 = (display.WIDTH - display.text_width(line2, SCALE)) // 2
y1 = (display.HEIGHT - (8 * SCALE * 2 + 8)) // 2
y2 = y1 + 8 * SCALE + 8

display.draw_text(x1, y1, line1, WHITE, BLACK, scale=SCALE)
display.draw_text(x2, y2, line2, WHITE, BLACK, scale=SCALE)
