"""Native block-clock Habitat Arc versus explicit direct controls (actual HTTP)."""
import base64
import hashlib
import json
import sys
import threading
import urllib.error
import urllib.request
from live import make_server

def mix(a,b,n):
    return tuple((x*(40-n)+y*n)//40 for x,y in zip(a,b))

def schedule(origin,n):
    base,drought,recovery=(180,200,40),(0,0,255),(255,220,0)
    if n<=40: return mix(origin,base,n)
    if n<=80: return mix(base,drought,n-40)
    if n<=120: return drought
    if n<=160: return mix(drought,recovery,n-120)
    return recovery

with make_server(sys.argv[1],0) as server:
    worker=threading.Thread(target=server.serve_forever,daemon=True)
    worker.start()
    base_url="http://127.0.0.1:"+str(server.server_address[1])
    def post(path,body,status=200):
        request=urllib.request.Request(base_url+path,json.dumps(body).encode(),
            {"Content-Type":"application/json","X-Ecophon-Fixture":"1"})
        try: response=urllib.request.urlopen(request,timeout=5)
        except urllib.error.HTTPError as exc: response=exc
        with response:
            assert response.code==status,(path,response.code,status)
            return json.load(response)
    def reset(preset,seed):
        return post("/reset",dict(seed=seed,preset=preset))["generation"]
    def direct(g,v,frozen=0):
        return post("/step",dict(generation=g,fertility=v[0],sharing=v[1],pressure=v[2],frozen=frozen))
    def arc(g,verb,status=200,**extra):
        return post("/arc/"+verb,dict(generation=g,**extra),status)
    def comparable(d):
        return {k:v for k,v in d.items() if k not in ("generation","arc_block","arc_remaining")}
    comparisons=sounding=0
    digest=hashlib.sha256()
    try:
        # Establish a genuinely issued, positive stale generation for the first arm.
        reset(0,42)
        for preset in range(3):
            for seed in (42,991):
                for cut in (240,73):
                    origin=(117,202,93)
                    manual=(150,240,70)
                    g=reset(preset,seed)
                    got=[direct(g,origin)]
                    expected=[origin]
                    arc(g,"step",409)
                    assert arc(g,"start")["total_blocks"]==240
                    for n in range(1,cut+1):
                        if n==11:
                            arc(0,"step",400)
                            arc(g-1,"step",409)
                            arc(g+1,"step",409)
                            arc(g,"step",400,extra=1)
                            post("/memory/step",dict(generation=g),409)
                            stored=post("/memory/capture",dict(generation=g,slot=0))
                            assert stored["controls"]==list(schedule(origin,n-1))
                        d=arc(g,"step")
                        assert d["arc_block"]==n and d["arc_remaining"]==240-n
                        got.append(d)
                        expected.append(schedule(origin,n))
                    if cut<240:
                        got.append(direct(g,manual))
                        expected.append(manual)
                    arc(g,"step",409)
                    # Frozen takeover and panic cannot leave a stale score armed.
                    direct(g,manual,1)
                    arc(g,"start",409)
                    direct(g,manual)
                    arc(g,"start")
                    post("/panic",dict(generation=g))
                    arc(g,"step",409)
                    h=reset(preset,seed)
                    arc(h,"step",409)
                    for d,v in zip(got,expected):
                        want=direct(h,v)
                        assert comparable(d)==comparable(want),(preset,seed,cut,d["ticks"])
                        raw=base64.b64decode(d["pcm"],validate=True)
                        assert len(raw)==4800
                        digest.update(raw)
                        sounding+=any(raw)
                        comparisons+=1
                    arc(g,"start",409)
        assert comparisons==1896 and sounding>0,(comparisons,sounding)
        # A successful recall interrupts the Arc, but a malformed recall does not.
        target,origin=(240,12,80),(117,202,93)
        g=reset(1,77)
        got=[direct(g,target)]
        post("/memory/capture",dict(generation=g,slot=1))
        got.append(direct(g,origin))
        expected=[target,origin]
        arc(g,"start")
        for n in range(1,6):
            if n==3:
                post("/memory/recall",dict(generation=g,slot=2),400)
            d=arc(g,"step")
            assert d["arc_block"]==n
            got.append(d)
            expected.append(schedule(origin,n))
        post("/memory/recall",dict(generation=g,slot=1))
        arc(g,"step",409)
        recall_origin=expected[-1]
        for n in range(1,41):
            if n==7:
                post("/memory/capture",dict(generation=g,slot=1))
            got.append(post("/memory/step",dict(generation=g)))
            expected.append(mix(recall_origin,target,n))
        # Reset while armed must invalidate both the old and new cursor.
        arc(g,"start")
        h=reset(1,77)
        arc(g,"step",409)
        arc(h,"step",409)
        for d,v in zip(got,expected):
            assert comparable(d)==comparable(direct(h,v)),("recall",d["ticks"])
            raw=base64.b64decode(d["pcm"],validate=True)
            assert len(raw)==4800
            digest.update(raw)
            sounding+=any(raw)
            comparisons+=1
        assert comparisons==1943 and sounding>0,(comparisons,sounding)
        print("PASS actual HTTP/native Arc",comparisons,"exact PCM/state blocks,",sounding,"sounding; SHA256",digest.hexdigest())
    finally:
        server.shutdown()
        worker.join()
