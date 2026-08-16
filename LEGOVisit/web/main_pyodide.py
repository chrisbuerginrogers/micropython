'''
PythonIDE -- a small in-browser Python editor for LEGO Education hardware:
write code, connect devices from a panel, Run it, Stop it if it runs long.

Standalone page, same foundation as the other pages here (legoeducation +
Pyodide + Web Bluetooth, cross-origin isolation from mini-coi-fd.js). This
one adds four things none of the others needed:

1. A real code editor (CodeMirror 5, loaded from its own CDN -- a separate,
   MIT-licensed open-source project, not LEGO's).
2. Running arbitrary user code, not just fixed device calls. exec() inside
   an `async def` handler works the same way every other button here does
   (see main.py's docstring for why it has to be async) -- the exec'd
   statements run in the same coroutine frame, so blocking-looking
   legoeducation calls inside the user's code still stack-switch correctly.
3. A Stop button that can actually interrupt a running script. This uses
   two mechanisms together, confirmed necessary by testing in headless
   Chrome: Pyodide's own interrupt-buffer API
   (pyodide_js.setInterruptBuffer) catches CPU-bound loops, but on its own
   it can land at an inconvenient moment -- observed landing inside an
   unrelated garbage-collection callback once, where Python silently
   swallows exceptions rather than letting them propagate, so the
   KeyboardInterrupt never reached the running script at all. The second
   mechanism, a plain stop flag that a swapped-in time.sleep() checks
   every 20ms, is what actually catches the common case: nearly every demo
   script here sleeps in a loop, and that flag-checking sleep responds to
   Stop immediately and reliably regardless of where the low-level
   interrupt happens to land.
4. A "More Demos" picker that fetches one of Ethan Danahy's own demo
   scripts (dataviewer.py, posedetection.py, etc. -- shared with us
   directly for this purpose) from his GitHub repo and drops it straight
   into the editor. Those scripts are NOT plain snippets meant for exec()
   in an arbitrary namespace -- per the page-contract his own repo
   documents (template/instructions.md in edanahy/pythonbetademos), they
   expect to run alongside a host module literally named "main_pyodide"
   (PyScript names a `<script type="py" src="...">` module after its
   filename, hence this file's name) exposing two module-level names,
   `_panel_devices` (dict[panel_id -> connected device instance]) and `le`
   (the legoeducation module), which they reach via
   `sys.modules['main_pyodide']` -- and three DOM anchors: `#device-panel`
   (an empty element his own layout code inserts its UI as a sibling
   after), `#device-rows` (scanned for `.device-row` elements, each
   needing a `.status-dot`, a `<select>`, and a text `<input>` -- see the
   hidden select/input in _render_device_list below, kept only for that
   contract, not shown to us), and `#log` (a panel his own Logger class
   writes timestamped divs into, same shape as ours). All of this is this
   file's own device panel and log panel, just under the names his scripts
   look for, plus the two extra module attributes and the empty anchor
   div -- exec() runs in the same interpreter either way, so none of this
   needed a different execution mechanism, just matching names.

The device panel is a free-form list, not one fixed slot per type -- add as
many Controllers, Double Motors, Single Motors or Color Sensors as you
want, each under whatever variable name you give it, and that's the name
it's injected into the run namespace under. Rows are added to the DOM
after the page has already loaded, so @when's normal decoration -- which
only binds to elements present at that moment -- can't wire their
Connect/Disconnect/Remove buttons directly. Event delegation handles that
instead: one listener on the (always-present) #device-rows container,
which on each click walks up from whatever was actually clicked to find
the button and its row, and dispatches from there. That's why this file
has both a #btn-add-device handler AND a #device-rows handler -- adding a
row and acting on an existing one are different concerns.
'''

import asyncio
import io
import re
import sys
import time as _real_time
import traceback
from datetime import datetime

import legoeducation as le
from js import Int32Array, SharedArrayBuffer, crossOriginIsolated, document
from pyscript import when
from pyodide.http import pyfetch

try:
    import pyodide_js
except ImportError:
    pyodide_js = None

DEVICE_CLASSES = {
    'Controller': le.Controller,
    'DoubleMotor': le.DoubleMotor,
    'SingleMotor': le.SingleMotor,
    'ColorSensor': le.ColorSensor,
}
DEVICE_LABELS = {
    'Controller': 'Controller',
    'DoubleMotor': 'Double Motor',
    'SingleMotor': 'Single Motor',
    'ColorSensor': 'Color Sensor',
}
DEVICE_VARNAME_PREFIX = {
    'Controller': 'controller',
    'DoubleMotor': 'doublemotor',
    'SingleMotor': 'singlemotor',
    'ColorSensor': 'colorsensor',
}
# Same icon glyphs used on the other pages' fixed device cards, kept here
# as plain SVG markup so a dynamically-built row can carry one too.
DEVICE_ICONS = {
    'Controller': ('<rect x="2" y="8" width="20" height="10" rx="4"/>'
                   '<circle cx="8" cy="13" r="2"/><circle cx="16" cy="13" r="2"/>'),
    'DoubleMotor': ('<circle cx="5" cy="17" r="3"/><circle cx="19" cy="17" r="3"/>'
                    '<line x1="8" y1="17" x2="16" y2="17"/>'
                    '<rect x="7" y="6" width="10" height="7" rx="1.5"/>'
                    '<line x1="12" y1="13" x2="12" y2="17"/>'),
    'SingleMotor': ('<circle cx="12" cy="17" r="3"/>'
                    '<rect x="7" y="6" width="10" height="7" rx="1.5"/>'
                    '<line x1="12" y1="13" x2="12" y2="17"/>'),
    'ColorSensor': ('<circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="3.5"/>'
                    '<line x1="12" y1="1" x2="12" y2="3.5"/>'
                    '<line x1="12" y1="20.5" x2="12" y2="23"/>'
                    '<line x1="1" y1="12" x2="3.5" y2="12"/>'
                    '<line x1="20.5" y1="12" x2="23" y2="12"/>'),
}

_IDENTIFIER_RE = re.compile(r'^[A-Za-z_][A-Za-z0-9_]*$')
_RESERVED_NAMES = {'le', 'legoeducation', 'time'}

# panel_id -> {'type': 'DoubleMotor', 'varname': 'motor1', 'instance': <device>}
panel_devices = {}
# panel_id -> <device>, kept in sync with panel_devices above -- this is the
# module-level name (alongside `le`) that fetched demo scripts reach via
# sys.modules['main_pyodide']._panel_devices, per their own page contract
# (see the module docstring). Deliberately a plain dict of raw instances,
# not the {'type', 'varname', 'instance'} wrapper above, since that's the
# exact shape their code expects.
_panel_devices = {}
_panel_id_counter = 0

_interrupt_buffer = None
_running = False
_stop_requested = False


class _InterruptibleTimeModule:
    '''Swapped into sys.modules['time'] for the duration of a run, so any
    `import time` in the user's script (however it's written) gets a
    sleep() that notices Stop within 20ms -- see the module docstring for
    why the raw interrupt buffer alone isn't reliable enough on its own.'''

    def __getattr__(self, name):
        return getattr(_real_time, name)

    def sleep(self, seconds):
        if _stop_requested:
            raise KeyboardInterrupt()
        end = _real_time.time() + seconds
        while True:
            if _stop_requested:
                raise KeyboardInterrupt()
            remaining = end - _real_time.time()
            if remaining <= 0:
                return
            _real_time.sleep(min(remaining, 0.02))


_interruptible_time = _InterruptibleTimeModule()


# ── small DOM helpers ───────────────────────────────────────────────────

def _el(id):
    return document.getElementById(id)


def log(msg, cls='log-info'):
    '''cls is a full CSS class name ("log-info" / "log-warn" / "log-error" /
    "log-ok"), not a suffix -- fetched demo scripts call this exact
    signature (positional cls, e.g. log("...", "log-warn")) directly
    against #log, per their own page contract (see module docstring).'''
    ts = datetime.now().strftime('%H:%M:%S')
    el = _el('log')
    el.innerHTML += '<div class="{}">[{}] {}</div>'.format(cls, ts, msg)
    el.scrollTop = el.scrollHeight


class _OutputWriter(io.TextIOBase):
    '''Sends print()/stderr text from user code straight into the output
    panel, unstyled -- so it reads like a terminal, not like our own log
    lines above and below it.'''

    def write(self, text):
        if text:
            el = _el('log')
            el.appendChild(document.createTextNode(text))
            el.scrollTop = el.scrollHeight
        return len(text) if text else 0


_output_writer = _OutputWriter()


def _escape(text):
    return (text.replace('&', '&amp;').replace('<', '&lt;')
                .replace('>', '&gt;').replace('"', '&quot;'))


# ── the device panel: add, render, connect, disconnect, remove ─────────

def _valid_varname(name):
    return bool(_IDENTIFIER_RE.match(name)) and name not in _RESERVED_NAMES


def _suggest_varname(device_type):
    prefix = DEVICE_VARNAME_PREFIX[device_type]
    existing = {info['varname'] for info in panel_devices.values()}
    if prefix not in existing:
        return prefix
    n = 2
    while '{}{}'.format(prefix, n) in existing:
        n += 1
    return '{}{}'.format(prefix, n)


def _render_device_list():
    container = _el('device-rows')
    if not panel_devices:
        container.innerHTML = ('<div class="empty-hint">No devices added yet '
                               '— pick a type below and add as many as you want.</div>')
        return
    rows = []
    for panel_id, info in panel_devices.items():
        connected = info['instance'].connected
        rows.append(
            '<div class="device-row" data-panel-id="{pid}" data-device-id="{pid}">'
            '<svg class="btn-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">{icon}</svg>'
            '<span class="status-dot{dot_class}"></span>'
            '<span class="device-varname">{varname}</span>'
            '<span class="device-type-label">{label}</span>'
            '<span class="status {status_class}">{status_text}</span>'
            '<select hidden><option value="{type}" selected>{type}</option></select>'
            '<input type="text" hidden value="{varname}" readonly>'
            '<div class="row">'
            '<button class="btn-connect-panel"{connect_dis}>Connect</button>'
            '<button class="btn-disconnect-panel btn-outline"{disconnect_dis}>Disconnect</button>'
            '<button class="btn-remove-panel btn-outline" title="Remove">✕</button>'
            '</div>'
            '</div>'.format(
                pid=panel_id,
                icon=DEVICE_ICONS[info['type']],
                dot_class=' connected' if connected else '',
                varname=_escape(info['varname']),
                label=DEVICE_LABELS[info['type']],
                type=info['type'],
                status_class='status-on' if connected else 'status-off',
                status_text='connected' if connected else 'not connected',
                connect_dis=' disabled' if connected else '',
                disconnect_dis='' if connected else ' disabled',
            )
        )
    container.innerHTML = ''.join(rows)


@when('change', '#add-device-type')
async def on_device_type_change(event):
    _el('add-device-name').placeholder = _suggest_varname(_el('add-device-type').value)


@when('click', '#btn-add-device')
async def on_add_device(event):
    global _panel_id_counter
    device_type = _el('add-device-type').value
    varname = _el('add-device-name').value.strip()
    if not varname:
        varname = _suggest_varname(device_type)
    if not _valid_varname(varname):
        log('"{}" isn\'t a usable variable name -- letters, numbers and '
            'underscores, and it can\'t start with a number'.format(varname), 'log-warn')
        return
    if any(info['varname'] == varname for info in panel_devices.values()):
        log('a device named "{}" already exists'.format(varname), 'log-warn')
        return

    _panel_id_counter += 1
    panel_id = 'dev{}'.format(_panel_id_counter)
    instance = DEVICE_CLASSES[device_type]()
    panel_devices[panel_id] = {
        'type': device_type,
        'varname': varname,
        'instance': instance,
    }
    _panel_devices[panel_id] = instance
    _render_device_list()
    _el('add-device-name').value = ''
    _el('add-device-name').placeholder = _suggest_varname(device_type)
    log('added {} as "{}"'.format(DEVICE_LABELS[device_type], varname), 'log-ok')


async def _connect_panel(panel_id):
    info = panel_devices.get(panel_id)
    if info is None:
        return
    dev = info['instance']
    if dev.connected:
        return
    try:
        dev.connect()
    except Exception as exc:
        log('{}: connect failed -- {}'.format(info['varname'], exc), 'log-error')
        return
    if dev.connected:
        log('{} connected'.format(info['varname']), 'log-ok')
    else:
        log('{}: no device selected'.format(info['varname']), 'log-warn')
    _render_device_list()


async def _disconnect_panel(panel_id):
    info = panel_devices.get(panel_id)
    if info is None:
        return
    dev = info['instance']
    if not dev.connected:
        return
    try:
        dev.disconnect()
    except Exception as exc:
        log('{}: disconnect error -- {}'.format(info['varname'], exc), 'log-warn')
    log('{} disconnected'.format(info['varname']), 'log-ok')
    _render_device_list()


async def _remove_panel(panel_id):
    info = panel_devices.pop(panel_id, None)
    _panel_devices.pop(panel_id, None)
    if info is None:
        return
    dev = info['instance']
    if dev.connected:
        try:
            dev.disconnect()
        except Exception:
            pass
    _render_device_list()
    log('removed "{}"'.format(info['varname']), 'log-ok')


@when('click', '#device-rows')
async def on_device_rows_click(event):
    '''Event delegation: #device-rows itself is present at page load, so
    @when can bind to it directly -- the rows inside it, added later, ride
    along on bubbling instead of each needing their own listener.'''
    btn = event.target.closest('button')
    if btn is None:
        return
    row = btn.closest('.device-row')
    if row is None:
        return
    panel_id = row.dataset.panelId
    if btn.classList.contains('btn-connect-panel'):
        await _connect_panel(panel_id)
    elif btn.classList.contains('btn-disconnect-panel'):
        await _disconnect_panel(panel_id)
    elif btn.classList.contains('btn-remove-panel'):
        await _remove_panel(panel_id)


# ── interrupt buffer, for Stop ──────────────────────────────────────────

def _setup_interrupt_buffer():
    global _interrupt_buffer
    if pyodide_js is None or not crossOriginIsolated:
        log('Stop is unavailable: needs cross-origin isolation '
            '(reload once if this just changed)', 'log-warn')
        return
    try:
        buf = SharedArrayBuffer.new(4)
        _interrupt_buffer = Int32Array.new(buf)
        pyodide_js.setInterruptBuffer(_interrupt_buffer)
    except Exception as exc:
        log('Could not set up the interrupt buffer -- {}'.format(exc), 'log-warn')


def _clear_interrupt():
    if _interrupt_buffer is not None:
        _interrupt_buffer[0] = 0


# ── examples ─────────────────────────────────────────────────────────────

EXAMPLES = {
    'single-motor': '''\
import legoeducation as le

singlemotor = le.SingleMotor()
singlemotor.connect()
if not singlemotor.connected:
    print("No Single Motor found.")
else:
    singlemotor.motor_run_for_degrees(360)
    print("spun once")
''',
    'double-motor': '''\
import legoeducation as le

doublemotor = le.DoubleMotor()
doublemotor.connect()
if not doublemotor.connected:
    print("No Double Motor found.")
else:
    doublemotor.movement_move_for_degrees(360)
    print("drove forward one wheel turn")
''',
    'color-sensor': '''\
import legoeducation as le
import time

colorsensor = le.ColorSensor()
colorsensor.connect()
if not colorsensor.connected:
    print("No Color Sensor found.")
else:
    for _ in range(20):
        print(le.LEGO_COLOR_NAME_MAP.get(colorsensor.sensor.color, "?"))
        time.sleep(0.25)
''',
    'controller': '''\
import legoeducation as le
import time

controller = le.Controller()
controller.connect()
if not controller.connected:
    print("No Controller found.")
else:
    for _ in range(20):
        s = controller.sensor
        print("left {:+.0f}%  right {:+.0f}%".format(s.leftPercent, s.rightPercent))
        time.sleep(0.25)
''',
    'double-motor-controller': '''\
import legoeducation as le
import time

doublemotor = le.DoubleMotor()
doublemotor.connect()
controller = le.Controller()
controller.connect()

if not (doublemotor.connected and controller.connected):
    print("Need both a Double Motor and a Controller.")
else:
    print("driving from the controller for 10 seconds")
    for _ in range(100):
        s = controller.sensor
        doublemotor.movement_move_tank(speed_left=s.leftPercent, speed_right=s.rightPercent)
        time.sleep(0.1)
    doublemotor.movement_stop()
''',
    'single-motor-color-sensor': '''\
import legoeducation as le
import time

singlemotor = le.SingleMotor()
singlemotor.connect()
colorsensor = le.ColorSensor()
colorsensor.connect()

if not (singlemotor.connected and colorsensor.connected):
    print("Need both a Single Motor and a Color Sensor.")
else:
    print("green is fast, red is slow, for 10 seconds")
    for _ in range(100):
        color = colorsensor.sensor.color
        if color == le.LEGO_COLOR_GREEN:
            singlemotor.motor_run(speed=80)
        elif color == le.LEGO_COLOR_RED:
            singlemotor.motor_run(speed=10)
        time.sleep(0.1)
    singlemotor.motor_stop()
''',
}


@when('click', '#btn-examples')
async def on_toggle_examples(event):
    event.stopPropagation()
    _el('examples-dropdown').classList.toggle('hidden')


@when('click', '.example-item')
async def on_pick_example(event):
    key = event.target.dataset.example
    code = EXAMPLES.get(key)
    if code is not None:
        _el('editor').value = code
        if getattr(document, 'legoIdeEditor', None):
            document.legoIdeEditor.setValue(code)
    _el('examples-dropdown').classList.add('hidden')


# Ethan Danahy's own demo programs, shared with us directly for this
# purpose -- pulled live from his GitHub repo (raw file, not the HTML page)
# straight into the editor. These are full mini-apps written against the
# host-page contract described in the module docstring, not plain
# snippets -- that's why this file exposes _panel_devices/le/#device-panel/
# #device-rows/#log rather than just running them through _run_namespace().
DEMOS = {
    'dataviewer': ('Data Viewer',
        'https://raw.githubusercontent.com/edanahy/pythonbetademos/main/dataviewer.py'),
    'posedetection': ('Pose Detection',
        'https://raw.githubusercontent.com/edanahy/pythonbetademos/main/posedetection.py'),
    'supervisedclassification': ('Supervised Classification',
        'https://raw.githubusercontent.com/edanahy/pythonbetademos/main/supervisedclassification.py'),
    'reinforcementlearning': ('Reinforcement Learning',
        'https://raw.githubusercontent.com/edanahy/pythonbetademos/main/reinforcementlearning.py'),
    'pong': ('Pong',
        'https://raw.githubusercontent.com/edanahy/pythonbetademos/main/pong.py'),
}


@when('click', '#btn-more-demos')
async def on_toggle_more_demos(event):
    event.stopPropagation()
    _el('more-demos-dropdown').classList.toggle('hidden')


@when('click', '.demo-item')
async def on_pick_demo(event):
    key = event.target.dataset.demo
    entry = DEMOS.get(key)
    _el('more-demos-dropdown').classList.add('hidden')
    if entry is None:
        return
    label, url = entry
    log('fetching "{}" from GitHub...'.format(label), 'log-info')
    try:
        response = await pyfetch(url)
        if not response.ok:
            log('"{}": GitHub returned {}'.format(label, response.status), 'log-error')
            return
        code = await response.string()
    except Exception as exc:
        log('"{}": could not fetch -- {}'.format(label, exc), 'log-error')
        return
    _el('editor').value = code
    if getattr(document, 'legoIdeEditor', None):
        document.legoIdeEditor.setValue(code)
    log('"{}" loaded into the editor -- connect the devices it needs on the '
        'left, then Run'.format(label), 'log-ok')


@when('click', 'body')
async def on_body_click(event):
    for dropdown_id, opener_id in (('examples-dropdown', 'btn-examples'),
                                   ('more-demos-dropdown', 'btn-more-demos')):
        dropdown = _el(dropdown_id)
        if dropdown.classList.contains('hidden'):
            continue
        if dropdown.contains(event.target) or _el(opener_id).contains(event.target):
            continue
        dropdown.classList.add('hidden')


# ── run / stop ───────────────────────────────────────────────────────────

def _run_namespace():
    ns = {'le': le, 'legoeducation': le, 'time': _interruptible_time}
    for info in panel_devices.values():
        if info['instance'].connected:
            ns[info['varname']] = info['instance']
    return ns


def _set_running_ui(running):
    _el('btn-run').disabled = running
    _el('btn-stop').disabled = not running


@when('click', '#btn-run')
async def on_run(event):
    global _running, _stop_requested
    if _running:
        return
    _running = True
    _stop_requested = False
    _set_running_ui(True)
    _clear_interrupt()

    code = _el('editor').value
    if getattr(document, 'legoIdeEditor', None):
        code = document.legoIdeEditor.getValue()

    old_stdout, old_stderr = sys.stdout, sys.stderr
    old_time_module = sys.modules.get('time')
    sys.stdout = sys.stderr = _output_writer
    # Swapped at the sys.modules level, not just handed to exec() as a
    # namespace entry: a bare `import time` inside the user's script would
    # otherwise re-fetch the real module and silently undo the substitution.
    sys.modules['time'] = _interruptible_time
    try:
        exec(compile(code, '<editor>', 'exec'), _run_namespace())
    except KeyboardInterrupt:
        log('stopped', 'log-warn')
    except Exception:
        sys.stdout, sys.stderr = old_stdout, old_stderr
        log(traceback.format_exc(), 'log-error')
    finally:
        sys.stdout, sys.stderr = old_stdout, old_stderr
        if old_time_module is not None:
            sys.modules['time'] = old_time_module
        _running = False
        _set_running_ui(False)


@when('click', '#btn-stop')
async def on_stop(event):
    global _stop_requested
    if not _running:
        return
    _stop_requested = True
    if _interrupt_buffer is not None:
        _interrupt_buffer[0] = 2  # SIGINT, per Pyodide's interrupt-buffer protocol
    log('stop requested...', 'log-warn')


@when('click', '#btn-clear')
async def on_clear(event):
    _el('log').innerHTML = ''


# ── boot ─────────────────────────────────────────────────────────────────

_render_device_list()
_el('add-device-name').placeholder = _suggest_varname(_el('add-device-type').value)
_setup_interrupt_buffer()
_set_running_ui(False)
document.getElementById('site-header').classList.add('ready')
log('ready -- connect devices, write or pick an example, then Run', 'log-ok')
