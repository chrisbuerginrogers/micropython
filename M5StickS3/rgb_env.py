from machine import Pin, I2C
from time import sleep_ms
from m5.m5_display import Display, WHITE, BLACK
from m5.m5_EnvSensor import BMP280, GROVE_SDA_PIN, GROVE_SCL_PIN
from m5.m5_RGB import Sk6812
from m5.m5_battery import Battery

# NOTE: the potentiometer from potentiometer.py can't share this hub too.
# Its wiper needs a clean analog voltage on G10, but this hub has pull-up
# resistors on G9/G10 (needed for I2C) that swamp that signal - confirmed
# live: the pot reads pinned to one extreme through the hub, but tracks
# the knob correctly when plugged directly into the StickS3's own Grove
# port with no hub in between. With only one physical Grove port on this
# board, it's the hub (this script) or the pot (potentiometer.py), not
# both at once.

NUM_LEDS = 3

display = Display()
display.fill(BLACK)

bmp280 = BMP280()
led = Sk6812(NUM_LEDS)
battery = Battery()
sleep_ms(50)  # let the first normal-mode conversion finish before reading

SCALE = 2
LINE_HEIGHT = 8 * SCALE + 16
Y0 = 70
last_temp_text = None
last_press_text = None
last_alt_text = None
last_batt_text = None

# Simple liveness demo: cycle the LED so you can visually confirm it's
# responding. Swap in your own color logic (e.g. map hue to temperature)
# once you've confirmed the wiring works.
COLORS = [
    (40, 0, 0),  # red
    (0, 40, 0),  # green
    (0, 0, 40),  # blue
    (40, 40, 40),  # white
    (0, 0, 0),  # off
]

i = 0
while True:
    # BMP280 needs G9 (SDA) and G10 (SCL) as an I2C bus, but the LED's
    # data line is also on G9 - the hub duplicates the same two signal
    # wires to every port, so only one use can own G9 at a time. Re-claim
    # I2C here before every read; the LED write below re-claims G9 after.
    bmp280.i2c = I2C(0, scl=Pin(GROVE_SCL_PIN), sda=Pin(GROVE_SDA_PIN), freq=400000)
    temp_c, pressure_pa = bmp280.read()
    alt_m = BMP280.altitude(pressure_pa)
    pressure_hpa = pressure_pa / 100.0

    led.fill(COLORS[i % len(COLORS)])

    temp_text = "{:.1f}C".format(temp_c)
    press_text = "{:.0f}hPa".format(pressure_hpa)
    alt_text = "{:.0f}m".format(alt_m)

    print("BMP280  temp={}  pressure={:.1f}Pa  altitude~{:.1f}m".format(
        temp_text, pressure_pa, alt_m))

    batt_text = "{}%".format(battery.read_percent())
    if batt_text != last_batt_text:
        bx = display.WIDTH - display.text_width(batt_text) - 2
        display.draw_text(bx, 2, batt_text, WHITE, BLACK)
        last_batt_text = batt_text

    if temp_text != last_temp_text:
        x = (display.WIDTH - display.text_width(temp_text, SCALE)) // 2
        display.draw_text(x, Y0, temp_text, WHITE, BLACK, scale=SCALE)
        last_temp_text = temp_text

    if press_text != last_press_text:
        x = (display.WIDTH - display.text_width(press_text, SCALE)) // 2
        display.draw_text(x, Y0 + LINE_HEIGHT, press_text, WHITE, BLACK, scale=SCALE)
        last_press_text = press_text

    if alt_text != last_alt_text:
        x = (display.WIDTH - display.text_width(alt_text, SCALE)) // 2
        display.draw_text(x, Y0 + 2 * LINE_HEIGHT, alt_text, WHITE, BLACK, scale=SCALE)
        last_alt_text = alt_text

    i += 1
    sleep_ms(1000)
