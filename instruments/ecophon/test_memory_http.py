"""Actual local HTTP/native memory control versus explicit-control oracle."""
import base64
import json
import sys
import threading
import urllib.error
import urllib.request
from live import make_server

A = (240, 210, 15)
B = (35, 40, 175)
C = (120, 99, 70)

with make_server(sys.argv[1], 0) as server:
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    base = 'http://127.0.0.1:' + str(server.server_address[1])

    def post(path, body, status=200, authorized=True):
        headers = {'Content-Type': 'application/json'}
        if authorized:
            headers['X-Ecophon-Fixture'] = '1'
        req = urllib.request.Request(base + path, json.dumps(body).encode(), headers)
        try:
            response = urllib.request.urlopen(req, timeout=5)
        except urllib.error.HTTPError as exc:
            response = exc
        with response:
            assert response.code == status, (path, response.code, status)
            return json.load(response)

    def reset(preset):
        return post('/reset', {'seed': 42, 'preset': preset})['generation']

    def step(gen, controls, frozen=0):
        f, s, p = controls
        return post('/step', dict(generation=gen, fertility=f, sharing=s, pressure=p, frozen=frozen))

    def memory(gen, action, slot=None, status=200):
        body = dict(generation=gen)
        if slot is not None:
            body['slot'] = slot
        return post('/memory/' + action, body, status)

    def comparable(result):
        result = dict(result)
        del result['generation']
        assert len(base64.b64decode(result['pcm'], validate=True)) == 4800
        assert result['state_source'] == 'local native core (not device telemetry)'
        return result

    def mix(a, b, n):
        return tuple((x * (40-n) + y * n) // 40 for x,y in zip(a,b))

    try:
        comparisons = sounding = 0
        g = reset(0)
        memory(g, 'recall', 0, 409)  # initially empty
        for preset in range(3):
            for takeover in (False, True):
                g = reset(preset)
                actual = [step(g,A)]
                memory(g,'capture',0)
                actual.append(step(g,B))
                memory(g,'capture',1)
                memory(g,'recall',0)
                expected = [A,B]
                for n in range(1,46):
                    if n == 8:
                        memory(g,'capture',0)  # detached target must not change
                        memory(g-1,'recall',1,409)
                        memory(g,'capture',2,400)
                        post('/memory/step',dict(generation=g,slot=0),400)
                        post('/memory/step',dict(generation=g),403,False)
                    if takeover and n == 15:
                        actual.append(step(g,C))
                    else:
                        actual.append(memory(g,'step'))
                    expected.append(C if takeover and n>=15 else mix(B,A,min(n,40)))
                memory(g,'recall',1)
                actual.append(step(g,C,1))  # freeze and manual control cancel recall
                expected.append(C)
                memory(g,'recall',1,409)
                actual.append(memory(g,'step'))
                expected.append(C)
                post('/panic',dict(generation=g))
                for action,slot in [('capture',0),('recall',0),('step',None)]:
                    memory(g,action,slot,409)
                h = reset(preset)
                for i,(got,controls) in enumerate(zip(actual,expected)):
                    want = step(h,controls,int(i>=len(expected)-2))
                    assert comparable(got)==comparable(want),(preset,takeover,i)
                    comparisons+=1
                    sounding+=any(base64.b64decode(got['pcm']))
                # Retained B is still available in the new generation; old generation is not.
                memory(g,'recall',1,409)
                step(h,A)
                memory(h,'recall',1)
                assert memory(h,'step')['controls']==list(mix(A,B,1))
        assert comparisons==294 and sounding>0
        print(f'PASS HTTP/native memory: {comparisons} exact PCM/state blocks, {sounding} sounding; detached recall, manual/freeze, stale/panic and retained slot')
    finally:
        server.shutdown()
        worker.join()
