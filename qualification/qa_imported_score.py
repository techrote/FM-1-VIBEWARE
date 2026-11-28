"""Independent Chronomorph imported-score oracle against the running native server."""
import base64
import hashlib
import http.client
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time

CUES = [
    dict(bpm=40, warp=-60, variation=0, patterns=[[1,1],[16,32769],[9,257]]),
    dict(bpm=220, warp=60, variation=100, patterns=[[16,65535],[3,5],[7,73]]),
    dict(bpm=137, warp=-17, variation=53, patterns=[[13,4693],[8,129],[4,5]]),
    dict(bpm=79, warp=31, variation=19, patterns=[[5,21],[11,1321],[2,3]]),
]

def exercise(root, lib):
    root = root.resolve()
    with tempfile.TemporaryDirectory(prefix="QA score server log ") as td:
        log = Path(td)/"server.log"
        with log.open("w", encoding="utf-8") as stream:
            child = subprocess.Popen([sys.executable, str(root/"live.py"), str(root/lib), "--port","0"],
                                     cwd=root, stdout=stream, stderr=stream)
            try:
                deadline=time.monotonic()+15
                while True:
                    lines=log.read_text(encoding="utf-8",errors="replace").splitlines()
                    urls=[x.split("http://127.0.0.1:",1)[1].strip() for x in lines if "http://127.0.0.1:" in x]
                    if urls:
                        port=int(urls[0])
                        break
                    assert child.poll() is None and time.monotonic()<deadline,lines
                    time.sleep(.05)
                def post(path, data, code=200):
                    conn=http.client.HTTPConnection("127.0.0.1",port,timeout=5)
                    try:
                        conn.request("POST",path,json.dumps(data),{"Content-Type":"application/json"})
                        res=conn.getresponse()
                        raw=res.read()
                        assert res.status==code,(path,res.status,code,raw[:200])
                        return json.loads(raw) if code==200 else None
                    finally:
                        conn.close()
                def session(preset):
                    return post("/session",dict(version=1,preset=preset,seed=181))["token"]
                def direct(t,seq,cue,playing=1):
                    return post("/block",dict(token=t,seq=seq,playing=playing,**cue))
                def sample(row):
                    raw=base64.b64decode(row["pcm"],validate=True)
                    assert len(raw)==2400 and len(row["lanes"])==3
                    return raw,row["lanes"],row["playing"]
                count=sounding=0
                digest=hashlib.sha256()
                for preset in range(3):
                    for mask in range(1,16):
                        slots=[c if mask&(1<<i) else None for i,c in enumerate(CUES)]
                        indices=[i for i,x in enumerate(slots) if x is not None]
                        t=session(preset)
                        def cmd(path,seq,code=200,**kw):
                            return post(path,dict(token=t,seq=seq,**kw),code)
                        start=cmd("/score/start",1,seconds=1,slots=slots)
                        total=20*len(indices)
                        assert start["scene"]==dict(next_slot=indices[0],remaining_blocks=20,
                                                    occupied_mask=0,total_remaining=total)
                        cmd("/score/start",2,400,seconds=1,slots=[None]*4)
                        cmd("/score/start",2,400,seconds=1,slots=[CUES[0]|{"patterns":[[1,2],[1,1],[1,1]]},None,None,None])
                        cmd("/score/block",3,409)
                        actual=[]
                        for n in range(total):
                            row=cmd("/score/block",2+n)
                            i=indices[n//20]
                            assert row["frame"]==dict(slot=i,controls=CUES[i])
                            assert row["scene"]["total_remaining"]==total-n-1
                            actual.append(sample(row))
                        cmd("/score/block",total+2,400)
                        assert not any(sample(direct(t,total+2,CUES[0],0))[0])
                        post("/panic",{"token":t})
                        cmd("/score/block",total+3,409)
                        fresh=session(preset)
                        for n,got in enumerate(actual):
                            expected=sample(direct(fresh,n+1,CUES[indices[n//20]]))
                            assert got==expected,(preset,mask,n)
                            digest.update(got[0])
                            digest.update(json.dumps(got[1],separators=(",",":")).encode())
                            count+=1
                            sounding+=bool(any(got[0]))
                        assert not any(sample(direct(fresh,total+1,CUES[0],0))[0])
                assert count==1920 and sounding>0
                return dict(blocks=count,sounding=sounding,trace_sha256=digest.hexdigest(),
                            masks=15,presets=3,invalid_replacement_and_panic="PASS")
            finally:
                child.terminate()
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait(timeout=5)
                assert "runtime error:" not in log.read_text(encoding="utf-8",errors="replace")

if __name__=="__main__":
    a=exercise(Path(sys.argv[1]),sys.argv[3])
    b=exercise(Path(sys.argv[2]),sys.argv[3])
    assert a==b,(a,b)
    print(json.dumps(a,sort_keys=True))
