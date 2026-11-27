"""Original Grimoire artifact: independent extracted executable, WAV and HTTP replay."""
import argparse
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile

from ecophon_archive import extract
from orbit_http import run

def sha(data):
    return hashlib.sha256(data).hexdigest()

def main():
    p=argparse.ArgumentParser()
    p.add_argument("source",type=Path)
    p.add_argument("archive",type=Path)
    p.add_argument("digest")
    a=p.parse_args()
    source=a.source.resolve()
    with tempfile.TemporaryDirectory(prefix="QA Orbit archive with spaces ") as td:
        root=Path(td)
        original=root/"original package"
        original.mkdir()
        extract(a.archive.resolve(),original,a.digest)
        ui=source/"companion/grimoire"
        core=source/"instruments/grimoire"
        checked=[]
        for f in sorted(ui.iterdir()):
            if f.is_file() and (original/f.name).is_file():
                assert f.read_bytes().replace(b"\r\n",b"\n")== (original/f.name).read_bytes().replace(b"\r\n",b"\n"),f.name
                checked.append(f.name)
        assert {"host.py","index.html","gesture.js","profile.json"}.issubset(checked)
        lib="orbit.dll" if os.name=="nt" else "orbit.so"
        exe="test.exe" if os.name=="nt" else "test"
        assert (original/lib).is_file() and (original/exe).is_file()
        if os.name!="nt":
            (original/exe).chmod(0o755)
        rebuilt=root/exe
        flags=[] if os.name=="nt" else ["-fsanitize=undefined","-fno-sanitize-recover=all"]
        subprocess.run(["gcc","-std=c11","-O2","-Wall","-Wextra","-Werror",*flags,
                         str(core/"orbit.c"),str(ui/"session.c"),str(core/"test.c"),"-o",str(rebuilt)],
                         check=True,timeout=120,cwd=root)
        names=["amber.wav","iron.wav","abyss.wav"]
        hashes={}
        for label,binary in [("original",original/exe),("fresh",rebuilt)]:
            paths=[root/(label+"-"+n) for n in names]
            subprocess.run([str(binary),*[str(v) for v in paths]],check=True,timeout=120,cwd=binary.parent)
            for n,path in zip(names,paths):
                expected=(original/n).read_bytes()
                assert path.read_bytes()==expected,(label,n)
                hashes[n]=sha(expected)
        assert len(set(hashes.values()))==3
        witnesses=[]
        for package in (original,None):
            stream=io.StringIO()
            with contextlib.redirect_stdout(stream):
                run(source,original=package)
            witnesses.append(json.loads(stream.getvalue()))
        assert witnesses[0]==witnesses[1],"original package and exact rebuild differ"
        print(json.dumps({"archive_sha256":a.digest,"source_files_checked":checked,"wav_sha256":hashes,
                         "binary_sha256":{f:sha((original/f).read_bytes()) for f in (lib,exe)},
                         "http":witnesses[0]},sort_keys=True))
if __name__=="__main__":
    main()
