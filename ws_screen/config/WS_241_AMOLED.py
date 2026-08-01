from machine import Pin, I2C, SPI, SDCard, ADC
import amoled   # Screen driver
import tca9554  # Extended GPIO

TFT_CS  = Pin(9,Pin.OUT)   # CHIP SELECT
TFT_SCK = Pin(10,Pin.OUT)   # SPICLK_P
TFT_MOSI = None
TFT_MISO = None
TFT_RST = Pin(21,Pin.OUT)   # TFT RESET
TFT_D0  = Pin(11,Pin.OUT)   # D0 QSPI
TFT_D1  = Pin(12,Pin.OUT)   # D1 QSPI
TFT_D2  = Pin(13,Pin.OUT)   # D2 QSPI & SPICLK_N
TFT_D3  = Pin(14,Pin.OUT)   # D3 QSPI

TFT_TS_RST = Pin(3, Pin.OUT) # TS RESET
I2C0_SCL = Pin(48)  # TOUCH I2C SCL 
I2C0_SDA = Pin(47)  # TOUCH I2C SCA

TFT_WIDTH = 600
TFT_HEIGHT = 450
I2C_FREQ = 400_000
I2C_TIMEOUT = 200_000
SPI_PORT = 2
SPI_BAUD = 80_000_000
SPI_POLAR = False
SPI_PHASE = False


i2c = I2C(0, scl=I2C0_SCL, sda=I2C0_SDA, freq=I2C_FREQ, timeout=I2C_TIMEOUT)
TFT_CDE = tca9554.TCA9554(i2c, pin=1, io=0) #Specific EXI01 AMOLED_EN : Output
TFT_TE = tca9554.TCA9554(i2c, pin=0, io=1) #Specific EXI00 AMOLED_TEARING : Input
spi = SPI(SPI_PORT, baudrate = SPI_BAUD, sck=TFT_SCK, mosi=TFT_MOSI, miso=TFT_MISO, polarity=SPI_POLAR, phase=SPI_PHASE)
panel = amoled.QSPIPanel(spi=spi, data=(TFT_D0, TFT_D1, TFT_D2, TFT_D3),
            dc=TFT_D1, cs=TFT_CS, pclk=SPI_BAUD, width=TFT_HEIGHT, height=TFT_WIDTH)
display = amoled.AMOLED(panel, type=1, reset=TFT_RST, bpp=16, auto_refresh= not BUF)
display.reset()
display.init()
display.brightness(0)
TFT_CDE.value(1)
BAT_ON.value(1)