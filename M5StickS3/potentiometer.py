from time import sleep_ms
from m5.m5_display import Display, WHITE, BLACK
from m5.m5_potentiometer import Potentiometer
from m5.m5_battery import Battery

display = Display()
display.fill(BLACK)

pot = Potentiometer()
battery = Battery()

SCALE = 3
last_percent_text = None
last_volt_text = None
last_batt_text = None

while True:
    raw = pot.read_raw()  # 0-65535
    volts = raw * 3.3 / 65535
    percent = raw * 100 // 65535
    print(percent, volts)

    batt_text = "{}%".format(battery.read_percent())
    if batt_text != last_batt_text:
        bx = display.WIDTH - display.text_width(batt_text) - 2
        display.draw_text(bx, 2, batt_text, WHITE, BLACK)
        last_batt_text = batt_text

    whole = int(volts)
    frac = int(round((volts - whole) * 100))
    volt_text = "{}.{:02d}V".format(whole, frac)
    percent_text = "{:3d}%".format(percent)

    if volt_text != last_volt_text:
        x = (display.WIDTH - display.text_width(volt_text, SCALE)) // 2
        display.draw_text(x, 90, volt_text, WHITE, BLACK, scale=SCALE)
        last_volt_text = volt_text

    if percent_text != last_percent_text:
        x = (display.WIDTH - display.text_width(percent_text, SCALE)) // 2
        display.draw_text(x, 90 + 8 * SCALE + 12, percent_text, WHITE, BLACK, scale=SCALE)
        last_percent_text = percent_text

    sleep_ms(150)
