import base64, sys
from host import Engine
e=Engine(sys.argv[1])
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
