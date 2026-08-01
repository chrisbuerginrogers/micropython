from time import sleep_ms
from m5.m5_display import Display, WHITE, BLACK
from m5.m5_imu import IMU

RED = 0xF800
GREEN = 0x07E0
BLUE = 0x001F

# Shows every output the onboard BMI270 IMU provides: 3-axis
# acceleration (g), 3-axis gyroscope (degrees/sec), and die temperature.

display = Display()
display.fill(BLACK)

imu = IMU()

title = "IMU"
x = (display.WIDTH - display.text_width(title, scale=2)) // 2
display.draw_text(x, 4, title, WHITE, BLACK, scale=2)

ACCEL_LABEL_Y = 32
ACCEL_Y0 = 56
GYRO_LABEL_Y = 128
GYRO_Y0 = 152
TEMP_Y = 224
LINE_HEIGHT = 24

display.draw_text(4, ACCEL_LABEL_Y, "Accel (g)", WHITE, BLACK)
display.draw_text(4, GYRO_LABEL_Y, "Gyro (dps)", WHITE, BLACK)

last_text = {}


def draw_value(y, key, label, value, color, fmt):
    text = label + fmt.format(value)
    if last_text.get(key) != text:
        display.draw_text(4, y, text, color, BLACK)
        last_text[key] = text


while True:
    ax, ay, az = imu.accel()
    gx, gy, gz = imu.gyro()
    temp_c = imu.temperature()

    draw_value(ACCEL_Y0, "ax", "X: ", ax, RED, "{:+.3f}")
    draw_value(ACCEL_Y0 + LINE_HEIGHT, "ay", "Y: ", ay, GREEN, "{:+.3f}")
    draw_value(ACCEL_Y0 + 2 * LINE_HEIGHT, "az", "Z: ", az, BLUE, "{:+.3f}")

    draw_value(GYRO_Y0, "gx", "X: ", gx, RED, "{:+.1f}")
    draw_value(GYRO_Y0 + LINE_HEIGHT, "gy", "Y: ", gy, GREEN, "{:+.1f}")
    draw_value(GYRO_Y0 + 2 * LINE_HEIGHT, "gz", "Z: ", gz, BLUE, "{:+.1f}")

    draw_value(TEMP_Y, "temp", "Temp: ", temp_c, WHITE, "{:.1f}C")

    sleep_ms(100)
