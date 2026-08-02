from m5.m5_display import Display, WHITE, BLACK
from m5.m5_imu import IMU
from m5.m5_audio import Speaker
from m5.m5_buttons import Buttons

# Tilt the StickS3 forward/back (Y axis) to raise/lower the pitch of a
# tone. Press BtnA to stop.

MIN_FREQ = 200
MAX_FREQ = 2000
MIN_G = -2.0
MAX_G = 2.0
TONE_MS = 60

display = Display()
display.fill(BLACK)
display.draw_text(4, 4, "Tilt = pitch", WHITE, BLACK)
display.draw_text(4, 20, "BtnA = stop", WHITE, BLACK)

imu = IMU()
buttons = Buttons()

try:
    speaker = Speaker(volume=60)
except OSError as e:
    # ES8311 codec doesn't respond on I2C on some StickS3 units - see
    # m5_audio.py's docstring. Keep the tilt readout running silently
    # rather than crash.
    print("Speaker init failed ({}) - running without audio".format(e))
    speaker = None
    display.draw_text(4, 36, "(no audio)", WHITE, BLACK)

SCALE = 2
last_text = None

while not buttons.a.is_pressed():
    _, y_g, _ = imu.accel()

    clamped = max(MIN_G, min(MAX_G, y_g))
    t = (clamped - MIN_G) / (MAX_G - MIN_G)
    freq = int(MIN_FREQ + t * (MAX_FREQ - MIN_FREQ))

    text = "{:+.2f}g {}Hz".format(y_g, freq)
    if text != last_text:
        x = (display.WIDTH - display.text_width(text, SCALE)) // 2
        display.draw_text(x, 100, text, WHITE, BLACK, scale=SCALE)
        last_text = text

    if speaker:
        speaker.tone(freq, TONE_MS)

if speaker:
    speaker.deinit()
display.fill(BLACK)
display.draw_text(20, 110, "Stopped", WHITE, BLACK, scale=2)
