"""Exercise actual HTTP / persistent native core, not browser rendering."""
import base64
import json
import struct
import sys
import threading
import urllib.request
import urllib.error
from live import make_server

with make_server(sys.argv[1],0) as s:
    thread=threading.Thread(target=s.serve_forever,daemon=True)
    thread.start()
    base="http://127.0.0.1:"+str(s.server_address[1])
    def post(path,d,status=200,header=True):
        headers={"Content-Type":"application/json"}
        if header:headers["X-Ecophon-Fixture"]="1"
        q=urllib.request.Request(base+path,json.dumps(d).encode(),headers)
        try:r=urllib.request.urlopen(q,timeout=5)
        except urllib.error.HTTPError as e:r=e
        with r:
            assert r.code==status,(r.code,status)
            return json.load(r)
    def reset(p=0):
        return post("/reset",{"seed":42,"preset":p})["generation"]
    def step(g,f=180,sharing=200,p=40,ab=0):
        d=post("/step",dict(generation=g,fertility=f,sharing=sharing,pressure=p,frozen=ab))
        pcm=base64.b64decode(d["pcm"],validate=True)
        assert len(pcm)==4800 and d["rate"]==24000
        assert len(d["agents"])==8 and len(d["resources"])==4
        assert all(0<=x<=4096 for x in d["resources"])
        assert all(0<=a["energy"]<=4096 and 0<=a["patch"]<4 for a in d["agents"])
        assert max(abs(x) for x in struct.unpack("<2400h",pcm))<=24000
        return d,pcm
    try:
        with urllib.request.urlopen(base+"/") as r:assert b"habitat laboratory" in r.read()
        g=reset();a,pcm=step(g);b,pcm2=step(g)
        assert a["ticks"]==10 and b["ticks"]==20 and pcm!=pcm2 and any(pcm)
        g2=reset();assert step(g2)[1]==pcm
        good=dict(generation=g2,fertility=180,sharing=200,pressure=40,frozen=0)
        post("/step",dict(good,generation=g),409)
        for invalid in [dict(good,pressure=-1),dict(good,fertility=256),dict(good,sharing=True),dict(good,frozen=2),dict(good,unknown=1)]:
            post("/step",invalid,400)
        post("/step",good,403,False)
        assert step(g2)[1]==pcm2 # invalid requests never advance model
        g3=reset(); step(g3);normal=[step(g3) for _ in range(50)]
        g4=reset(); step(g4);harsh=[step(g4,0,0,255) for _ in range(50)]
        assert normal[-1][1]!=harsh[-1][1]
        assert normal[-1][0]["resources"]!=harsh[-1][0]["resources"]
        assert harsh[-1][0]["deaths"]>normal[-1][0]["deaths"]
        g5=reset(); frozen=[step(g5,180,200,40,1) for _ in range(51)]
        assert frozen[-1][0]["gifts"]==frozen[-1][0]["births"]==0
        assert frozen[-1][1]!=normal[-1][1]
        assert post("/panic",{"generation":g5})["muted"]
        post("/step",dict(good,generation=g5),409)
        g6=reset();assert step(g6)[1]==pcm
        print("PASS HTTP persistent PCM, reset, invalid/stale no advance, pressure intervention, frozen ablation, panic/reconnect")
        print("Normal deaths",normal[-1][0]["deaths"],"harsh deaths",harsh[-1][0]["deaths"],"ticks",harsh[-1][0]["ticks"])
    finally:
        s.shutdown()
        thread.join()
