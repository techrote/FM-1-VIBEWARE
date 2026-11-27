"""QA #7: compare original immutable native archives with independent builds."""
import argparse
import base64
import hashlib
import http.client
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import time
import wave

from ecophon_archive import extract

def sha(data):
    return hashlib.sha256(data).hexdigest()

def run(cmd, cwd):
    subprocess.run([str(x) for x in cmd], cwd=cwd, check=True, timeout=120)

def witness(root, lib, instrument):
    log = root / "qa-http.log"
    with log.open("w", encoding="utf-8") as stream:
        p = subprocess.Popen([sys.executable, str(root/"live.py"), str(root/lib), "--port", "0"],
                             cwd=root, stdout=stream, stderr=stream)
        try:
            deadline = time.monotonic()+10
            while True:
                lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
                urls = [s.split("http://127.0.0.1:",1)[1].strip() for s in lines if "http://127.0.0.1:" in s]
                if urls:
                    port = int(urls[0])
                    break
                assert p.poll() is None and time.monotonic() < deadline, lines
                time.sleep(.05)
            def post(path, data, status=200):
                c = http.client.HTTPConnection("127.0.0.1",port,timeout=5)
                try:
                    c.request("POST",path,json.dumps(data),{"Content-Type":"application/json"})
                    res = c.getresponse()
                    raw = res.read()
                    assert res.status == status, (path, res.status, status, raw)
                    return json.loads(raw) if status==200 else None
                finally:
                    c.close()
            gen = instrument == "chronomorph"
            def session(version=1, status=200):
                body = {"version":version,"seed":913,"preset":1} if gen else {"version":version}
                reply = post("/session" if gen else "/open",body,status)
                return reply["token"] if status==200 else None
            def block(token, index, status=200, **changes):
                if gen:
                    q = dict(token=token,seq=index+1,bpm=97,warp=0,variation=20,
                             playing=1,patterns=[[7,73],[5,21],[11,1321]])
                else:
                    q = dict(token=token,seq=index,p=2,e=83,d=30,c=100,n=57,v=103,
                             event=1 if index==0 else 0)
                q.update(changes)
                return post("/block",q,status)
            def pcm(d):
                raw = base64.b64decode(d["pcm"],validate=True)
                assert len(raw)==2400
                return raw
            def trajectory(changes):
                token = session()
                raw = bytearray()
                for i in range(60):
                    d = block(token,i,**(changes if i>=5 else {}))
                    raw.extend(pcm(d))
                    if gen:
                        assert len(d["lanes"])==3 and all(len(v)==5 for v in d["lanes"])
                    else:
                        assert len(d["levels"])==6 and all(0<=x<=131070 for x in d["levels"])
                assert any(raw)
                state = {k:v for k,v in d.items() if k!="pcm"}
                return {"hash":sha(raw),"state":state,"peak":max(map(abs,struct.unpack("<72000h",raw)))}
            baseline=trajectory({})
            assert baseline==trajectory({})
            if gen:
                comparisons={ "tempo":trajectory({"bpm":181}), "warp":trajectory({"warp":-59}),
                              "pattern":trajectory({"patterns":[[7,0],[5,21],[11,1321]]})}
            else:
                comparisons={"damping":trajectory({"d":127})}
                # Coupling ablation must start at excitation, not after energy already transferred.
                token=session()
                coupled=block(token,0)
                token=session()
                isolated=block(token,0,c=0)
                assert any(coupled["levels"][3:]) and isolated["levels"][3:]==[0,0,0]
                assert pcm(coupled)!=pcm(isolated)
                comparisons["coupling"]={"hash":sha(pcm(isolated)),"coupled_hash":sha(pcm(coupled))}
            assert all(v["hash"]!=baseline["hash"] for v in comparisons.values())
            token=session()
            first=block(token,0)
            session(2,400)
            block(token,0,status=409)
            block(token,1,status=400,**({"bpm":221} if gen else {"d":128}))
            second=block(token,1)
            fresh=session()
            block(token,2,status=409)
            assert block(fresh,0)==first and block(fresh,1)==second
            if gen:
                paused=block(fresh,2,playing=0)
                assert not any(pcm(paused)) and paused["lanes"]==second["lanes"]
                assert block(fresh,3,playing=0)["lanes"]==paused["lanes"]
            else:
                for i in range(2,14):
                    tail=block(fresh,i,d=127,event=2 if i==2 else 0)
                assert not any(pcm(tail))
            post("/panic",{"token":fresh})
            block(fresh,14,status=409)
            current=session()
            assert block(current,0)==first
            time.sleep(1.7)
            block(current,1,status=409)
            assert block(session(),0)==first
            return {"baseline":baseline,"comparisons":comparisons,
                    "invalid_stale_panic_release_or_pause_expiry":"PASS"}
        finally:
            p.terminate()
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
                p.wait(timeout=5)
            assert "runtime error:" not in log.read_text(encoding="utf-8",errors="replace"), "UBSan"

def main():
    p=argparse.ArgumentParser()
    p.add_argument("instrument",choices=["chronomorph","xenoresonator"])
    p.add_argument("source",type=Path)
    p.add_argument("archive",type=Path)
    p.add_argument("digest")
    a=p.parse_args()
    source=a.source.resolve()/"instruments"/a.instrument
    gen=a.instrument=="chronomorph"
    windows=os.name=="nt"
    lib=("chronomorph-live.dll" if windows else "chronomorph-live.so") if gen else "live.dll"
    exe="chronomorph.exe" if gen else "render.exe"
    core="chrono.c" if gen else "xeno.c"
    cli="audition.c" if gen else "render.c"
    revision="source-revision.txt" if gen else "SOURCE-REVISION.txt"
    with tempfile.TemporaryDirectory(prefix="QA native archive with spaces ") as td:
        root=Path(td)
        original=root/"original package"
        rebuilt=root/"clean rebuild"
        original.mkdir(); rebuilt.mkdir()
        extract(a.archive.resolve(),original,a.digest)
        checked=[]
        # Text checkout can use CRLF on Windows. Normalize only line endings.
        for path in sorted(source.iterdir()):
            if not path.is_file():
                continue
            shutil.copy2(path,rebuilt/path.name)
            if (original/path.name).exists():
                assert path.read_bytes().replace(b"\r\n",b"\n")== (original/path.name).read_bytes().replace(b"\r\n",b"\n"),path.name
                checked.append(path.name)
        assert set([core,cli,"live.py","live.html","live_bridge.c","profile.json"]).issubset(checked)
        for f in (exe,lib):
            assert (original/f).is_file()
        if not windows:
            (original/exe).chmod(0o755)
        flags=["gcc","-std=c11","-O2","-Wall","-Wextra","-Werror"]
        if not windows:
            flags+=["-fsanitize=undefined","-fno-sanitize-recover=all"]
        run(flags+[core,cli,"-o",exe],rebuilt)
        run(flags+["-shared"]+(["-Wl,--export-all-symbols"] if windows else ["-fPIC"])+[core,"live_bridge.c","-o",lib],rebuilt)
        if gen:
            run([rebuilt/exe,"--test"],rebuilt)
            cases=[
                ("glass-lattice.wav",["--render","0","17","112","24","12","12","7","73","5","21","11","1321"]),
                ("broken-meridian.wav",["--render","1","17","142","-32","12","12","5","21","9","297","7","85"]),
                ("slow-eclipse.wav",["--render","2","17","84","48","12","12","9","293","7","73","13","4693"])]
        else:
            run(flags+[core,"test.c","-o","qa-test.exe"],rebuilt)
            run([rebuilt/"qa-test.exe"],rebuilt)
            cases=[(f"material{i}.wav",[str(i),"76","12","90","48","110","phrase"]) for i in range(4)]
            cases.append(("uncoupled.wav",["2","76","12","0","48","110","phrase"]))
        hashes={}
        for name,args in cases:
            expected=(original/name).read_bytes()
            for label,where in (("original",original),("fresh",rebuilt)):
                out=root/(label+"-"+name)
                arguments=[args[0],out,*args[1:]] if gen else [out,*args]
                run([where/exe,*arguments],where)
                assert out.read_bytes()==expected,(label,name)
            with wave.open(str(original/name),"rb") as w:
                assert w.getsampwidth()==2 and w.getnframes()>0
                raw=w.readframes(w.getnframes())
                assert any(raw)
                hashes[name]={"wav_sha256":sha(expected),"pcm_sha256":sha(raw),"rate":w.getframerate(),"frames":w.getnframes()}
        assert len({v["pcm_sha256"] for v in hashes.values()})==len(cases)
        old=witness(original,lib,a.instrument)
        new=witness(rebuilt,lib,a.instrument)
        assert old==new,"package and clean native rebuild diverged"
        print(json.dumps({"instrument":a.instrument,"archive_sha256":a.digest,
            "source_receipt":(original/revision).read_text().strip(),"source_files_checked":checked,
            "binary_hashes":{f:sha((original/f).read_bytes()) for f in (exe,lib)},
            "wavs":hashes,"http":old},sort_keys=True))

if __name__=="__main__":
    main()
