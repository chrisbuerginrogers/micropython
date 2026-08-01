from time import sleep_ms
from m5.m5_display import Display, WHITE, BLACK
from m5 import m5_power
from m5.m5_battery import Battery
from m5.m5_buttons import Buttons

# Shows battery voltage/percent and which supplies currently have power
# present (USB / Grove-5V-out / battery - see m5_power.get_power_source()).
# Press BtnA to toggle charging on/off.

display = Display()
display.fill(BLACK)
display.draw_text(4, 4, "Battery", WHITE, BLACK, scale=2)
display.draw_text(4, 30, "BtnA = toggle charge", WHITE, BLACK)

battery = Battery()
buttons = Buttons()

charge_enabled = True
m5_power.set_charge_enable(charge_enabled)

SCALE = 2
Y0 = 70
LINE_HEIGHT = 8 * SCALE + 12
last_text = {}


def draw_line(y, key, text):
    if last_text.get(key) != text:
        display.draw_text(4, y, text, WHITE, BLACK, scale=SCALE)
        last_text[key] = text


while True:
    if buttons.a.is_pressed():
        charge_enabled = not charge_enabled
        m5_power.set_charge_enable(charge_enabled)
        buttons.a.wait_for_release()

    src = m5_power.get_power_source()
    present = []
    if src & m5_power.POWER_SOURCE_USB:
        present.append("USB")
    if src & m5_power.POWER_SOURCE_5VINOUT:
        present.append("5VIO")
    if src & m5_power.POWER_SOURCE_BATTERY:
        present.append("BAT")

    draw_line(Y0, "mv", "{}mV".format(battery.read_mv()))
    draw_line(Y0 + LINE_HEIGHT, "pct", "{}%".format(battery.read_percent()))
    draw_line(Y0 + 2 * LINE_HEIGHT, "src", "+".join(present) if present else "none")
    draw_line(Y0 + 3 * LINE_HEIGHT, "chg", "Charge: {}".format("ON" if charge_enabled else "OFF"))

    sleep_ms(200)
