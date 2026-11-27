"""Local actual-core note audition; no MIDI, device or telemetry claims."""
import argparse
import pathlib
import subprocess
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

PAGE = b'''<!doctype html><meta charset="utf-8"><title>Xenoresonator</title>
<style>body{font:16px system-ui;background:#141922;color:#e6e8ee;max-width:540px;margin:3em auto;padding:1em}label{display:block;margin:1em 0}input,select,button{font:inherit}input[type=range]{width:100%}button{padding:.6em}small{color:#aab7c8}</style>
<h1>Xenoresonator</h1><p>Coupled virtual materials / local native-core audition</p>
<label>Material <select id="p"><option value="0">Ceramic</option><option value="1">Woodglass</option><option value="2">Alien metal</option><option value="3">Membrane</option></select></label>
<label>Excitation (X)<input id="e" type="range" min="0" max="127" value="76"></label>
<label>Damping (Y)<input id="d" type="range" min="0" max="127" value="12"></label>
<label>Coupling<input id="c" type="range" min="0" max="127" value="90"></label>
<label>Note<input id="n" type="number" min="36" max="84" value="48"></label>
<label>Velocity<input id="v" type="range" min="1" max="127" value="110"></label>
<button id="play">Strike</button> <button id="phrase">Play phrase</button> <button id="stop">Stop</button>
<p id="status" role="status">Ready</p><small>Each gesture renders actual engine audio; controls apply on next strike. No device connection. Stop cancels local playback.</small>
<script>let a=new Audio(),generation=0,object=null;const $=id=>document.getElementById(id);function stop(){generation++;a.pause();a.removeAttribute('src');a.load();if(object){URL.revokeObjectURL(object);object=null;}$('status').textContent='Stopped';}async function play(phrase){stop();const g=generation;const q=new URLSearchParams();for(const k of ['p','e','d','c','n','v'])q.set(k,$(k).value);q.set('phrase',phrase?'1':'0');$('status').textContent='Rendering';try{const r=await fetch('/render?'+q);if(!r.ok)throw Error('Invalid controls or renderer failure');const b=await r.blob();if(g!==generation)return;object=URL.createObjectURL(b);a.src=object;await a.play();if(g===generation)$('status').textContent='Playing native-core render';}catch(e){if(g===generation)$('status').textContent=String(e);}}$('play').onclick=()=>play(false);$('phrase').onclick=()=>play(true);$('stop').onclick=stop;</script>'''

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        u = urlsplit(self.path)
        if u.path == '/':
            self.send_payload(200, 'text/html; charset=utf-8', PAGE)
            return
        if u.path != '/render' or len(u.query) > 160:
            self.send_error(404)
            return
        try:
            q = parse_qs(u.query, strict_parsing=True)
            limits = {'p': (0,3), 'e': (0,127), 'd': (0,127), 'c': (0,127), 'n': (36,84), 'v': (0,127), 'phrase': (0,1)}
            if set(q) != set(limits):
                raise ValueError()
            for k, (lo, hi) in limits.items():
                if len(q[k]) != 1 or not lo <= int(q[k][0]) <= hi or not q[k][0].isascii() or not q[k][0].isdigit():
                    raise ValueError()
        except ValueError:
            self.send_error(400, 'Invalid controls')
            return
        try:
            with tempfile.TemporaryDirectory(prefix='xeno audition ') as d:
                wav = pathlib.Path(d)/'note.wav'
                args = [str(self.server.renderer), str(wav)] + [q[k][0] for k in ('p','e','d','c','n','v')]
                if q['phrase'][0] == '1':
                    args.append('phrase')
                subprocess.run(args, check=True, timeout=8)
                self.send_payload(200, 'audio/wav', wav.read_bytes())
        except (OSError, subprocess.SubprocessError):
            self.send_error(500, 'Renderer failed')

    def send_payload(self, status, kind, data):
        self.send_response(status)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(data)

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('renderer', type=pathlib.Path)
    p.add_argument('--port', type=int, default=8765)
    a = p.parse_args()
    with ThreadingHTTPServer(('127.0.0.1', a.port), Handler) as server:
        server.renderer = a.renderer.resolve(strict=True)
        print(f'http://127.0.0.1:{server.server_port}', flush=True)
        server.serve_forever()
