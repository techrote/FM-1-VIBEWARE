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
