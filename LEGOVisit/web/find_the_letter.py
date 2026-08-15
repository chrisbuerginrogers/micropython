'''
FindTheLetter -- drive the Double Motor across a shape while plotting the
Color Sensor's live raw-color trace, to tell shapes/letters apart by how
they reflect light as the sensor moves across them.

Standalone page: a Web Bluetooth GATT connection does not survive a page
navigation, so this reconnects to both devices independently of index.html
-- it just reuses the same vendored legoeducation/ package and
mini-coi-fd.js already sitting next to it in this folder.

The driving controls (direction picture, duration picture, run arrow) are
the same design as going_the_distance.py, copied in rather than shared,
matching how each of these pages is a small standalone script -- see that
file for the fuller comment on the popover/click-outside-closes wiring.
The plot's Run/Stop is its own separate control, deliberately not tied to
the drive button: start recording, then drive, so a moment of stillness
before the motor starts is part of the trace too.

Like every other page here, every @when handler is `async def`, even ones
that never use await themselves -- confirmed by testing in headless Chrome
while building index.html: a plain `def` handler makes PyScript invoke it
as an ordinary call, and any legoeducation call inside it then fails
stack-switching with "Cannot stack switch because the Python entrypoint was
a synchronous function".

The plot talks to Plotly (loaded from its CDN in this page's <head>) via
Pyodide's JS interop -- plain Python dicts/lists, handed to Plotly.react()
through pyodide.ffi.to_js(), which converts them (recursively, including
nested dicts like each trace's `line` style) into the JS objects/arrays
Plotly expects. Same to_js(..., dict_converter=Object.fromEntries) pattern
web_bluetooth.py already uses to build requestDevice() filters.

The RGB / Reflected Light switch doesn't change what's sampled -- every
tick records raw R/G/B *and* reflection regardless of which is on screen,
so flipping the switch mid-run just changes which trace set is drawn, with
nothing lost and no need to clear.
'''

import asyncio
import time
from datetime import datetime

import legoeducation as le
from js import Object, Plotly, document
from pyodide.ffi import to_js
from pyscript import when

DEFAULT_SPEED = 100     # 0..100 -- fallback if the speed box is empty/invalid
MIN_INTERVAL_MS = 20    # floor, so a typo like "0" can't spin the sample loop

devices = {
    'doublemotor': le.DoubleMotor(),
    'colorsensor': le.ColorSensor(),
}

direction = le.MOVEMENT_DIRECTION_FORWARD
duration_s = 1.0

plot_active = False
plot_mode = 'rgb'  # 'rgb' or 'reflection' -- which trace set is shown
plot_t = []
plot_red = []
plot_green = []
plot_blue = []
plot_reflection = []
plot_start_time = 0.0


# ── small DOM helpers ───────────────────────────────────────────────────

def _el(id):
    return document.getElementById(id)


def log(msg, level='info'):
    ts = datetime.now().strftime('%H:%M:%S')
    el = _el('log')
    el.innerHTML += '<div class="log-{}">[{}] {}</div>'.format(level, ts, msg)
    el.scrollTop = el.scrollHeight


def _set_status(key, connected):
    el = _el('{}-status'.format(key))
    el.textContent = 'connected' if connected else 'not connected'
    el.className = 'status ' + ('status-on' if connected else 'status-off')
    _el('btn-connect-{}'.format(key)).disabled = connected
    _el('btn-disconnect-{}'.format(key)).disabled = not connected
    _update_run_button()
    _update_plot_button()


# ── connect / disconnect ────────────────────────────────────────────────

def _connect(key, label):
    dev = devices[key]
    if dev.connected:
        return
    try:
        dev.connect()
    except Exception as exc:
        log('{}: connect failed -- {}'.format(label, exc), 'err')
        return
    if dev.connected:
        log('{} connected'.format(label), 'ok')
    else:
        log('{}: no device selected'.format(label), 'warn')
    _set_status(key, dev.connected)


def _disconnect(key, label):
    dev = devices[key]
    if not dev.connected:
        return
    try:
        dev.disconnect()
    except Exception as exc:
        log('{}: disconnect error -- {}'.format(label, exc), 'warn')
    _set_status(key, dev.connected)
    log('{} disconnected'.format(label), 'ok')


@when('click', '#btn-connect-doublemotor')
async def on_connect_doublemotor(event):
    _connect('doublemotor', 'Double Motor')


@when('click', '#btn-disconnect-doublemotor')
async def on_disconnect_doublemotor(event):
    _disconnect('doublemotor', 'Double Motor')


@when('click', '#btn-connect-colorsensor')
async def on_connect_colorsensor(event):
    _connect('colorsensor', 'Color Sensor')


@when('click', '#btn-disconnect-colorsensor')
async def on_disconnect_colorsensor(event):
    global plot_active
    if devices['colorsensor'].connected:
        plot_active = False
        _update_plot_button()
    _disconnect('colorsensor', 'Color Sensor')


# ── the motor picture: click to flip direction ──────────────────────────

def _update_direction_ui():
    forward = direction == le.MOVEMENT_DIRECTION_FORWARD
    # U+21BB clockwise / U+21BA anticlockwise open circle arrow -- a real
    # rotation direction, not just an animation direction.
    _el('motor-arrow').textContent = '↻' if forward else '↺'
    _el('direction-label').textContent = 'Forward' if forward else 'Backward'


@when('click', '#motor-picture')
async def on_toggle_direction(event):
    global direction
    direction = (le.MOVEMENT_DIRECTION_BACKWARD
                if direction == le.MOVEMENT_DIRECTION_FORWARD
                else le.MOVEMENT_DIRECTION_FORWARD)
    _update_direction_ui()


# ── the clock picture: click to open a duration picker ──────────────────

def _format_seconds(value):
    return '{:g}s'.format(value)


def _update_duration_label():
    _el('duration-label').textContent = _format_seconds(duration_s)


def _close_duration_popover():
    _el('duration-popover').classList.add('hidden')


@when('click', '#clock-picture')
async def on_open_duration(event):
    event.stopPropagation()
    _el('duration-popover').classList.toggle('hidden')


@when('click', '.chip')
async def on_pick_duration(event):
    global duration_s
    value = event.target.dataset.value
    custom_input = _el('custom-duration')
    if value == 'custom':
        custom_input.classList.remove('hidden')
        custom_input.focus()
        return
    duration_s = float(value)
    custom_input.classList.add('hidden')
    _update_duration_label()
    _close_duration_popover()


@when('keydown', '#custom-duration')
async def on_custom_duration_key(event):
    global duration_s
    if event.key != 'Enter':
        return
    raw = _el('custom-duration').value
    try:
        value = float(raw)
    except ValueError:
        log('"{}" is not a number'.format(raw), 'warn')
        return
    if value <= 0:
        log('duration must be positive', 'warn')
        return
    duration_s = value
    _update_duration_label()
    _close_duration_popover()


@when('click', 'body')
async def on_body_click(event):
    '''Close the duration popover on a click outside it or the clock.'''
    popover = _el('duration-popover')
    if popover.classList.contains('hidden'):
        return
    if popover.contains(event.target) or _el('clock-picture').contains(event.target):
        return
    _close_duration_popover()


# ── drive ────────────────────────────────────────────────────────────────

def _update_run_button():
    _el('btn-run').disabled = not devices['doublemotor'].connected


def _read_speed():
    '''Speed magnitude (0..100) from the speed box, clamped and defaulted
    on anything unusable -- direction is the separate motor-picture toggle,
    so this is a magnitude, not a signed value.'''
    raw = _el('speed-input').value
    try:
        speed = float(raw)
    except ValueError:
        log('"{}" is not a number -- using {:g}'.format(raw, DEFAULT_SPEED), 'warn')
        return DEFAULT_SPEED
    clamped = max(0.0, min(100.0, speed))
    if clamped != speed:
        log('speed clamped to {:g}'.format(clamped), 'warn')
    return clamped


@when('click', '#btn-run')
async def on_drive(event):
    doublemotor = devices['doublemotor']
    if not doublemotor.connected:
        log('connect the Double Motor first', 'warn')
        return
    btn = _el('btn-run')
    btn.disabled = True
    btn.classList.add('running')
    speed = _read_speed()
    time_ms = int(round(duration_s * 1000))
    dir_name = 'forward' if direction == le.MOVEMENT_DIRECTION_FORWARD else 'backward'
    log('driving {} for {} at {:g}% speed...'.format(
        dir_name, _format_seconds(duration_s), speed), 'ok')
    try:
        doublemotor.movement_move_for_time(time_ms, direction=direction, speed=speed)
        log('done driving', 'ok')
    except Exception as exc:
        log('drive failed -- {}'.format(exc), 'err')
    finally:
        btn.disabled = not doublemotor.connected
        btn.classList.remove('running')


# ── plot drawing ─────────────────────────────────────────────────────────

def _trace(name, color, y):
    return {'x': plot_t, 'y': y, 'type': 'scatter', 'mode': 'lines',
            'name': name, 'line': {'color': color}}


def _redraw_plot():
    if plot_mode == 'reflection':
        traces = [_trace('Reflection', '#5f6368', plot_reflection)]
        y_title = 'reflection (0-255)'
    else:
        traces = [
            _trace('Red', '#de1a21', plot_red),
            _trace('Green', '#61a836', plot_green),
            _trace('Blue', '#006cb8', plot_blue),
        ]
        y_title = 'raw value'
    layout = {
        'margin': {'t': 20, 'r': 10, 'l': 44, 'b': 34},
        'xaxis': {'title': 'seconds'},
        'yaxis': {'title': y_title},
        'showlegend': True,
    }
    Plotly.react('color-plot',
                to_js(traces, dict_converter=Object.fromEntries),
                to_js(layout, dict_converter=Object.fromEntries))


def _clear_plot():
    global plot_start_time
    plot_t.clear()
    plot_red.clear()
    plot_green.clear()
    plot_blue.clear()
    plot_reflection.clear()
    plot_start_time = time.time()
    _redraw_plot()


# ── RGB / reflected-light switch ────────────────────────────────────────
#
# Both are sampled every tick regardless of which is shown (see
# _plot_loop() below), so flipping this doesn't lose data or need a clear
# -- it just changes which trace set _redraw_plot() draws.

def _update_mode_switch():
    track = _el('mode-track')
    track.classList.toggle('on', plot_mode == 'reflection')
    _el('mode-label-rgb').classList.toggle('active', plot_mode == 'rgb')
    _el('mode-label-reflection').classList.toggle('active', plot_mode == 'reflection')


@when('click', '#mode-switch-row')
async def on_mode_toggle(event):
    global plot_mode
    plot_mode = 'reflection' if plot_mode == 'rgb' else 'rgb'
    _update_mode_switch()
    _redraw_plot()


# ── plot run / stop (independent of driving) ────────────────────────────

def _update_plot_button():
    btn = _el('btn-plot-run')
    btn.disabled = not devices['colorsensor'].connected
    btn.textContent = 'Stop' if plot_active else 'Run'
    btn.classList.toggle('btn-active', plot_active)


@when('click', '#btn-plot-run')
async def on_plot_toggle(event):
    global plot_active
    if plot_active:
        plot_active = False
        _update_plot_button()
        log('plot stopped', 'ok')
        return

    if not devices['colorsensor'].connected:
        log('connect the Color Sensor first', 'warn')
        return

    _clear_plot()
    plot_active = True
    _update_plot_button()
    log('plot started', 'ok')
    asyncio.ensure_future(_plot_loop())


async def _plot_loop():
    global plot_active
    while plot_active:
        cs = devices['colorsensor']
        if not cs.connected:
            log('Color Sensor disconnected -- plot stopped', 'warn')
            plot_active = False
            _update_plot_button()
            break

        plot_t.append(time.time() - plot_start_time)
        plot_red.append(cs.sensor.rawRed)
        plot_green.append(cs.sensor.rawGreen)
        plot_blue.append(cs.sensor.rawBlue)
        plot_reflection.append(cs.sensor.reflection)
        _redraw_plot()

        try:
            interval_ms = float(_el('sample-interval').value)
        except ValueError:
            interval_ms = 200.0
        await asyncio.sleep(max(interval_ms, MIN_INTERVAL_MS) / 1000.0)


# ── boot ─────────────────────────────────────────────────────────────────

for _key in devices:
    _set_status(_key, False)
_update_direction_ui()
_update_duration_label()
_update_mode_switch()
_redraw_plot()
document.getElementById('site-header').classList.add('ready')
log('ready -- connect both devices, then Run the plot and drive', 'ok')
