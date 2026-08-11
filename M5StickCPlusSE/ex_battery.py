"""Battery/VBUS voltage and charge/discharge current, read from the AXP192."""

from m5 import m5_display, m5_power
import time

NAME = "Battery"


def run(display, should_stop):
    while not should_stop():
        batt_mv = m5_power.read_battery_mv()
        vbus_mv = m5_power.read_vbus_mv()
        chg_ma = m5_power.read_battery_charge_ma()
        dis_ma = m5_power.read_battery_discharge_ma()

        display.fill(m5_display.BLACK)
        display.draw_text(4, 30, 'BATT', m5_display.WHITE, m5_display.BLACK, scale=2)
        display.draw_text(4, 55, '{:.0f} mV'.format(batt_mv), m5_display.WHITE, m5_display.BLACK, scale=2)
        display.draw_text(4, 95, 'VBUS', m5_display.WHITE, m5_display.BLACK, scale=2)
        display.draw_text(4, 120, '{:.0f} mV'.format(vbus_mv), m5_display.WHITE, m5_display.BLACK, scale=2)
        display.draw_text(4, 160, 'chg {:.0f} mA'.format(chg_ma), m5_display.WHITE, m5_display.BLACK)
        display.draw_text(4, 175, 'dis {:.0f} mA'.format(dis_ma), m5_display.WHITE, m5_display.BLACK)
        time.sleep_ms(400)
