"""Source-only Windows native audition selector; no firmware, target emulator or downloads."""
import argparse
import hashlib
import http.client
import io
import json
from pathlib import Path
import re
import socket
import stat
import subprocess
import sys
import tempfile
import time
import webbrowser
import zipfile

BASE="https://github.com/techrote/FM-1-VIBEWARE"
LIMIT=50_000_000
CACHE="__pycache__/host.cpython-312.pyc"
ECO_PAYLOADS=frozenset((
    "performances/habitat-arc.wav", "performances/steady-control.wav",
    "performances/frozen-control.wav", "performances/performance.json",
    "performances/companion-replay.json", "feedback/population-feedback.wav",
    "feedback/population-steady.wav", "feedback/population-feedback.json",
    "feedback/population-steady.json", "feedback/population-summary.json",
))

ECO_LIVE_ARC = frozenset(f'live-arc/{p}-{a}.wav' for p in range(3) for a in ('arc','steady','takeover')) | {'live-arc/live-arc-replay.json'}

def catalogue():
    d=json.loads(Path(__file__).with_name("native-packages.json").read_text(encoding="utf-8"))
    if d["schema"]!=1 or d["kind"]!="native-host-only":
        raise ValueError("Unknown catalogue")
    return {p["id"]:p for p in d["packages"]}

def verified_extract(archive,dest,p):
    if archive.stat().st_size>LIMIT:
        raise ValueError("Archive too large")
    raw=archive.read_bytes()
    if hashlib.sha256(raw).hexdigest()!=p["sha256"]:
        raise ValueError("Original ZIP SHA-256 mismatch; download the exact pinned archive")
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        infos=z.infolist()
        if sum(i.file_size for i in infos)>LIMIT or len(infos)>200:
            raise ValueError("Expanded archive exceeds bounds")
        seen=set()
        allowed_nested=ECO_PAYLOADS if p["id"]=="ecophon" else frozenset()
        if p.get("ecophon_live_arc", False):
            if p["id"]!="ecophon" or p["ecophon_live_arc"] is not True:
                raise ValueError("Invalid Ecophon live-arc inventory flag")
            allowed_nested=allowed_nested | ECO_LIVE_ARC
        found_nested=set()
        for i in infos:
            name=i.filename
            key=name.casefold()
            if key in seen:
                raise ValueError("Duplicate archive entry")
            seen.add(key)
            if p["id"]=="grimoire" and name==CACHE:
                continue
            if name in allowed_nested:
                if stat.S_ISLNK(i.external_attr>>16) or i.is_dir():
                    raise ValueError("Unexpected nested archive entry: "+name)
                found_nested.add(name)
                target=dest/name
                target.parent.mkdir(exist_ok=True)
                with target.open("xb") as f:
                    f.write(z.read(i))
                continue
            if (not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*",name)
                or name.endswith(".") or stat.S_ISLNK(i.external_attr>>16)
                or name.split(".")[0].upper() in {"CON","PRN","AUX","NUL",*[f"COM{x}" for x in range(1,10)],*[f"LPT{x}" for x in range(1,10)]}):
                raise ValueError("Unexpected archive entry: "+name)
            with (dest/name).open("xb") as f:
                f.write(z.read(i))
        if found_nested!=allowed_nested:
            raise ValueError("Missing required Ecophon payload")
    if not all((dest/p[k]).is_file() for k in ("entry","library")):
        raise ValueError("Missing entrypoint or library")
    return sorted(x.relative_to(dest).as_posix() for x in dest.rglob("*.wav"))

def url_for(p):
    return f"{BASE}/actions/runs/{p['run']}/artifacts/{p['artifact']}"

def launch(root,p,probe=False):
    with socket.socket() as s:
        s.bind(("127.0.0.1",0))
        port=s.getsockname()[1]
    cmd=[sys.executable,str(root/p["entry"])]
    if p["library_flag"]:
        cmd.append("--library")
    cmd.extend([str(root/p["library"]),"--port",str(port)])
    log=root/"selector-server.log"
    with log.open("w",encoding="utf-8") as stream:
        child=subprocess.Popen(cmd,cwd=root,stdout=stream,stderr=stream)
        try:
            deadline=time.monotonic()+12
            while True:
                if child.poll() is not None:
                    raise RuntimeError("Native server exited: "+log.read_text(errors="replace")[-2000:])
                c=http.client.HTTPConnection("127.0.0.1",port,timeout=1)
                try:
                    c.request("GET","/")
                    response=c.getresponse()
                    data=response.read()
                    if response.status==200 and p["page"].casefold().encode() in data.lower():
                        break
                except OSError:
                    pass
                finally:
                    c.close()
                if time.monotonic()>=deadline:
                    raise RuntimeError("Native server readiness timeout")
                time.sleep(.1)
            url=f"http://127.0.0.1:{port}/"
            print(p["name"]+" actual local native server ready: "+url,flush=True)
            if not probe:
                webbrowser.open(url)
                print("Keep this window open during audition. Press Ctrl+C to close the server.")
                try:
                    child.wait()
                except KeyboardInterrupt:
                    pass
        finally:
            if child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()

def main():
    entries=catalogue()
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("instrument",nargs="?",choices=entries)
    ap.add_argument("archive",nargs="?",type=Path)
    ap.add_argument("--verify",action="store_true",help="Check original ZIP and extract without execution")
    ap.add_argument("--probe",action="store_true",help="Run local native HTTP readiness test without opening browser")
    ap.add_argument("--allow-provisional",action="store_true",help="Explicitly allow a candidate without current independent QA")
    a=ap.parse_args()
    if not a.instrument:
        for p in entries.values():
            print(f"{p['id']}: {p['qa']}\n  {p['controls']}\n  {url_for(p)}")
        print("Run: python selector.py INSTRUMENT DOWNLOADED_ORIGINAL_ZIP")
        return
    p=entries[a.instrument]
    if a.archive is None:
        ap.error("Supply the downloaded original ZIP from "+url_for(p))
    if p["qa_run"] is None and not a.allow_provisional and not a.verify:
        ap.error("Provisional candidate; use --allow-provisional only for explicit evaluation")
    if not a.verify and sys.platform!="win32":
        ap.error("These pinned native archives are Windows packages")
    with tempfile.TemporaryDirectory(prefix="VIBEWARE native selector ") as td:
        root=Path(td)
        wavs=verified_extract(a.archive.resolve(),root,p)
        print("SHA-256 verified; demos:",", ".join(wavs),flush=True)
        if not a.verify:
            launch(root,p,a.probe)

if __name__=="__main__":
    main()
