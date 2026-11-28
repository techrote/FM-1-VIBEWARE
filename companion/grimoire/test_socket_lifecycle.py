"""Real loopback HTTP + native PCM lifecycle; not a device transport test."""
import base64
import http.client
import json
import pathlib
import socket
import subprocess
import sys
import time
import urllib.request

def raw_post(port, body, lengths, extra=()):
    headers=['POST /api HTTP/1.0','Host: 127.0.0.1','Content-Type: application/json']
    headers += ['Content-Length: '+str(n) for n in lengths]+list(extra)
    with socket.create_connection(('127.0.0.1',port),timeout=3) as sock:
        sock.sendall(('\r\n'.join(headers)+'\r\n\r\n').encode('ascii')+body)
        sock.shutdown(socket.SHUT_WR)
        response=http.client.HTTPResponse(sock);response.begin()
        return response.status,json.loads(response.read())

def run(library):
    root=pathlib.Path(__file__).resolve().parent
    with socket.socket() as s:
        s.bind(('127.0.0.1',0));port=s.getsockname()[1]
    with subprocess.Popen([sys.executable,str(root/'host.py'),str(library),'--port',str(port)],
                          stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL) as host:
        try:
            for _ in range(100):
                try:
                    with urllib.request.urlopen(f'http://127.0.0.1:{port}/',timeout=.2):break
                except OSError:
                    assert host.poll() is None
                    time.sleep(.05)
            else:raise AssertionError('host did not start')
            def post(d,expected=200):
                body=json.dumps(d).encode()
                status,reply=raw_post(port,body,[len(body)])
                assert status==expected,(d,status,reply)
                return reply
            def connect():return post(dict(kind='connect',version=1))['generation']
            g=connect()
            def call(kind,expected=200,**kw):return post(dict(kind=kind,generation=g,**kw),expected)
            def audio(sounding):
                out=call('audio');pcm=base64.b64decode(out['pcm'],validate=True)
                assert len(pcm)==2400 and out['rate']==24000
                assert any(pcm)==sounding,(out['gate'],out['env'])
                return out
            assert audio(False)['gate']==0
            body=json.dumps(dict(kind='event',generation=g,op=2,a=1,b=0)).encode()
            invalid=[([len(body)+1],()),([len(body),len(body)],()),
                     ([len(body)],('Transfer-Encoding: chunked',)),([],()),
                     (['+'+str(len(body))],()),(['00000'],()),([1025],())]
            for lengths,extra in invalid:
                status,_=raw_post(port,body,lengths,extra)
                assert status==400,(lengths,extra,status)
                assert audio(False)['gate']==0
            call('event',op=2,a=1,b=0)
            assert audio(True)['gate']==1
            call('ribbon',action='speed',value=4)
            assert audio(True)['ribbon']['speed']==4
            call('event',op=4,a=0,b=0)
            assert audio(False)['ribbon']['speed']==0
            call('event',op=2,a=1,b=0)
            call('ribbon',action='speed',value=2)
            assert audio(True)['gate']==1
            # Read-only snapshots do not keep the session alive.
            # Avoid tight wall-clock margins: a full lease without any mutation.
            call('ribbon',action='state')
            time.sleep(1.8)
            call('audio',expected=400)
            call('event',expected=400,op=2,a=1,b=0)
            old=g;g=connect()
            assert g!=old
            post(dict(kind='ribbon',generation=old,action='speed',value=4),400)
            out=audio(False)
            assert out['gate']==0 and out['ribbon']['speed']==0 and out['ribbon']['has_sketch']==0
            call('event',op=2,a=1,b=0)
            assert audio(True)['gate']==1
            call('disconnect')
            call('audio',expected=400)
            g=connect()
            assert audio(False)['gate']==0
            print('PASS: seven malformed frames, native silence and sounding PCM, panic, lease expiry, stale rejection, reconnect and disconnect')
        finally:
            host.terminate();host.wait(timeout=5)

if __name__=='__main__':run(pathlib.Path(sys.argv[1]).resolve())
