'''
LEGOVisit browser control page -- talks to LEGO Education hardware straight
from Chrome over Web Bluetooth, via the legoeducation library running in
Pyodide.

Modeled on LEGO Education's own Pyodide Web IDE demo
(edanahy.github.io/pythonbetademos/betasite/) -- same legoeducation /
pyodide / Web Bluetooth foundation, cut down to a fixed device panel instead
of a full code editor: one Connect button per device, live readouts, and a
"drive from controller" relay -- no code to write or run.

Device classes look and behave exactly like legoeducation always has
(le.Controller(), .connect(), .sensor.leftPercent, ...). What changes under
the hood in the browser is legoeducation/web_bluetooth.py, which talks to
navigator.bluetooth instead of bleak, and legoeducation/_platform.py, which
makes that async work look synchronous via Pyodide's stack-switching --
this needs cross-origin isolation, which mini-coi-fd.js (loaded from
index.html) provides via a service worker even on a plain static file
server. See that file's own comment for why a page reload is sometimes
needed the very first time it's served.

Connecting shows Chrome's native "Select a Bluetooth device" picker, which
only appears when triggered directly from a click -- so each Connect
button's handler calls .connect() as the first thing it does, the same
way the demo's device-panel "Connect" buttons do.

Every @when handler below is `async def`, even ones that never use await
themselves. Confirmed by testing in headless Chrome: a plain `def` handler
makes PyScript invoke it as an ordinary call, and any legoeducation call
inside it then fails with "Cannot stack switch because the Python
entrypoint was a synchronous function" -- stack-switching only works when
the JS-to-Python entry point itself was invoked "promising" style, which
PyScript only does for coroutine functions.

Booted successfully in headless Chrome (PyScript ready, legoeducation
imported, cross-origin isolated, all button handlers registered without
error) -- confirms the page loads correctly. The actual BLE connect/drive
flow has NOT been exercised against real hardware, since that needs a real
user click (Web Bluetooth's device picker refuses synthetic ones) and
physical bricks. Treat the first live click-through as the real test.
'''

import asyncio
from datetime import datetime

import legoeducation as le
from js import crossOriginIsolated, document
from pyscript import when

POLL_S = 0.1

# One instance per device, created once at load and reused across
# connect/disconnect cycles -- __init__ does not touch Bluetooth at all,
# only connect()/disconnect() do.
devices = {
    'controller': le.Controller(),
    'doublemotor': le.DoubleMotor(),
    'singlemotor': le.SingleMotor(),
    'colorsensor': le.ColorSensor(),
}

relay_active = False


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


@when('click', '#btn-connect-controller')
async def on_connect_controller(event):
    _connect('controller', 'Controller')
    _update_relay_button()


@when('click', '#btn-disconnect-controller')
async def on_disconnect_controller(event):
    global relay_active
    relay_active = False
    _disconnect('controller', 'Controller')
    _update_relay_button()


@when('click', '#btn-connect-doublemotor')
async def on_connect_doublemotor(event):
    _connect('doublemotor', 'Double Motor')
    _update_relay_button()


@when('click', '#btn-disconnect-doublemotor')
async def on_disconnect_doublemotor(event):
    global relay_active
    if devices['doublemotor'].connected:
        devices['doublemotor'].movement_stop()
    relay_active = False
    _disconnect('doublemotor', 'Double Motor')
    _update_relay_button()


@when('click', '#btn-connect-singlemotor')
async def on_connect_singlemotor(event):
    _connect('singlemotor', 'Single Motor')


@when('click', '#btn-disconnect-singlemotor')
async def on_disconnect_singlemotor(event):
    if devices['singlemotor'].connected:
        devices['singlemotor'].motor_stop()
    _disconnect('singlemotor', 'Single Motor')


@when('click', '#btn-connect-colorsensor')
async def on_connect_colorsensor(event):
    _connect('colorsensor', 'Color Sensor')


@when('click', '#btn-disconnect-colorsensor')
async def on_disconnect_colorsensor(event):
    _disconnect('colorsensor', 'Color Sensor')


# ── single motor manual controls ────────────────────────────────────────

@when('click', '#btn-sm-forward')
async def on_sm_forward(event):
    dev = devices['singlemotor']
    if dev.connected:
        dev.motor_run(speed=60)


@when('click', '#btn-sm-reverse')
async def on_sm_reverse(event):
    dev = devices['singlemotor']
    if dev.connected:
        dev.motor_run(speed=-60)


@when('click', '#btn-sm-stop')
async def on_sm_stop(event):
    dev = devices['singlemotor']
    if dev.connected:
        dev.motor_stop()


# ── controller-drives-motor relay ───────────────────────────────────────

def _update_relay_button():
    btn = _el('btn-relay-toggle')
    both = devices['controller'].connected and devices['doublemotor'].connected
    btn.disabled = not both
    btn.textContent = ('Stop driving from controller' if relay_active
                       else 'Drive from controller')
    btn.classList.toggle('btn-active', relay_active)


@when('click', '#btn-relay-toggle')
async def on_relay_toggle(event):
    global relay_active
    relay_active = not relay_active
    if not relay_active and devices['doublemotor'].connected:
        devices['doublemotor'].movement_stop()
    _update_relay_button()
    log('driving from controller: ' + ('on' if relay_active else 'off'), 'ok')


# ── one coordinator loop: live readouts, and the relay itself ──────────
#
# A single loop rather than one per device, so nothing here races another
# poll to touch the same device at the same time.

async def _main_loop():
    while True:
        ctrl = devices['controller']
        if ctrl.connected:
            left = ctrl.sensor.leftPercent
            right = ctrl.sensor.rightPercent
            _el('controller-left').textContent = '{:+.0f}%'.format(left)
            _el('controller-right').textContent = '{:+.0f}%'.format(right)
            if relay_active and devices['doublemotor'].connected:
                devices['doublemotor'].movement_move_tank(
                    speed_left=left, speed_right=right)
        else:
            _el('controller-left').textContent = '--'
            _el('controller-right').textContent = '--'

        cs = devices['colorsensor']
        if cs.connected:
            color = cs.sensor.color
            name = le.LEGO_COLOR_NAME_MAP.get(color, str(color))
            hexcolor = le.LEGO_COLOR_HEX_MAP.get(color, '#333')
            _el('colorsensor-name').textContent = name.replace('LEGO_COLOR_', '')
            _el('colorsensor-swatch').style.backgroundColor = hexcolor

        await asyncio.sleep(POLL_S)


# ── boot ─────────────────────────────────────────────────────────────────

def _report_isolation():
    if crossOriginIsolated:
        log('cross-origin isolated -- Bluetooth calls will work', 'ok')
    else:
        log('NOT cross-origin isolated -- reload the page once (the '
            'service worker that enables it needs a fresh load to take '
            'effect the very first time this is served)', 'warn')


_report_isolation()
for _key in devices:
    _set_status(_key, False)
_update_relay_button()
asyncio.ensure_future(_main_loop())
document.getElementById('site-header').classList.add('ready')
log('ready -- click Connect on a device to begin', 'ok')
