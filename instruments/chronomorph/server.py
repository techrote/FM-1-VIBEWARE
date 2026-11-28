"""Loopback-only native audition fixture; each preview is a fresh seeded render."""
import argparse
import http.server
import pathlib
import subprocess
import tempfile
import urllib.parse

KEYS = ('preset','seed','bpm','warp','variation','seconds','len0','mask0','len1','mask1','len2','mask2')

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        url = urllib.parse.urlsplit(self.path)
        if url.path == '/' and not url.query:
            data = pathlib.Path(__file__).with_name('index.html').read_bytes()
            self.send_response(200); self.send_header('Content-Type','text/html; charset=utf-8')
            self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)
            return
        if url.path != '/render' or len(url.query)>512:
            self.send_error(404); return
        try:
            q = urllib.parse.parse_qs(url.query,strict_parsing=True,max_num_fields=12)
            if set(q)!=set(KEYS) or any(len(q[k])!=1 for k in KEYS): raise ValueError()
            args = [str(int(q[k][0])) for k in KEYS]
            with tempfile.TemporaryDirectory() as d:
                wav = pathlib.Path(d)/'preview.wav'
                p = subprocess.run([self.server.engine,'--render',str(wav),*args],capture_output=True,text=True,timeout=10)
                if p.returncode or not wav.is_file(): raise ValueError()
                data=wav.read_bytes(); state=p.stdout.strip()
                if len(data)>960044 or not data.startswith(b'RIFF') or not state: raise ValueError()
        except (ValueError, OSError, subprocess.TimeoutExpired):
            self.send_error(400,'Invalid or failed render'); return
        self.send_response(200); self.send_header('Content-Type','audio/wav')
        self.send_header('Cache-Control','no-store'); self.send_header('X-Clock-State',state)
        self.send_header('Content-Length',str(len(data))); self.end_headers(); self.wfile.write(data)

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('engine'); p.add_argument('--port',type=int,default=8766); a=p.parse_args()
    with http.server.HTTPServer(('127.0.0.1',a.port),Handler) as server:
        server.engine=str(pathlib.Path(a.engine).resolve(strict=True))
        print(f'Chronomorph: http://127.0.0.1:{a.port}',flush=True); server.serve_forever()
