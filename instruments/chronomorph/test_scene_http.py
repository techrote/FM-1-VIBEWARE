"""Actual local HTTP/native score consumer vs direct control replay."""
import base64,json,sys,threading,time,urllib.error,urllib.request
from live import Engine,Handler,Server

CUES=[
    dict(bpm=112,warp=24,variation=12,patterns=[[7,73],[5,21],[11,1321]]),
    dict(bpm=220,warp=-60,variation=88,patterns=[[3,5],[16,32769],[9,257]]),
]
with Server(("127.0.0.1",0),Handler) as server:
    server.engine=Engine(sys.argv[1])
    worker=threading.Thread(target=server.serve_forever,daemon=True)
    worker.start()
    root=f"http://127.0.0.1:{server.server_port}"
    def post(path,data,code=200):
        req=urllib.request.Request(root+path,data=json.dumps(data).encode(),headers={"Content-Type":"application/json"})
        try:
            with urllib.request.urlopen(req,timeout=4) as response:
                assert code==200,(path,code)
                return json.load(response)
        except urllib.error.HTTPError as exc:
            assert exc.code==code,(path,exc.code,code)
    def session(preset):
        return post("/session",dict(version=1,preset=preset,seed=17))["token"]
    def direct(token,seq,cue,playing=1):
        return post("/block",dict(token=token,seq=seq,playing=playing,**cue))
    def stripped(r):
        return {k:r[k] for k in ("pcm","lanes","playing")}
    def quiet(r):
        return not any(base64.b64decode(r["pcm"]))
    total=sounding=0
    try:
        for preset in range(3):
            t=session(preset)
            post("/score/begin",dict(token=t,seq=1,seconds=1),400)
            prefix=[direct(t,1,CUES[0])]
            assert post("/scene/capture",dict(token=t,seq=2,slot=0))["scene"]["occupied_mask"]==1
            prefix.append(direct(t,3,CUES[1]))
            assert post("/scene/capture",dict(token=t,seq=4,slot=3))["scene"]["occupied_mask"]==9
            assert post("/score/begin",dict(token=t,seq=5,seconds=1))["scene"]["next_slot"]==0
            assert post("/scene/clear",dict(token=t,seq=6))["scene"]["occupied_mask"]==0
            post("/score/begin",dict(token=t,seq=7,seconds=1),400)
            post("/score/block",dict(token=t,seq=8),409)
            actual=[]
            for n in range(40):
                row=post("/score/block",dict(token=t,seq=7+n))
                actual.append(stripped(row))
                assert row["scene"]["next_slot"]==(0 if n<19 else 3 if n<39 else None)
                assert row["scene"]["remaining_blocks"]==(20 if n==19 else 19-n%20)
            post("/score/block",dict(token=t,seq=47),400)
            assert quiet(direct(t,47,CUES[1],0))
            post("/scene/recall",dict(token=t,seq=48,slot=0,playing=1),400)
            post("/scene/capture",dict(token=t,seq=48,slot=2))
            recall=post("/scene/recall",dict(token=t,seq=49,slot=2,playing=1))
            assert recall["scene"]["next_slot"] is None
            post("/score/begin",dict(token=t,seq=50,seconds=1))
            post("/block",dict(token=t,seq=51,playing=1,**(CUES[0]|{"bpm":0})),400)
            resumed=post("/score/block",dict(token=t,seq=51))
            assert resumed["scene"]["remaining_blocks"]==19
            assert quiet(direct(t,52,CUES[0],0))
            post("/score/block",dict(token=t,seq=53),400)
            post("/panic",dict(token=t))
            post("/score/begin",dict(token=t,seq=53,seconds=1),409)
            b=session(preset)
            post("/scene/recall",dict(token=b,seq=1,slot=2,playing=1),400)
            assert stripped(direct(b,1,CUES[0]))==stripped(prefix[0])
            assert stripped(direct(b,2,CUES[1]))==stripped(prefix[1])
            for n,row in enumerate(actual):
                expected=stripped(direct(b,3+n,CUES[n//20]))
                assert row==expected,(preset,n)
                total+=1;sounding+=not quiet(row)
            assert quiet(direct(b,43,CUES[1],0))
            assert stripped(recall)==stripped(direct(b,44,CUES[1]))
            post("/scene/capture",dict(token=b,seq=45,slot=0))
            post("/score/begin",dict(token=b,seq=46,seconds=1))
            time.sleep(1.7)
            post("/score/block",dict(token=b,seq=47),409)
        # Imported/factory cues arm atomically without rendering an extra
        # block or mutating the separate native capture bank.
        imported=0
        for preset in range(3):
            t=session(preset)
            slots=[CUES[0],None,None,CUES[1]]
            def arm(seq,seconds,values,code=200):
                return post("/score/start",dict(token=t,seq=seq,seconds=seconds,slots=values),code)
            assert arm(1,1,slots)["scene"]==dict(next_slot=0,remaining_blocks=20,occupied_mask=0,total_remaining=40)
            arm(2,1,[CUES[0],None,None,CUES[1]|{"bpm":221}],400)
            arm(2,1,[None]*4,400)
            arm(2,0,slots,400)
            arm(3,1,slots,409)
            actual=[]
            for n in range(40):
                row=post("/score/block",dict(token=t,seq=2+n))
                assert row["frame"]==dict(slot=0 if n<20 else 3,controls=CUES[n//20])
                assert row["scene"]["total_remaining"]==39-n
                assert row["scene"]["occupied_mask"]==0
                actual.append(stripped(row))
            post("/score/block",dict(token=t,seq=42),400)
            assert quiet(direct(t,42,CUES[1],0))
            assert arm(43,1,slots)["scene"]["total_remaining"]==40
            post("/panic",dict(token=t))
            post("/score/block",dict(token=t,seq=44),409)
            b=session(preset)
            post("/score/block",dict(token=b,seq=1),400)
            for n,row in enumerate(actual):
                assert row==stripped(direct(b,n+1,CUES[n//20])),(preset,n)
                imported+=1
        assert imported==120
        print("Atomic imported score: 120 exact PCM/state blocks, native cue readback, rejection, detached bank and panic PASS")
        assert total==120 and sounding>0
        print(f"Native HTTP score: {total} exact PCM/state blocks, {sounding} sounding; detached bank, recall, cancellation, panic and expiry PASS")
    finally:
        server.shutdown();worker.join()
