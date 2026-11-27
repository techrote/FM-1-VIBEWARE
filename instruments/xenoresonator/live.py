"""Local, single-session Xenoresonator performance fixture (not a wire protocol)."""
import argparse
import base64
import ctypes as C
import json
import pathlib
import secrets
import struct
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

LIMITS = dict(p=(0,3), e=(0,127), d=(0,127), c=(0,127), n=(36,84), v=(1,127), event=(0,2))
FRAMES = 1200
LEASE = 1.5

class Session:
    def __init__(self, library):
        self.lib = C.CDLL(str(pathlib.Path(library).resolve(strict=True)))
        for name in ('live_reset','live_panic'):
            fn = getattr(self.lib,name)
            fn.argtypes = []
            fn.restype = None
        self.lib.live_block.argtypes = [C.c_uint]*7+[C.POINTER(C.c_int16),C.POINTER(C.c_uint32)]
        self.lib.live_block.restype = None
        self.token = None
        self.seq = 0
        self.deadline = 0
        self.lib.live_reset()

    def expire(self):
        if self.token and time.monotonic() >= self.deadline:
            self.panic()

    def panic(self):
        self.lib.live_panic()
        self.token = None

    def request(self,path,q):
        self.expire()
        if path == '/open':
            if q != {'version':1} or type(q.get('version')) is not int:
                return 400,{'error':'profile version'}
            self.lib.live_reset()
            self.token = secrets.token_hex(16)
            self.seq = 0
            self.deadline = time.monotonic()+LEASE
            return 200,{'token':self.token,'rate':24000,'frames':FRAMES}
        if path not in ('/block','/panic'):
            return 404,{'error':'path'}
        if not self.token or q.get('token') != self.token:
            return 409,{'error':'stale session'}
        if path == '/panic':
            if set(q) != {'token'}:
                return 400,{'error':'panic fields'}
            self.panic()
            return 200,{'muted':True}
        if set(q) != set(LIMITS)|{'token','seq'} or type(q.get('seq')) is not int:
            return 400,{'error':'fields'}
        if q['seq'] != self.seq:
            return 409,{'error':'sequence'}
        if any(type(q[k]) is not int or not lo<=q[k]<=hi for k,(lo,hi) in LIMITS.items()):
            return 400,{'error':'control range'}
        pcm = (C.c_int16*FRAMES)()
        levels = (C.c_uint32*6)()
        self.lib.live_block(*(q[k] for k in LIMITS),pcm,levels)
        self.seq += 1
        self.deadline = time.monotonic()+LEASE
        return 200,{'pcm':base64.b64encode(struct.pack('<1200h',*pcm)).decode('ascii'), 'levels':list(levels),'seq':q['seq']}

class Server(HTTPServer):
    def service_actions(self):
        self.session.expire()

class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(2)

    def reply(self,status,data,kind='application/json'):
        if kind == 'application/json':
            data = json.dumps(data,separators=(',',':')).encode()
        self.send_response(status)
        self.send_header('Content-Type',kind)
        self.send_header('Content-Length',str(len(data)))
        self.send_header('Cache-Control','no-store')
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == '/':
            self.reply(200,(pathlib.Path(__file__).parent/'live.html').read_bytes(),'text/html; charset=utf-8')
        else:
            self.reply(404,{'error':'path'})

    def do_POST(self):
        try:
            # No cross-origin access; browsers cannot send JSON cross-origin without preflight.
            if self.headers.get('Content-Type') != 'application/json':
                raise ValueError()
            origin = self.headers.get('Origin')
            if origin and origin != 'http://127.0.0.1:'+str(self.server.server_port):
                raise ValueError()
            if self.headers.get('Host') != '127.0.0.1:'+str(self.server.server_port):
                raise ValueError()
            size = int(self.headers.get('Content-Length','0'))
            if not 1<=size<=1024:
                raise ValueError()
            q = json.loads(self.rfile.read(size))
            if not isinstance(q,dict):
                raise ValueError()
        except (ValueError,TimeoutError):
            self.reply(400,{'error':'invalid request'})
            return
        self.reply(*self.server.session.request(self.path,q))

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('library')
    p.add_argument('--port',type=int,default=8766)
    a = p.parse_args()
    with Server(('127.0.0.1',a.port),Handler) as server:
        server.session = Session(a.library)
        print(f'http://127.0.0.1:{server.server_port}',flush=True)
        server.serve_forever(poll_interval=.1)
