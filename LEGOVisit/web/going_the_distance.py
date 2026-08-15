'''
GoingTheDistance -- pick a direction, pick a duration, run the Double Motor.

Standalone page: a Web Bluetooth GATT connection does not survive a page
navigation, so this reconnects to the Double Motor independently of
index.html -- it just reuses the same vendored legoeducation/ package and
mini-coi-fd.js already sitting next to it in this folder.

Like main.py, every @when handler here is `async def`, even ones that never
use await themselves. Confirmed by testing in headless Chrome while building
index.html: a plain `def` handler makes PyScript invoke it as an ordinary
call, and any legoeducation call inside it then fails stack-switching with
"Cannot stack switch because the Python entrypoint was a synchronous
function" -- stack-switching only works when the JS-to-Python entry point
itself was invoked "promising" style, which PyScript only does for
coroutine functions.
'''

import asyncio
from datetime import datetime

import legoeducation as le
from js import document
from pyscript import when

DEFAULT_SPEED = 60  # -100..100 -- how hard the motor runs while going the distance
PRESET_SECONDS = (1, 2, 3, 4, 5)

doublemotor = le.DoubleMotor()

direction = le.MOVEMENT_DIRECTION_FORWARD
duration_s = 1.0


# ── small DOM helpers ───────────────────────────────────────────────────

def _el(id):
    return document.getElementById(id)


def log(msg, level='info'):
    ts = datetime.now().strftime('%H:%M:%S')
    el = _el('log')
    el.innerHTML += '<div class="log-{}">[{}] {}</div>'.format(level, ts, msg)
    el.scrollTop = el.scrollHeight


def _set_status(connected):
    el = _el('doublemotor-status')
    el.textContent = 'connected' if connected else 'not connected'
    el.className = 'status ' + ('status-on' if connected else 'status-off')
    _el('btn-connect').disabled = connected
    _el('btn-disconnect').disabled = not connected
    _el('btn-run').disabled = not connected


# ── connect / disconnect ────────────────────────────────────────────────

@when('click', '#btn-connect')
async def on_connect(event):
    if doublemotor.connected:
        return
    try:
        doublemotor.connect()
    except Exception as exc:
        log('connect failed -- {}'.format(exc), 'err')
        return
    if doublemotor.connected:
        log('Double Motor connected', 'ok')
    else:
        log('no device selected', 'warn')
    _set_status(doublemotor.connected)


@when('click', '#btn-disconnect')
async def on_disconnect(event):
    if not doublemotor.connected:
        return
    try:
        doublemotor.disconnect()
    except Exception as exc:
        log('disconnect error -- {}'.format(exc), 'warn')
    _set_status(doublemotor.connected)
    log('Double Motor disconnected', 'ok')


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


def _close_popover():
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
    _close_popover()


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
    _close_popover()


@when('click', 'body')
async def on_body_click(event):
    '''Close the duration popover on a click outside it or the clock.'''
    popover = _el('duration-popover')
    if popover.classList.contains('hidden'):
        return
    if popover.contains(event.target) or _el('clock-picture').contains(event.target):
        return
    _close_popover()


# ── run ──────────────────────────────────────────────────────────────────

@when('click', '#btn-run')
async def on_run(event):
    if not doublemotor.connected:
        log('connect the Double Motor first', 'warn')
        return
    btn = _el('btn-run')
    btn.disabled = True
    btn.classList.add('running')
    time_ms = int(round(duration_s * 1000))
    dir_name = 'forward' if direction == le.MOVEMENT_DIRECTION_FORWARD else 'backward'
    log('running {} for {}...'.format(dir_name, _format_seconds(duration_s)), 'ok')
    try:
        doublemotor.movement_move_for_time(time_ms, direction=direction, speed=DEFAULT_SPEED)
        log('done', 'ok')
    except Exception as exc:
        log('run failed -- {}'.format(exc), 'err')
    finally:
        btn.disabled = not doublemotor.connected
        btn.classList.remove('running')


# ── boot ─────────────────────────────────────────────────────────────────

_set_status(False)
_update_direction_ui()
_update_duration_label()
document.getElementById('site-header').classList.add('ready')
log('ready -- connect the Double Motor, pick direction + duration, then run', 'ok')
