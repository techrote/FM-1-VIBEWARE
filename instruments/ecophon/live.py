"""Loopback-only demand-driven audition of actual Ecophon C core."""
import argparse
import base64
import ctypes as C
import json
import struct
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
FRAMES = 2400
PRESETS = [(180,200,40,0),(100,20,150,0),(230,90,85,0),(180,200,40,1)]

class Fixture:
    def __init__(self, library):
        self.lib = C.CDLL(str(Path(library).resolve()))
        self.lib.ecof_reset.argtypes = [C.c_uint32,C.c_uint]
        self.lib.ecof_reset.restype = None
        self.lib.ecof_panic.argtypes = []
        self.lib.ecof_panic.restype = None
        self.lib.ecof_step.argtypes = [C.c_uint]*4+[C.POINTER(C.c_int16),C.POINTER(C.c_uint32)]
        self.lib.ecof_step.restype = C.c_int
        for fn in (self.lib.ecof_memory_capture,self.lib.ecof_memory_recall):
            fn.argtypes = [C.c_uint]
            fn.restype = C.c_int
        self.lib.ecof_memory_step.argtypes = [C.POINTER(C.c_int16),C.POINTER(C.c_uint32)]
        self.lib.ecof_memory_step.restype = C.c_int
        self.lib.ecof_memory_get.argtypes = [C.c_uint,C.POINTER(C.c_uint8)]
        self.lib.ecof_memory_get.restype = C.c_int
        self.gen = 0
        self.active = False

    def memory_slot(self, slot):
        values = (C.c_uint8*3)()
        return list(values) if self.lib.ecof_memory_get(slot,values) else None

    def handle(self, route, d):
        def fields(spec):
            if type(d) is not dict or set(d) != set(spec):
                raise ValueError("wrong fields")
            for k,(lo,hi) in spec.items():
                if type(d[k]) is not int or not lo <= d[k] <= hi:
                    raise ValueError("invalid "+k)
        if route == "/reset":
            fields({"seed":(0,4294967295),"preset":(0,3)})
            self.gen += 1
            self.lib.ecof_reset(d["seed"],d["preset"])
            self.active = True
            return {"generation":self.gen,"controls":PRESETS[d["preset"]],
                    "memory_slots":[self.memory_slot(i) for i in range(2)]}
        spec = {"generation":(1,2**53-1)}
        if route == "/step":
            spec.update({"fertility":(0,255),"sharing":(0,255),"pressure":(0,255),"frozen":(0,1)})
        elif route in ("/memory/capture","/memory/recall"):
            spec["slot"] = (0,1)
        elif route not in ("/panic","/memory/step"):
            raise ValueError("unknown command")
        fields(spec)
        if not self.active or d["generation"] != self.gen:
            raise RuntimeError("stale session")
        if route == "/panic":
            self.lib.ecof_panic()
            self.active = False
            return {"muted":True}
        if route in ("/memory/capture","/memory/recall"):
            fn = self.lib.ecof_memory_capture if route.endswith("capture") else self.lib.ecof_memory_recall
            if not fn(d["slot"]):
                raise RuntimeError("native memory rejected request")
            return {"generation":self.gen,"slot":d["slot"],"accepted":True,
                    "controls":self.memory_slot(d["slot"])}
        pcm=(C.c_int16*FRAMES)()
        snap=(C.c_uint32*56)()
        if route == "/memory/step":
            count = self.lib.ecof_memory_step(pcm,snap)
        else:
            count = self.lib.ecof_step(d["fertility"],d["sharing"],d["pressure"],d["frozen"],pcm,snap)
        if count!=56:
            raise RuntimeError("native fixture rejected request")
        v=list(snap)
        return {"generation":self.gen,"rate":24000,
                "pcm":base64.b64encode(struct.pack("<2400h",*pcm)).decode("ascii"),
                "ticks":v[0],"births":v[1],"deaths":v[2],"gifts":v[3],"moves":v[4],"consumed":v[5],
                "regime":v[6],"frozen":v[7],"muted":v[8],"controls":v[9:12],
                "resources":v[12:16],
                "agents":[dict(zip(("alive","patch","species","trait","energy"),v[i:i+5])) for i in range(16,56,5)],
                "state_source":"local native core (not device telemetry)"}

class Handler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(3)

    def local(self):
        port=self.server.server_address[1]
        return self.headers.get("Host") in (f"127.0.0.1:{port}",f"localhost:{port}")

    def reply(self,status,data,kind="application/json"):
        payload=data if isinstance(data,bytes) else json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type",kind)
        self.send_header("Content-Length",str(len(payload)))
        self.send_header("Cache-Control","no-store")
        self.send_header("X-Content-Type-Options","nosniff")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if self.local() and self.path=="/":
            self.reply(200,(ROOT/"live.html").read_bytes(),"text/html; charset=utf-8")
        else:
            self.reply(404,{"error":"not found"})

    def do_POST(self):
        if not self.local() or self.headers.get("X-Ecophon-Fixture")!="1":
            self.reply(403,{"error":"local fixture only"})
            return
        try:
            n=int(self.headers.get("Content-Length","0"))
            if not 1<=n<=512 or self.headers.get("Content-Type")!="application/json":
                raise ValueError("invalid body")
            d=json.loads(self.rfile.read(n))
            result=self.server.fixture.handle(self.path,d)
        except (ValueError,TypeError,UnicodeError):
            self.reply(400,{"error":"invalid request"})
        except RuntimeError as e:
            self.reply(409,{"error":str(e)})
        else:
            self.reply(200,result)

    def log_message(self,*args):
        pass

def make_server(library,port):
    server=HTTPServer(("127.0.0.1",port),Handler)
    try:
        server.fixture=Fixture(library)
    except Exception:
        server.server_close()
        raise
    return server

if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--library",default=str(ROOT/("ecof.dll" if sys.platform=="win32" else "libecof.so")))
    p.add_argument("--port",type=int,default=8768)
    a=p.parse_args()
    with make_server(a.library,a.port) as server:
        print(f"Open http://127.0.0.1:{server.server_address[1]} — local model, not FM-1",flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
