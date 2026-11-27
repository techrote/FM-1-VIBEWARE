import base64
import json
import pathlib
import struct
import sys
import threading
import time
import urllib.error
import urllib.request
from live import Engine,Server,Handler

with Server(("127.0.0.1",0),Handler) as s:
    s.engine=Engine(sys.argv[1])
    t=threading.Thread(target=s.serve_forever,kwargs={"poll_interval":.05},daemon=True)
    t.start()
    root=f"http://127.0.0.1:{s.server_port}"
    def post(path,q,code=200):
        req=urllib.request.Request(root+path,data=json.dumps(q).encode(),headers={"Content-Type":"application/json"})
        try:
            with urllib.request.urlopen(req,timeout=4) as r:
                assert code==200
                return json.load(r)
        except urllib.error.HTTPError as e:
            assert e.code==code,(e.code,code)
    def session():return post("/session",{"version":1,"seed":17,"preset":0})["token"]
    def block(token,seq,**kw):
        return dict(token=token,seq=seq,bpm=112,warp=24,variation=12,playing=1,patterns=[[7,73],[5,21],[11,1321]])|kw
    def samples(r):
        return struct.unpack("<1200h",base64.b64decode(r["pcm"]))
    try:
        assert b"Chronomorph" in urllib.request.urlopen(root+"/",timeout=4).read()
        a=session()
        first=post("/block",block(a,1))
        post("/session",{"version":2,"seed":17,"preset":0},400)
        post("/block",block(a,1),409)
        post("/block",block(a,2,patterns=[[1,2],[5,21],[11,1321]]),400)
        second=post("/block",block(a,2))
        assert any(samples(first)) and first["pcm"]!=second["pcm"]
        b=session()
        post("/block",block(a,3),409)
        assert post("/block",block(b,1))==first
        assert post("/block",block(b,2))==second
        baseline=[post("/block",block(b,i)) for i in range(3,43)]
        c=session()
        assert post("/block",block(c,1))==first
        assert post("/block",block(c,2))==second
        altered=[post("/block",block(c,i,bpm=220,warp=-60,patterns=[[1,0],[5,21],[11,1321]])) for i in range(3,43)]
        assert any(x["pcm"]!=y["pcm"] for x,y in zip(baseline,altered))
        assert baseline[-1]["lanes"]!=altered[-1]["lanes"]
        pause=post("/block",block(c,43,playing=0))
        assert not any(samples(pause)) and pause["lanes"]==altered[-1]["lanes"]
        again=post("/block",block(c,44,playing=0))
        assert again["lanes"]==pause["lanes"]
        resume=post("/block",block(c,45))
        assert resume["playing"]==1
        post("/panic",{"token":c})
        post("/block",block(c,46),409)
        d=session()
        assert post("/block",block(d,1))==first
        time.sleep(1.7)
        post("/block",block(d,2),409)
        e=session()
        assert post("/block",block(e,1))==first
        print("Live HTTP PASS: 48,000-frame intervention, exact reset/replay, phase-preserving pause, panic, expiry, invalid profile/pattern, stale and duplicate rejection")
    finally:
        s.shutdown();t.join()
