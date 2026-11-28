"""Independently qualify the original Ecophon artifact and exact-source rebuild."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import stat
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile

WAVS = (
    "6971486e4a5736a93cc1dda9ed4dc5675edf79f828de1e14a1fad70f2fc9ac88",
    "e6c974d5988449d7880838223cc11a835ffba764ba67854e46558e2f12618b74",
    "155158bdf0d51a2bed10948d9f1bf226d9f6c57e9b8f272c5c6ddcfb99e8bc7b",
    "73e1093fb5103213af9f3ddccf52bce37ad1fbbb9aa5b3a1375c5c2cbcf3a41f",
)
SOURCE = ("ecophon.c", "ecophon.h", "fixture.c", "live.py", "live.html", "profile.json", "test_live.py", "README.md")
def sha(data):
    return hashlib.sha256(data).hexdigest()

ECO_SUCCESSOR_FILES = (
    "performances/habitat-arc.wav", "performances/steady-control.wav",
    "performances/frozen-control.wav", "performances/performance.json",
    "performances/companion-replay.json", "feedback/population-feedback.wav",
    "feedback/population-steady.wav", "feedback/population-feedback.json",
    "feedback/population-steady.json", "feedback/population-summary.json",
)

ECO_ARC_FILES = tuple(f'live-arc/{p}-{a}.wav' for p in range(3) for a in ('arc','steady','takeover')) + ('live-arc/live-arc-replay.json',)

def extract(archive, dest, expected, ignored=(), allowed_nested=()):
    assert sha(archive.read_bytes()) == expected, "original archive digest mismatch"
    with zipfile.ZipFile(archive) as z:
        names = z.namelist()
        assert len(names) == len(set(n.casefold() for n in names)), "duplicate name"
        kept = [n for n in names if n not in ignored]
        assert all(n in allowed_nested or (n and n not in (".", "..") and "/" not in n and chr(92) not in n and ":" not in n) for n in kept), "unexpected archive path"
        assert all(not stat.S_ISLNK(i.external_attr >> 16) for i in z.infolist()), "symlink archive entry"
        assert set(allowed_nested).issubset(kept), "missing required nested payload"
        assert sum(i.file_size for i in z.infolist()) < 30_000_000
        z.extractall(dest, members=kept)

def witness(root, library):
    # Exercise the actual packaged entry point in a separate process.
    p = subprocess.Popen([sys.executable, str(root/"live.py"), "--library", str(library), "--port", "0"],
                         cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
                         env=dict(os.environ, PYTHONIOENCODING="utf-8"))
    try:
        line = p.stdout.readline()
        assert line.startswith("Open http://127.0.0.1:"), line
        url = line.split()[1]
        def post(path, data, expected=200):
            req = urllib.request.Request(url+path, json.dumps(data).encode(), {"Content-Type":"application/json","X-Ecophon-Fixture":"1"})
            try:
                res = urllib.request.urlopen(req,timeout=5)
            except urllib.error.HTTPError as e:
                res = e
            with res:
                assert res.status == expected, (path,res.status,expected)
                return json.load(res)
        def reset(preset=0):
            return post("/reset",{"seed":42,"preset":preset})["generation"]
        def step(g, f=180, s=200, pressure=40, frozen=0):
            d=post("/step",{"generation":g,"fertility":f,"sharing":s,"pressure":pressure,"frozen":frozen})
            assert d["state_source"]=="local native core (not device telemetry)"
            pcm=base64.b64decode(d.pop("pcm"),validate=True)
            assert d["rate"]==24000 and len(pcm)==4800
            assert max(map(abs,struct.unpack("<2400h",pcm)))<=24000
            assert len(d["agents"])==8 and len(d["resources"])==4
            assert all(0<=x<=4096 for x in d["resources"])
            d.pop("generation")
            return d,pcm
        def trajectory(f,s,pressure,frozen=0):
            g=reset()
            blocks=[]
            for i in range(51):
                d,pcm=step(g,f,s,pressure,frozen)
                assert d["ticks"]==(i+1)*10
                blocks.append(pcm)
            raw=b"".join(blocks)
            assert any(raw)
            return {"pcm_sha256":sha(raw),"end_state":d}
        a=trajectory(180,200,40)
        assert a==trajectory(180,200,40)
        b=trajectory(0,0,255)
        c=trajectory(180,200,40,1)
        assert len({x["pcm_sha256"] for x in (a,b,c)})==3
        assert b["end_state"]["deaths"]>a["end_state"]["deaths"]
        assert c["end_state"]["births"]==c["end_state"]["gifts"]==0
        g=reset()
        first=step(g)
        g2=reset()
        post("/step",dict(generation=g,fertility=180,sharing=200,pressure=40,frozen=0),409)
        post("/step",dict(generation=g2,fertility=180,sharing=200,pressure=256,frozen=0),400)
        assert step(g2)==first
        assert post("/panic",{"generation":g2})["muted"]
        post("/step",dict(generation=g2,fertility=180,sharing=200,pressure=40,frozen=0),409)
        assert step(reset())==first
        return {"normal":a,"harsh":b,"frozen":c,"reset_stale_invalid_panic":"PASS"}
    finally:
        p.terminate()
        p.communicate(timeout=10)

def main():
    p=argparse.ArgumentParser()
    p.add_argument("source",type=Path)
    p.add_argument("archive",type=Path)
    p.add_argument("digest")
    p.add_argument("--successor", action="store_true")
    p.add_argument("--live-arc", action="store_true")
    args=p.parse_args()
    assert not args.live_arc or args.successor
    source=args.source.resolve()/ "instruments/ecophon"
    windows=sys.platform=="win32"
    lib="ecof.dll" if windows else "libecof.so"
    exe="ecophon.exe" if windows else "ecophon"
    with tempfile.TemporaryDirectory(prefix="QA Ecophon path with spaces ") as td:
        root=Path(td)
        extracted=root/"original package"
        extracted.mkdir()
        extract(args.archive,extracted,args.digest, allowed_nested=(ECO_SUCCESSOR_FILES + (ECO_ARC_FILES if args.live_arc else ())) if args.successor else ())
        for name in SOURCE + (("live_arc_fixture.py",) if args.live_arc else ()):
            assert (extracted/name).read_bytes()==(source/name).read_bytes(),name
        for i,h in enumerate(WAVS):
            assert sha((extracted/f"{i}.wav").read_bytes())==h
        # ZIP extraction does not preserve execute bits on every platform.
        if not windows:
            (extracted/exe).chmod(0o755)
        rebuilt=root/"independent rebuild"
        rebuilt.mkdir()
        for name in SOURCE+("host.c","test.c"):
            shutil.copy2(source/name,rebuilt/name)
        flags=["gcc","-std=c11","-O2","-Wall","-Wextra","-Werror"]
        if not windows:
            flags+=["-fsanitize=undefined","-fno-sanitize-recover=all"]
        def run(cmd):
            subprocess.run(cmd,cwd=rebuilt,check=True,timeout=120)
        run(flags+["ecophon.c","test.c","-o","qa-test.exe"])
        run([str(rebuilt/"qa-test.exe")])
        run(flags+["ecophon.c","host.c","-o",exe])
        run(flags+["-shared"]+([] if windows else ["-fPIC"])+["ecophon.c","fixture.c","-o",lib])
        for label,location in (("original",extracted),("rebuilt",rebuilt)):
            for i,h in enumerate(WAVS):
                out=root/f"{label}-{i}.wav"
                subprocess.run([str(location/exe),str(out),str(i),"42","30"],cwd=location,check=True,timeout=120)
                assert sha(out.read_bytes())==h,(label,i)
        original=witness(extracted,extracted/lib)
        fresh=witness(rebuilt,rebuilt/lib)
        assert original==fresh,"extracted and rebuilt actual HTTP results diverged"
        print(json.dumps({"archive_sha256":args.digest,"wav_sha256":WAVS,"extracted_library_sha256":sha((extracted/lib).read_bytes()),"extracted_executable_sha256":sha((extracted/exe).read_bytes()),"witness":original},sort_keys=True))
if __name__=="__main__":
    main()
