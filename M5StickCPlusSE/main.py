"""Menu: Button B (side) steps through the examples, Button A (front)
starts/stops whichever one is selected.
"""

from machine import Pin
import time

from m5 import m5_display, m5_power
import ex_buttons, ex_battery, ex_buzzer, ex_rtc, ex_status_led, ex_ir, ex_grove

EXAMPLES = [ex_buttons, ex_battery, ex_buzzer, ex_rtc, ex_status_led, ex_ir, ex_grove]


def pressed(pin):
    return pin.value() == 0


def draw_title(display, name, y0):
    """Centered, scale=2 -- split on the first space so two-word names
    (e.g. "Status LED") get a line each instead of running off this
    135px-wide panel (max 7 chars/line at this scale)."""
    first, _, second = name.partition(' ')
    display.draw_text_centered(y0, first, m5_display.WHITE, m5_display.BLACK, scale=2)
    if second:
        display.draw_text_centered(y0 + 24, second, m5_display.WHITE, m5_display.BLACK, scale=2)


def main():
    m5_power.init()
    display = m5_display.Display()
    btn_a = Pin(37, Pin.IN)
    btn_b = Pin(39, Pin.IN)

    index = 0

    def draw_menu():
        display.fill(m5_display.BLACK)
        draw_title(display, EXAMPLES[index].NAME, 80)
        display.draw_text_centered(140, 'A=run  B=next', m5_display.WHITE, m5_display.BLACK)

    draw_menu()
    last_a, last_b = pressed(btn_a), pressed(btn_b)

    while True:
        a, b = pressed(btn_a), pressed(btn_b)

        if b and not last_b:
            index = (index + 1) % len(EXAMPLES)
            draw_menu()

        if a and not last_a:
            example = EXAMPLES[index]
            display.fill(m5_display.BLACK)
            draw_title(display, example.NAME, 4)
            display.draw_text_centered(220, 'A=stop', m5_display.WHITE, m5_display.BLACK)

            while pressed(btn_a):  # let go of the press that started this run
                time.sleep_ms(10)

            stop_flag = [False]

            def should_stop():
                if pressed(btn_a):
                    stop_flag[0] = True
                return stop_flag[0]

            try:
                example.run(display, should_stop)
            except Exception as exc:
                display.fill(m5_display.BLACK)
                display.draw_text(4, 100, 'ERROR', 0xF800, m5_display.BLACK, scale=2)
                display.draw_text(4, 130, str(exc)[:20], 0xF800, m5_display.BLACK)
                time.sleep_ms(1500)

            while pressed(btn_a):  # let go of the press that stopped it
                time.sleep_ms(10)
            last_a = False
            draw_menu()
            continue

        last_a, last_b = a, b
        time.sleep_ms(20)


if __name__ == '__main__':
    main()
