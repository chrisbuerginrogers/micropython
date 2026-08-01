from machine import Pin, SoftI2C
import time
from max17048 import MAX17048
from lis2dw12 import LIS2DW12
BUZZERPIN = 19
#int1_pin = machine.Pin(1, machine.Pin.IN)
#motor    = machine.Pin(MOTOR_PIN, machine.Pin.OUT, value=0)


REDLED = 2
redled = Pin(REDLED, Pin.OUT)
redled.on()
I2C_SDA = 22
I2C_SCL = 23


#led = Pin(2, Pin.IN)
#led.value()
i2c      =  SoftI2C(sda=Pin(I2C_SDA), scl=Pin(I2C_SCL))
print(i2c.scan())
import brightness
from neopixel import NeoPixel
btn = Pin(0, Pin.IN)
np = NeoPixel(Pin(20), 60)
from opt3002 import OPT3002
light = OPT3002(i2c)
light.init()

m, lux = brightness.calibrate(light)
if lux is not None:
    print("  Light: %.0f lux -> brightness x%.2f" % (lux, m))
else:
    print("  Light: sensor reads failed, brightness x%.2f" % m)

import buzzer

buz = buzzer.Buzzer(BUZZERPIN)
buz.beep()
accel = LIS2DW12(i2c)
accel.init()


MOTOR = 21

motor = Pin(MOTOR, Pin.OUT)


batt = None
last_soc = 100  # default if no battery gauge
try:
    batt = MAX17048(i2c)
    v, s = batt.read_all()
    last_soc = max(0, min(100, int(s)))
    print("  Battery: %.2fV, %.1f%%" % (v, s))
except:
    print("no battery")

while True:
    print(accel.read())
    if (btn.value() == 0):
        #motor.on()
        #time.sleep(2)
        #motor.off()

        for i in range(25):
            np[i] = (10,10,0)
            np.write()
    else:

        #motor.on()
        #time.sleep(2)
        #motor.off()
        for i in range(25):
            np[i] = (0,0,10)
            np.write()
    time.sleep(0.4)
        
