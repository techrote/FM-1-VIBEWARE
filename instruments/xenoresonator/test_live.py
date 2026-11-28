import base64
import json
import pathlib
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.request

root = pathlib.Path(__file__).resolve().parent
proc = subprocess.Popen([sys.executable,str(root/'live.py'),sys.argv[1],'--port','0'],stdout=subprocess.PIPE,text=True)
try:
    url = proc.stdout.readline().strip()
    assert url.startswith('http://127.0.0.1:')
    def post(path,q,status=200):
        req = urllib.request.Request(url+path,json.dumps(q).encode(),{'Content-Type':'application/json'})
        try:
            with urllib.request.urlopen(req,timeout=5) as res:
                assert res.status == status
                return json.load(res)
        except urllib.error.HTTPError as exc:
            assert exc.code == status,(exc.code,status)
    def open_session():
        return post('/open',{'version':1})['token']
    def block(token,seq,event=0,c=90,d=0,p=2,status=200):
        return post('/block',dict(token=token,seq=seq,event=event,c=c,d=d,p=p,e=76,n=48,v=110),status)
    def pcm(r):
        return struct.unpack('<1200h',base64.b64decode(r['pcm']))
    token=open_session()
    a=block(token,0,1)
    assert any(pcm(a)) and any(a['levels'][3:])
    assert all(0<=x<=131070 for x in a['levels'])
    post('/open',{'version':2},400)
    block(token,0,status=409)
    block(token,1,c=128,status=400)
    b=block(token,1)
    assert any(pcm(b))
    token2=open_session()
    assert block(token2,0,1)==a
    assert block(token2,1)==b
    block(token,2,1,status=409)
    token3=open_session()
    uncoupled=block(token3,0,1,c=0)
    assert pcm(uncoupled)!=pcm(a) and uncoupled['levels'][3:]==[0]*3
    # Alter damping during a live decay, not a new strike.
    token4=open_session(); block(token4,0,1)
    changed=block(token4,1,d=127)
    assert pcm(changed)!=pcm(b)
    released=block(token4,2,2,d=127)
    for i in range(3,8):
        tail=block(token4,i,d=127)
    assert max(map(abs,pcm(tail)))==0
    post('/panic',{'token':token4})
    block(token4,8,1,status=409)
    token5=open_session(); silence=block(token5,0)
    assert not any(pcm(silence)) and silence['levels']==[0]*6
    block(token5,1,1)
    time.sleep(1.7)
    block(token5,2,1,status=409)
    # Compare native recall/morph blocks against independently mapped direct
    # controls, including rejection without sequence or engine advancement.
    checks = sounding = 0
    for i in range(4):
        for j in range(4):
            a = dict(p=i,e=104,d=0,c=127)
            b = dict(p=j,e=19,d=7,c=13)
            positions = [0,31,63,64,95,127,64,0]
            def mapped(q):
                return dict(p=i if q<64 else j, **{k:(a[k]*(127-q)+b[k]*q+63)//127 for k in ('e','d','c')})
            def direct(token,seq,patch,event=0):
                return post('/block',dict(token=token,seq=seq,n=48,v=113,event=event,**patch))
            def audio(r):
                return r['pcm'],r['levels']
            ref=open_session()
            expected=[audio(direct(ref,0,a,1))]
            last=a
            for k,q in enumerate(positions):
                expected.append(audio(direct(ref,2*k+1,last,1)))
                expected.append(audio(direct(ref,2*k+2,mapped(q))))
                last=mapped(q)
            expected.append(audio(direct(ref,17,b)))
            token=open_session()
            seq=0
            def mem(op,path='/memory',status=200,**kw):
                return post(path,dict(token=token,seq=seq,op=op,**kw),status)
            assert mem('clear')['slots']==[None,None]; seq+=1
            mem('morph','/memory-block',400,position=64)
            got=[audio(direct(token,seq,a,1))]; seq+=1
            assert mem('capture',slot=0)['slots']==[a,None]; seq+=1
            assert mem('store',slot=1,**b)['slots']==[a,b]; seq+=1
            mem('store',status=400,slot=True,**b)
            mem('store',status=400,slot=1,**dict(b,c=128))
            mem([],status=400)
            post('/memory',dict(token=ref,seq=seq,op='clear'),409)
            last=a
            for q in positions:
                got.append(audio(direct(token,seq,last,1))); seq+=1
                post('/memory-block',dict(token=token,seq=seq-1,op='morph',position=q),409)
                mem('morph','/memory-block',400,position=128)
                r=mem('morph','/memory-block',position=q)
                assert r['patch']==mapped(q) and r['seq']==seq
                got.append(audio(r)); seq+=1
                last=mapped(q)
            r=mem('recall','/memory-block',slot=1)
            assert r['patch']==b
            got.append(audio(r)); seq+=1
            assert got==expected,(i,j)
            checks+=len(got); sounding+=sum(any(base64.b64decode(p)) for p,_ in got)
            post('/panic',{'token':token})
            mem('recall','/memory-block',409,slot=0)
            token=open_session(); seq=0
            assert mem('inspect')['slots']==[a,b]; seq+=1
            r=mem('recall','/memory-block',slot=0)
            assert not any(pcm(r)) and r['levels']==[0]*6
    assert sounding>=128
    print(f'PASS {checks} native HTTP PCM/modal comparisons ({sounding} sounding), 16 ordered pairs and 16 silent reconnects')
    print('PASS persistent PCM repeat, live damping, modal coupling, release, panic, version/range/sequence, lease and stale reconnect')
finally:
    proc.terminate()
    proc.wait(timeout=5)

# Direct bridge witness: no reset between panic and the subsequent render.
import ctypes as C
lib = C.CDLL(str(pathlib.Path(sys.argv[1]).resolve(strict=True)))
lib.live_block.argtypes = [C.c_uint]*7+[C.POINTER(C.c_int16),C.POINTER(C.c_uint32)]
lib.live_block.restype = None
for fn in (lib.live_reset,lib.live_panic):
    fn.argtypes = []
    fn.restype = None
samples = (C.c_int16*1200)()
levels = (C.c_uint32*6)()
lib.live_reset()
lib.live_block(2,76,0,90,48,110,1,samples,levels)
assert any(samples) and any(levels)
print('strike peak',max(map(abs,samples)),'mode levels',list(levels))
lib.live_panic()
lib.live_block(2,76,0,90,48,110,0,samples,levels)
assert not any(samples) and not any(levels)
print('PASS direct panic PCM and modal zero')
