'''
sensor_web.py — live colour-sensor readout in the browser.

Continuously scans BLE advertisements from LEGO Education colour sensors (fd02
service data, device type 0x02) and serves a little webpage. Press the button
on the page to snapshot what each sensor is currently sensing.

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
    with _lock:
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
    with _lock:
        for addr, s in list(_sensors.items()):
            if now - s['ts'] > STALE_S:
                continue
            out.append({'uid': addr, 'id': addr[:8], **s,
                        'age': round(now - s['ts'], 1)})
    out.sort(key=lambda d: d['uid'])
    return out


PAGE = '''<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Colour sensors</title><style>
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
 .uid{font-family:ui-monospace,Menlo,monospace;font-size:11px;line-height:1.35;
   color:#fff;background:rgba(0,0,0,.5);padding:5px 7px;border-radius:7px;
   word-break:break-all;max-width:100%}
 .name{font-size:18px;font-weight:500;text-transform:capitalize}
 .meta{color:#9aa0a6;font-size:12px;margin-top:4px}
 .empty{color:#9aa0a6;margin-top:22px}
</style></head><body>
<h1>Colour sensor readout</h1>
<div class="sub">Hold the button to watch live. Let go to lock the reading.</div>
<button id="btn">Hold to scan</button><span id="state">locked</span>
<div id="grid"></div>
<script>
let live=false, latest=[];
const grid=document.getElementById('grid'), btn=document.getElementById('btn'),
      stateEl=document.getElementById('state');

function render(d){
  if(!d.length){ grid.innerHTML='<div class="empty">No colour sensors detected yet — power one on and tap its card.</div>'; return; }
  grid.innerHTML='';
  for(const s of d){
    const el=document.createElement('div'); el.className='card';
    el.innerHTML='<div class="sw" style="background:'+s.css+'">'
      +'<div class="uid">'+s.uid+'</div></div>'
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
  btn.textContent=on?'Scanning…':'Hold to scan';
  stateEl.textContent=on?'live':'locked';
}
btn.addEventListener('pointerdown',e=>{ e.preventDefault(); setLive(true); render(latest); });
async function lock(){ if(!live) return; setLive(false);
  try{ render(await fetchColors()); }catch(e){} }   // freeze on the reading at release
window.addEventListener('pointerup',lock);
window.addEventListener('pointercancel',lock);
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

    def log_message(self, *a):
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