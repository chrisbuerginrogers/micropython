'''
sensor_web.py — live color-sensor readout in the browser.

Continuously scans BLE advertisements from LEGO Education color sensors (fd02
service data, device type 0x02) and serves a little webpage. Press the button
on the page to start watching live; press it again to lock the reading.

No Web Bluetooth needed — bleak does the scanning here, the browser just
displays it, so it works in any browser on macOS.

Run:
    python card_mode/sensor_web.py
    # then open http://localhost:8000

Options:
    --port 8000        web port
    --purple-only      only show sensors wearing a purple card (byte1 == 2)
'''

import argparse
import asyncio
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from bleak import BleakScanner

FD02 = '0000fd02-0000-1000-8000-00805f9b34fb'
TYPE_COLOR_SENSOR = 0x02

COLOR_NAME = {0: 'black', 1: 'magenta', 2: 'purple', 3: 'blue', 4: 'azure',
              5: 'turquoise', 6: 'green', 7: 'yellow', 8: 'orange', 9: 'red',
              10: 'white', 0xff: 'none'}
COLOR_CSS = {'black': '#111', 'magenta': '#e0218a', 'purple': '#6b3fa0',
             'blue': '#0066b3', 'azure': '#4aa3e0', 'turquoise': '#1abc9c',
             'green': '#4a9d3f', 'yellow': '#f5c518', 'orange': '#f57c20',
             'red': '#d0202a', 'white': '#f5f5f5', 'none': '#888'}

STALE_S = 8.0

_sensors = {}          # address -> dict(color, css, card_color, serial, rssi, ts)
_numbers = {}          # address -> big display number, handed out 0, 1, 2, ...
# This workspace points Pylance at MicroPython stubs, whose Lock has no
# __enter__/__exit__ — hence the `type: ignore` on each `with _lock:` below.
# On CPython (where this script runs) the context manager is fine.
_lock = threading.Lock()
_purple_only = False


def _on_adv(device, adv):
    svc = (adv.service_data or {}).get(FD02)
    if not svc or len(svc) < 6:
        return
    p = bytes(svc)
    if p[0] != TYPE_COLOR_SENSOR:
        return
    if _purple_only and p[1] != 2:
        return
    name = COLOR_NAME.get(p[5], 'raw 0x%02x' % p[5])
    with _lock:  # type: ignore[attr-defined]
        if device.address not in _numbers:
            _numbers[device.address] = len(_numbers)   # keeps its number for the session
        _sensors[device.address] = {
            'color': name,
            'css': COLOR_CSS.get(name, '#888'),
            'card_color': COLOR_NAME.get(p[1], p[1]),
            'serial': p[3] | (p[4] << 8),
            'rssi': adv.rssi,
            'ts': time.time(),
        }


def _snapshot():
    now = time.time()
    out = []
    with _lock:  # type: ignore[attr-defined]
        for addr, s in list(_sensors.items()):
            if now - s['ts'] > STALE_S:
                continue
            out.append({'uid': addr, 'id': addr[:8], 'num': _numbers.get(addr, 0), **s,
                        'age': round(now - s['ts'], 1)})
    out.sort(key=lambda d: d['num'])
    return out


PAGE = '''<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Color sensors</title><style>
 body{font-family:-apple-system,system-ui,sans-serif;margin:0;padding:24px;
   background:#0f1115;color:#e8eaed;-webkit-user-select:none;user-select:none}
 h1{font-weight:500;font-size:20px;margin:0 0 4px}
 .sub{color:#9aa0a6;font-size:13px;margin-bottom:18px}
 #btn{font-size:18px;font-weight:500;padding:18px 26px;border:0;border-radius:14px;
   background:#3b6fd6;color:#fff;cursor:pointer;touch-action:none}
 #btn.live{background:#2fae63}
 #btn:active{transform:scale(.98)}
 #state{margin-left:14px;font-size:13px;color:#9aa0a6}
 #grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));
   gap:14px;margin-top:22px}
 .card{background:#1a1d24;border:1px solid #2a2e37;border-radius:14px;
   padding:12px;text-align:center}
 .sw{height:120px;border-radius:11px;border:1px solid #3a3f4a;margin-bottom:10px;
   display:flex;align-items:center;justify-content:center;padding:6px}
 .num{font-size:76px;font-weight:700;line-height:1;color:#fff;
   text-shadow:0 2px 10px rgba(0,0,0,.65)}
 .name{font-size:18px;font-weight:500;text-transform:capitalize}
 .meta{color:#9aa0a6;font-size:12px;margin-top:4px}
 .empty{color:#9aa0a6;margin-top:22px}
</style></head><body>
<h1>Color sensor readout</h1>
<div class="sub">Press the button to watch live. Press it again to lock the reading.</div>
<button id="btn">Press to scan</button><span id="state">locked</span>
<div id="grid"></div>
<script>
let live=false, latest=[];
const grid=document.getElementById('grid'), btn=document.getElementById('btn'),
      stateEl=document.getElementById('state');

// dark digits on a light swatch, white digits on a dark one
function inkFor(hex){
  const h=hex.replace('#',''),
        f=h.length===3?h.split('').map(c=>c+c).join(''):h,
        r=parseInt(f.slice(0,2),16), g=parseInt(f.slice(2,4),16), b=parseInt(f.slice(4,6),16);
  return (0.299*r+0.587*g+0.114*b)>150 ? '#111' : '#fff';
}
function render(d){
  if(!d.length){ grid.innerHTML='<div class="empty">No color sensors detected yet — power one on and tap its card.</div>'; return; }
  grid.innerHTML='';
  for(const s of d){
    const el=document.createElement('div'); el.className='card';
    el.innerHTML='<div class="sw" style="background:'+s.css+'">'
      +'<div class="num" style="color:'+inkFor(s.css)+'">'+s.num+'</div></div>'
      +'<div class="name">'+s.color+'</div>'
      +'<div class="meta">card '+s.card_color+' #'+s.serial
      +' · '+s.rssi+' dBm · '+s.age+'s</div>';
    grid.appendChild(el);
  }
}
async function fetchColors(){ const r=await fetch('/colors'); return await r.json(); }
async function poll(){
  try{ latest=await fetchColors(); }catch(e){}
  if(live) render(latest);
}
setInterval(poll,200); poll();

function setLive(on){
  live=on;
  btn.classList.toggle('live',on);
  btn.textContent=on?'Scanning… (press to lock)':'Press to scan';
  stateEl.textContent=on?'live':'locked';
}
async function lock(){ setLive(false);
  try{ render(await fetchColors()); }catch(e){} }   // freeze on the reading at the press
btn.addEventListener('click',e=>{
  e.preventDefault();
  if(live){ lock(); } else { setLive(true); render(latest); }
});
</script></body></html>'''


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith('/colors'):
            body = json.dumps(_snapshot()).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            body = PAGE.encode()
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    def log_message(self, format, *args):
        pass


async def main(port):
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print('open http://localhost:{}  (Ctrl+C to stop)'.format(port))
    async with BleakScanner(detection_callback=_on_adv):
        while True:
            await asyncio.sleep(1)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--port', type=int, default=8000)
    ap.add_argument('--purple-only', action='store_true',
                    help='only sensors wearing a purple card (byte1==2)')
    args = ap.parse_args()
    _purple_only = args.purple_only
    try:
        asyncio.run(main(args.port))
    except KeyboardInterrupt:
        print('\nstopped.')