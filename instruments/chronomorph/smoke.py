import hashlib
import http.server
import pathlib
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
import wave
import io
from server import Handler

with http.server.HTTPServer(('127.0.0.1',0),Handler) as s:
    s.engine=str(pathlib.Path(sys.argv[1]).resolve(strict=True))
    t=threading.Thread(target=s.serve_forever,daemon=True); t.start()
    root=f'http://127.0.0.1:{s.server_port}'
    q=dict(preset=0,seed=17,bpm=112,warp=24,variation=12,seconds=3,len0=7,mask0=73,len1=5,mask1=21,len2=11,mask2=1321)
    def get(params):
        with urllib.request.urlopen(root+'/render?'+urllib.parse.urlencode(params),timeout=12) as r:
            assert r.headers['X-Clock-State']; data=r.read()
            with wave.open(io.BytesIO(data)) as w: assert (w.getframerate(),w.getnframes(),w.getnchannels())==(24000,72000,1)
            return hashlib.sha256(data).hexdigest()
    try:
        assert b'Chronomorph' in urllib.request.urlopen(root+'/',timeout=5).read()
        a=get(q); assert get(q)==a; assert get(dict(q,warp=0))!=a; assert get(dict(q,mask0=0))!=a
        for bad in (dict(q,warp=61),dict(q,mask0=128),dict(q,seconds=21),dict(q,unknown=1),dict(q,seed=99999999999999999999999999)):
            try: get(bad); raise AssertionError('invalid accepted')
            except urllib.error.HTTPError as e: assert e.code==400
        print('real HTTP: deterministic PCM, warp/edit contrast, 5 invalid requests PASS')
    finally: s.shutdown(); t.join()
