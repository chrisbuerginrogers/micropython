from time import sleep_ms
from m5.m5_display import Display, WHITE, BLACK
from m5.m5_accel import MMA7660
from m5.m5_battery import Battery

RED = 0xF800
GREEN = 0x07E0
BLUE = 0x001F

display = Display()
display.fill(BLACK)

accel = MMA7660()
battery = Battery()

# --- Layout: battery corner, colored X/Y/Z readout, scope trace below --
BATT_Y0 = 2
TEXT_SCALE = 2
TEXT_Y0 = BATT_Y0 + 8 + 8
TEXT_LINE_HEIGHT = 8 * TEXT_SCALE + 4
PLOT_TOP = TEXT_Y0 + 3 * TEXT_LINE_HEIGHT + 8
PLOT_HEIGHT = display.HEIGHT - PLOT_TOP
display.set_scroll_region(PLOT_TOP, PLOT_HEIGHT)

# Each row is one sample in time; a pixel's horizontal position encodes
# that axis's g value, from -G_RANGE (left edge) to +G_RANGE (right edge).
G_RANGE = 1.5  # this sensor's full-scale range
CENTER_X = display.WIDTH // 2
PX_PER_G = (display.WIDTH - 1) / (2 * G_RANGE)

BLANK_ROW = bytes(display.WIDTH * 2)  # all-black row, used to clear the band

# Start the scroll band on a clean black canvas rather than whatever
# garbage happens to be sitting in GRAM at power-up.
for _row in range(PLOT_HEIGHT):
    display.write_scroll_row(_row, BLANK_ROW)
display.scroll_to(0)


def g_to_x(g):
    x = int(CENTER_X + g * PX_PER_G)
    if x < 0:
        return 0
    if x >= display.WIDTH:
        return display.WIDTH - 1
    return x


def make_row(x_g, y_g, z_g):
    row = bytearray(BLANK_ROW)
    for g, color in ((x_g, RED), (y_g, GREEN), (z_g, BLUE)):
        idx = g_to_x(g) * 2
        row[idx] = color >> 8
        row[idx + 1] = color & 0xFF
    return row


last_x_text = None
last_y_text = None
last_z_text = None
last_batt_text = None
write_row = 0

while True:
    x_g, y_g, z_g = accel.read_g()
    print("accel  x={:.2f}g  y={:.2f}g  z={:.2f}g".format(x_g, y_g, z_g))

    batt_text = "{}%".format(battery.read_percent())
    if batt_text != last_batt_text:
        bx = display.WIDTH - display.text_width(batt_text) - 2
        display.draw_text(bx, BATT_Y0, batt_text, WHITE, BLACK)
        last_batt_text = batt_text

    x_text = "{: .2f}g".format(x_g)
    y_text = "{: .2f}g".format(y_g)
    z_text = "{: .2f}g".format(z_g)

    if x_text != last_x_text:
        x = (display.WIDTH - display.text_width(x_text, TEXT_SCALE)) // 2
        display.draw_text(x, TEXT_Y0, x_text, RED, BLACK, scale=TEXT_SCALE)
        last_x_text = x_text

    if y_text != last_y_text:
        x = (display.WIDTH - display.text_width(y_text, TEXT_SCALE)) // 2
        display.draw_text(x, TEXT_Y0 + TEXT_LINE_HEIGHT, y_text, GREEN, BLACK, scale=TEXT_SCALE)
        last_y_text = y_text

    if z_text != last_z_text:
        x = (display.WIDTH - display.text_width(z_text, TEXT_SCALE)) // 2
        display.draw_text(x, TEXT_Y0 + 2 * TEXT_LINE_HEIGHT, z_text, BLUE, BLACK, scale=TEXT_SCALE)
        last_z_text = z_text

    # Newest sample enters at the top of the band and ages downward; the
    # row we overwrite each frame is the oldest one, about to scroll off.
    display.write_scroll_row(write_row, make_row(x_g, y_g, z_g))
    display.scroll_to(write_row)
    write_row = (write_row + 1) % PLOT_HEIGHT

    sleep_ms(30)
