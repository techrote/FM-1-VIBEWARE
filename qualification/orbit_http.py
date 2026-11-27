"""Independent host-only HTTP qualification of a checked-out Grimoire candidate."""
import base64
import hashlib
import http.client
import json
import os
from pathlib import Path
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time


def run(source):
    with tempfile.TemporaryDirectory(prefix="VIBEWARE QA package ") as directory:
        package = Path(directory)
        core = source / "instruments/grimoire"
        ui = source / "companion/grimoire"
        library = package / ("orbit.dll" if os.name == "nt" else "orbit.so")
        flags = [] if os.name == "nt" else ["-fPIC", "-fsanitize=undefined", "-fno-sanitize-recover=all"]
        subprocess.run(["gcc", "-std=c11", "-O2", "-Wall", "-Wextra", "-Werror", "-shared", *flags,
                        str(core / "orbit.c"), str(ui / "session.c"), "-o", str(library)], check=True)
        for name in ("host.py", "index.html", "gesture.js", "profile.json"):
            if (ui / name).exists():
                shutil.copy2(ui / name, package / name)
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        log = package / "host.log"
        with log.open("w+") as stream:
            proc = subprocess.Popen([sys.executable, str(package / "host.py"), str(library), "--port", str(port)],
                                    cwd=package.parent, stdout=stream, stderr=stream)
            def request(body, expected=200, path="/api", origin=None, content_type="application/json"):
                conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
                headers = {"Content-Type": content_type, "Origin": origin or f"http://127.0.0.1:{port}"}
                try:
                    conn.request("POST", path, body if isinstance(body, bytes) else json.dumps(body), headers)
                    response = conn.getresponse()
                    data = response.read()
                    assert response.status == expected, (body, response.status, expected, data)
                    return json.loads(data) if expected == 200 else None
                finally:
                    conn.close()
            try:
                deadline = time.monotonic() + 10
                while True:
                    try:
                        with socket.create_connection(("127.0.0.1", port), timeout=.2):
                            break
                    except OSError:
                        assert proc.poll() is None and time.monotonic() < deadline, "server did not start"
                        time.sleep(.05)
                def connect():
                    d = request({"kind": "connect", "version": 1})
                    assert d["version"] == 1 and d["instrument_id"] == "grimoire.orbit-gate"
                    assert d["state_source"] == "local native core"
                    return d["generation"]
                g = connect()
                def event(op, a=0, b=0, expected=200, generation=None):
                    return request(dict(kind="event", generation=g if generation is None else generation,
                                        op=op, a=a, b=b), expected)
                def audio():
                    d = request(dict(kind="audio", generation=g))
                    raw = base64.b64decode(d["pcm"], validate=True)
                    assert len(raw) == 2400 and d["rate"] == 24000 and d["state_source"] == "local native core"
                    assert len(d["phase"]) == 3 and all(0 <= v <= 65535 for v in d["phase"])
                    assert max(map(abs, struct.unpack("<1200h", raw))) <= 28000
                    return d, raw
                def witness(preset, x, y):
                    event(3, preset); event(1, x, y); event(2, 1)
                    d, raw = audio()
                    assert (d["preset"], d["x"], d["y"], d["gate"]) == (preset, x, y, 1)
                    assert any(raw) and d["energy"] > 0
                    return raw
                a = witness(0, 0, 0)
                assert a == witness(0, 0, 0), "reset not deterministic"
                b = witness(0, 127, 0)
                c = witness(0, 0, 127)
                d = witness(1, 0, 0)
                e = witness(2, 0, 0)
                hashes = [hashlib.sha256(v).hexdigest() for v in (a,b,c,d,e)]
                assert len(set(hashes)) == 5, "control/preset audio alias"
                # Actual HTTP failures, not direct Engine.handle mocks.
                request({"kind":"connect","version":99}, 400)
                request({"kind":"connect","version":True}, 400)
                request(b"{bad", 400)
                request(b"[]", 400)
                request(b"x" * 1025, 400)
                request(dict(kind="event",generation=g,op=4,a=0,b=0), 403, origin="https://invalid.example")
                request(dict(kind="event",generation=g,op=4,a=0,b=0), 403, content_type="text/plain")
                event(1,128,0,400); event(2,2,0,400); event(99,0,0,400)
                assert audio()[0]["gate"] == 1, "invalid requests disrupted session"
                event(2,0)
                for _ in range(5):
                    tail = audio()[1]
                assert not any(tail), "release tail never became silent"
                event(2,1); assert any(audio()[1]); event(4)
                assert not any(audio()[1]), "panic not immediate"
                event(2,1); assert any(audio()[1])
                time.sleep(1.8)
                request(dict(kind="audio",generation=g),400)
                old=g; g=connect(); assert g!=old
                event(2,1,expected=400,generation=old)
                assert not any(audio()[1]), "stale replay or reconnect not silent"
                request(dict(kind="disconnect",generation=g))
                request(dict(kind="audio",generation=g),400)
                print(json.dumps({"gate":"host HTTP native-core only","pcm_sha256":hashes,
                                  "control_cases":5,"malformed_rejections":10,
                                  "lease_panic_release_reconnect":"PASS"}, indent=2))
            finally:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill(); proc.wait()
                stream.seek(0)
                if "runtime error:" in stream.read():
                    raise AssertionError("UBSan runtime error in child")


if __name__ == "__main__":
    run(Path(sys.argv[1]).resolve())
