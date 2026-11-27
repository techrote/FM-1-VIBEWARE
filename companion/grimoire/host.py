"""Local-only actual-core audition; no hardware or wire protocol claim."""
import argparse, base64, ctypes as C, json, pathlib, struct
from http.server import HTTPServer, BaseHTTPRequestHandler
ROOT = pathlib.Path(__file__).resolve().parent
class Orbit(C.Structure):
    _fields_=[("phase",C.c_uint32*3),("env",C.c_uint32),("energy",C.c_uint32),("ticks",C.c_uint32),("low",C.c_int32),("x",C.c_uint8),("y",C.c_uint8),("preset",C.c_uint8),("gate",C.c_uint8)]
class Session(C.Structure):
    _fields_=[("core",Orbit),("generation",C.c_uint32),("connected",C.c_uint8)]
class Engine:
    def __init__(self,path):
        self.lib=C.CDLL(str(pathlib.Path(path).resolve()))
        l=self.lib; p=C.POINTER(Session); u=C.c_uint32
        l.os_init.argtypes=[p];l.os_init.restype=None
        l.os_connect.argtypes=[p,C.c_uint];l.os_connect.restype=u
        l.os_disconnect.argtypes=[p];l.os_disconnect.restype=None
        l.os_event.argtypes=[p,u,C.c_uint,C.c_uint,C.c_uint];l.os_event.restype=C.c_int
        l.os_render.argtypes=[p,C.POINTER(C.c_int16),C.c_size_t];l.os_render.restype=None
        self.s=Session();l.os_init(C.byref(self.s))
    def handle(self,d):
        l=self.lib;s=self.s;p=C.byref(s)
        def num(key,limit):
            v=d.get(key)
            if type(v) is not int or not 0<=v<=limit: raise ValueError(key)
            return v
        kind=d.get("kind")
        if kind=="connect":
            g=l.os_connect(p,num("version",255))
            if not g:raise ValueError("version")
            return {"generation":g,"version":1}
        g=num("generation",2**32-1)
        if not s.connected or g!=s.generation:raise ValueError("stale session")
        if kind=="disconnect":
            l.os_disconnect(p);return {"ok":True}
        if kind=="event":
            if not l.os_event(p,g,num("op",255),num("a",127),num("b",127)):raise ValueError("event")
            return {"ok":True}
        if kind=="audio":
            n=1200; b=(C.c_int16*n)();l.os_render(p,b,n)
            c=s.core
            return {"pcm":base64.b64encode(struct.pack("<"+"h"*n,*b)).decode(),"rate":24000,"phase":[v>>16 for v in c.phase],"energy":c.energy,"env":c.env,"x":c.x,"y":c.y,"gate":c.gate}
        raise ValueError("kind")
def serve(engine,port):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path!="/":self.send_error(404);return
            data=(ROOT/"index.html").read_bytes();self.send_response(200);self.send_header("Content-Type","text/html; charset=utf-8");self.end_headers();self.wfile.write(data)
        def do_POST(self):
            if self.path!="/api" or self.headers.get("Origin") not in (None,f"http://127.0.0.1:{port}") or self.headers.get("Content-Type")!="application/json":
                self.send_error(403);return
            try:
                n=int(self.headers.get("Content-Length","0"))
                if not 1<=n<=1024:raise ValueError("length")
                d=json.loads(self.rfile.read(n))
                if not isinstance(d,dict):raise ValueError("object")
                out=engine.handle(d);code=200
            except (ValueError,TypeError):out={"error":"invalid request/session"};code=400
            data=json.dumps(out).encode();self.send_response(code);self.send_header("Content-Type","application/json");self.end_headers();self.wfile.write(data)
    HTTPServer(("127.0.0.1",port),Handler).serve_forever()
if __name__=="__main__":
    a=argparse.ArgumentParser();a.add_argument("library");a.add_argument("--port",type=int,default=8765);v=a.parse_args();serve(Engine(v.library),v.port)
