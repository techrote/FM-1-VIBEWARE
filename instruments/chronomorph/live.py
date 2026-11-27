"""Single-client local audition. Pull-clocked 50 ms blocks, no device transport."""
import argparse
import base64
import ctypes as C
import http.server
import json
import pathlib
import secrets
import struct
import time

FRAMES=1200
LEASE=1.5

def integer(v,lo,hi):
    if type(v) is not int or not lo<=v<=hi:
        raise ValueError("integer out of range")
    return v

class Engine:
    def __init__(self,path):
        self.lib=C.CDLL(str(pathlib.Path(path).resolve(strict=True)))
        self.lib.live_reset.argtypes=[C.c_uint32,C.c_uint]
        self.lib.live_reset.restype=None
        self.lib.live_stop.argtypes=[]
        self.lib.live_stop.restype=None
        self.lib.live_block.argtypes=[C.c_uint,C.c_int,C.c_uint,C.c_uint,
            C.POINTER(C.c_uint32),C.POINTER(C.c_int16),C.POINTER(C.c_uint32)]
        self.lib.live_block.restype=C.c_int
        self.token=None
        self.seq=0
        self.deadline=0
        self.lib.live_reset(17,0)

    def expire(self):
        if self.token is not None and time.monotonic()>=self.deadline:
            self.lib.live_stop()
            self.token=None

    def request(self,path,q):
        self.expire()
        if type(q) is not dict:
            raise ValueError("object required")
        if path=="/session":
            if set(q)!={"version","preset","seed"} or integer(q["version"],1,1)!=1:
                raise ValueError("profile mismatch")
            preset=integer(q["preset"],0,2)
            seed=integer(q["seed"],1,2147483647)
            self.lib.live_reset(seed,preset)
            self.token=secrets.token_hex(16)
            self.seq=0
            self.deadline=time.monotonic()+LEASE
            return {"token":self.token,"version":1}
        if self.token is None or q.get("token")!=self.token:
            raise PermissionError("stale session")
        if path=="/panic":
            if set(q)!={"token"}: raise ValueError("invalid panic")
            self.lib.live_stop()
            self.token=None
            return {"stopped":True}
        if path!="/block" or set(q)!={"token","seq","bpm","warp","variation","playing","patterns"}:
            raise ValueError("invalid block")
        seq=integer(q["seq"],1,2147483647)
        if seq!=self.seq+1:
            raise PermissionError("out of order")
        bpm=integer(q["bpm"],40,220)
        warp=integer(q["warp"],-60,60)
        variation=integer(q["variation"],0,100)
        playing=integer(q["playing"],0,1)
        patterns=q["patterns"]
        if type(patterns) is not list or len(patterns)!=3:
            raise ValueError("three patterns required")
        pairs=[]
        for p in patterns:
            if type(p) is not list or len(p)!=2:
                raise ValueError("pattern pair required")
            length=integer(p[0],1,16)
            pairs.extend((length,integer(p[1],0,(1<<length)-1)))
        pcm=(C.c_int16*FRAMES)()
        snap=(C.c_uint32*15)()
        if not self.lib.live_block(bpm,warp,variation,playing,(C.c_uint32*6)(*pairs),pcm,snap):
            raise ValueError("core rejected block")
        self.seq=seq
        self.deadline=time.monotonic()+LEASE
        return {"seq":seq,"pcm":base64.b64encode(struct.pack("<1200h",*pcm)).decode("ascii"),
                "lanes":[list(snap[i:i+5]) for i in range(0,15,5)],"playing":playing}

class Handler(http.server.BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(2)
    def reply(self,status,data,kind="application/json"):
        self.send_response(status)
        self.send_header("Content-Type",kind)
        self.send_header("Content-Length",str(len(data)))
        self.send_header("Cache-Control","no-store")
        self.end_headers()
        self.wfile.write(data)
    def local(self):
        host=f"127.0.0.1:{self.server.server_port}"
        return self.headers.get("Host")==host and self.headers.get("Origin") in (None,"http://"+host)
    def do_GET(self):
        if not self.local(): self.send_error(403); return
        if self.path!="/": self.send_error(404); return
        self.reply(200,pathlib.Path(__file__).with_name("live.html").read_bytes(),"text/html; charset=utf-8")
    def do_POST(self):
        if not self.local(): self.send_error(403); return
        try:
            if self.headers.get("Content-Type")!="application/json": raise ValueError("JSON required")
            n=integer(int(self.headers.get("Content-Length","0")),1,1024)
            result=self.server.engine.request(self.path,json.loads(self.rfile.read(n)))
        except PermissionError:
            self.send_error(409,"stale or out-of-order session"); return
        except (ValueError,TypeError,OverflowError):
            self.send_error(400,"invalid request"); return
        self.reply(200,json.dumps(result,separators=(",",":")).encode("ascii"))

class Server(http.server.HTTPServer):
    def service_actions(self):
        self.engine.expire()

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("library",nargs="?",default=str(pathlib.Path(__file__).with_name("chronomorph-live.dll" if __import__("os").name=="nt" else "chronomorph-live.so")))
    p.add_argument("--port",type=int,default=8767)
    a=p.parse_args()
    with Server(("127.0.0.1",a.port),Handler) as s:
        s.engine=Engine(a.library)
        print(f"Chronomorph live: http://127.0.0.1:{s.server_port}",flush=True)
        s.serve_forever(poll_interval=.1)
