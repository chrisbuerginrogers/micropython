"""AtomS3: press the front button to step the RGB LED through colors."""

import neopixel, machine, time

led = neopixel.NeoPixel(machine.Pin(35), 1)
button = machine.Pin(41, machine.Pin.IN, machine.Pin.PULL_UP)

COLORS = [(40, 0, 0), (0, 40, 0), (0, 0, 40), (40, 40, 0), (0, 40, 40), (40, 0, 40)]

def show(color):
    led[0] = color
    led.write()

index = 0
show(COLORS[index])
pressed = False

while True:
    if button.value() == 0 and not pressed:
        pressed = True
        index = (index + 1) % len(COLORS)
        show(COLORS[index])
    elif button.value() == 1:
        pressed = False
    time.sleep_ms(20)
