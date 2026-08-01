from machine import Pin, I2C, I2S, SPI, SDCard, ADC
import amoled   # Screen driver
import tca9554  # Extended GPIO


TFT_CS  = Pin(12,Pin.OUT)   # LCD_CS
TFT_SCK = Pin(11,Pin.OUT)   # QSPI_SCL
TFT_MOSI = None
TFT_MISO = None
TFT_RST = Pin(13,Pin.OUT)  # WS datasheet is wrong (annonced to be LCD_TE)
TFT_D0  = Pin(4,Pin.OUT)   # QSPI_SIO0
TFT_D1  = Pin(5,Pin.OUT)   # QSPI_SI1
TFT_D2  = Pin(6,Pin.OUT)   # QSPI_SI2
TFT_D3  = Pin(7,Pin.OUT)   # QSPI_SI3
TFT_TS_IN = Pin(21, Pin.IN, Pin.PULL_UP)

I2C0_SCL = Pin(14)  # TP_SCL
I2C0_SDA = Pin(15)  # TP_SDA

SD_SCK = Pin(2, Pin.OUT)   # SCK
SD_MOSI = Pin(1, Pin.OUT)  # MOSI
SD_MISO = Pin(3, Pin.OUT)  # MISO

TFT_WIDTH = 368
TFT_HEIGHT = 448
I2C_FREQ = 400_000
SPI_PORT = 2
SPI_BAUD = 80_000_000
SPI_POLAR = False
SPI_PHASE = False

i2c = I2C(0, scl=I2C0_SCL, sda=I2C0_SDA, freq=I2C_FREQ, timeout=200000)

TFT_TE = tca9554.TCA9554(i2c, pin=0, io=1) # WS datasheet is wrong (annonced to be LCD_RESET)
TFT_CDE = tca9554.TCA9554(i2c, pin=1, io=0) #Specific EXI01 AMOLED_EN : Output
TFT_TS_RST = tca9554.TCA9554(i2c, pin=2, io=0) # TFT RST is EXIO_2

spi = SPI(SPI_PORT, baudrate = SPI_BAUD, sck=TFT_SCK, mosi=TFT_MOSI, miso=TFT_MISO, polarity=SPI_POLAR, phase=SPI_PHASE)
panel = amoled.QSPIPanel(spi=spi, data=(TFT_D0, TFT_D1, TFT_D2, TFT_D3),
            dc=TFT_D1, cs=TFT_CS, pclk=80_000_000, width=TFT_WIDTH, height=TFT_HEIGHT)
display = amoled.AMOLED(panel, type=2, reset=TFT_RST, bpp=16)
display.reset()
display.init()
display.brightness(0)
TFT_CDE.value(1)