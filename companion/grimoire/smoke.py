import base64, sys, json, pathlib
from host import Engine
clock=[0.0]
e=Engine(sys.argv[1],clock=lambda:clock[0])
g=e.handle({"kind":"connect","version":1})["generation"]
def event(op,a=0,b=0):
    return e.handle(dict(kind="event",generation=g,op=op,a=a,b=b))
def audio():
    return base64.b64decode(e.handle(dict(kind="audio",generation=g))["pcm"])
event(1,70,100);event(2,1);assert any(audio())
event(4);assert not any(audio())
e.handle(dict(kind="disconnect",generation=g))
h=e.handle({"kind":"connect","version":1})["generation"]
assert h!=g
try:event(2,1)
except ValueError:pass
else:raise AssertionError("stale accepted")
assert not any(base64.b64decode(e.handle(dict(kind="audio",generation=h))["pcm"]))
print("actual-core ctypes companion session PASS")
# A wrong-version connect must not hijack an active session.
g=h
event(2,1);assert any(audio())
try:e.handle({"kind":"connect","version":99})
except ValueError:pass
else:raise AssertionError("bad version accepted")
assert any(audio())
# Invalid events do not refresh lease. Expired sessions are immediately muted.
clock[0]=1.4
try:event(2,2)
except ValueError:pass
else:raise AssertionError("bad gate accepted")
clock[0]=1.51
assert e.expire() and not e.s.connected and not e.s.core.gate and e.s.core.env==0
try:audio()
except ValueError:pass
else:raise AssertionError("expired session accepted")
g=e.handle({"kind":"connect","version":1})["generation"]
assert not any(audio())
event(1,127,0);event(2,1);assert any(audio())
clock[0]+=1.0;assert any(audio())
clock[0]+=1.0;assert not e.expire()
clock[0]+=.51;assert e.expire()
profile=json.loads(pathlib.Path(__file__).with_name("profile.json").read_text())
assert profile["profile_version"]==1 and profile["instrument_id"]=="grimoire.orbit-gate"
g=e.handle({"kind":"connect","version":1})["generation"]
event(3,2)
d=e.handle(dict(kind="audio",generation=g))
assert d["preset"]==2 and d["x"]==48 and d["y"]==70 and d["state_source"]=="local native core"
print("lease, invalid version, no stale replay, semantic profile defaults PASS")
