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
        for name, args in [('clear', []), ('store', [C.c_uint]*5),
                           ('capture', [C.c_uint]),
                           ('read', [C.c_uint,C.POINTER(C.c_uint32)]),
                           ('block', [C.c_uint]*2+[C.POINTER(C.c_int16),C.POINTER(C.c_uint32)])]:
            fn = getattr(self.lib,'live_memory_'+name)
            fn.argtypes = args
            fn.restype = None if name == 'clear' else C.c_int
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

    def patch(self,slot):
        values = (C.c_uint32*4)()
        return dict(zip(('p','e','d','c'),values)) if self.lib.live_memory_read(slot,values) else None

    def committed(self,q,data):
        self.seq += 1
        self.deadline = time.monotonic()+LEASE
        return 200,dict(data,seq=q['seq'])

    def memory(self,path,q):
        op = q.get('op')
        fields = {'inspect':set(), 'clear':set(), 'capture':{'slot'},
                  'store':{'slot','p','e','d','c'}} if path == '/memory' else {
                  'recall':{'slot'}, 'morph':{'position'}}
        if type(op) is not str or op not in fields or set(q) != fields[op]|{'token','seq','op'}:
            return 400,{'error':'memory fields'}
        bounds = dict(slot=(0,1),position=(0,127),**{k:LIMITS[k] for k in ('p','e','d','c')})
        if any(type(q[k]) is not int or not bounds[k][0]<=q[k]<=bounds[k][1] for k in fields[op]):
            return 400,{'error':'memory range'}
        if path == '/memory':
            if op == 'clear':
                self.lib.live_memory_clear()
            elif op == 'capture':
                self.lib.live_memory_capture(q['slot'])
            elif op == 'store':
                self.lib.live_memory_store(*(q[k] for k in ('slot','p','e','d','c')))
            return self.committed(q,{'slots':[self.patch(0),self.patch(1)],'patch':self.patch(2)})
        pcm = (C.c_int16*FRAMES)()
        levels = (C.c_uint32*6)()
        args = (0,q['slot']) if op == 'recall' else (1,q['position'])
        if not self.lib.live_memory_block(*args,pcm,levels):
            return 400,{'error':'empty material memory'}
        return self.committed(q,{'pcm':base64.b64encode(struct.pack('<1200h',*pcm)).decode('ascii'),
                                 'levels':list(levels),'patch':self.patch(2)})

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
        if path not in ('/block','/panic','/memory','/memory-block'):
            return 404,{'error':'path'}
        if not self.token or q.get('token') != self.token:
            return 409,{'error':'stale session'}
        if path == '/panic':
            if set(q) != {'token'}:
                return 400,{'error':'panic fields'}
            self.panic()
            return 200,{'muted':True}
        if path in ('/memory','/memory-block'):
            if type(q.get('seq')) is not int:
                return 400,{'error':'fields'}
            if q['seq'] != self.seq:
                return 409,{'error':'sequence'}
            return self.memory(path,q)
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
