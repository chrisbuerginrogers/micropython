from time import sleep
from m5.m5_display import Display, BLACK

RED = 0xF800

display = Display()

while True:
    display.fill(RED)
    sleep(0.5)
    display.fill(BLACK)
    sleep(0.5)
