"""Synthetic archive boundary regression for the native selector."""
import hashlib
from pathlib import Path
import stat
import tempfile
import unittest
import zipfile
from selector import ECO_PAYLOADS, ECO_LIVE_ARC, verified_extract

class ArchiveTests(unittest.TestCase):
    def run_case(self, instrument, entries, ok, live_arc=False):
        with tempfile.TemporaryDirectory(prefix="QA selector ") as d:
            root=Path(d)
            zpath=root/"package.zip"
            dest=root/"extracted"
            dest.mkdir()
            with zipfile.ZipFile(zpath,"w") as z:
                for name, data in entries:
                    z.writestr(name,data)
            p={"id":instrument,"entry":"live.py","library":"core.dll",
               "sha256":hashlib.sha256(zpath.read_bytes()).hexdigest()}
            if live_arc: p["ecophon_live_arc"]=True
            if ok:
                wavs=verified_extract(zpath,dest,p)
                self.assertEqual(set(wavs),{n for n in (ECO_PAYLOADS | (ECO_LIVE_ARC if live_arc else set())) if n.endswith(".wav")} if instrument=="ecophon" else set())
            else:
                with self.assertRaises((ValueError,OSError)):
                    verified_extract(zpath,dest,p)
                self.assertFalse((root/"escape.wav").exists())
    def test_exact_inventory(self):
        base=[("live.py",b"source"),("core.dll",b"test")]
        eco=base+[(n,b"payload") for n in sorted(ECO_PAYLOADS)]
        self.run_case("ecophon",eco,True)
        self.run_case("ecophon",eco[:-1],False)
        self.run_case("ecophon",eco+[("feedback/extra.wav",b"x")],False)
        self.run_case("ecophon",eco+[("../escape.wav",b"x")],False)
        self.run_case("ecophon",eco+[("feedback/POPULATION-FEEDBACK.WAV",b"x")],False)
        self.run_case("chronomorph",eco,False)
        self.run_case("chronomorph",base,True)
        self.run_case("grimoire",base+[("__pycache__/host.cpython-312.pyc",b"x")],True)
        self.run_case("grimoire",base+[("__pycache__/other.pyc",b"x")],False)
    def test_live_arc_inventory(self):
        base=[("live.py",b"source"),("core.dll",b"test")]
        eco=base+[(n,b"payload") for n in sorted(ECO_PAYLOADS | ECO_LIVE_ARC)]
        self.run_case("ecophon",eco,True,True)
        self.run_case("ecophon",eco,False)
        self.run_case("ecophon",eco[:-1],False,True)
        self.run_case("ecophon",eco+[("live-arc/extra.wav",b"x")],False,True)
        self.run_case("ecophon",eco+[("live-arc/0-ARC.wav",b"x")],False,True)
        self.run_case("chronomorph",base,False,True)
    def test_nested_symlink(self):
        link=zipfile.ZipInfo("feedback/population-feedback.wav")
        link.create_system=3
        link.external_attr=(stat.S_IFLNK|0o777)<<16
        entries=[("live.py",b"source"),("core.dll",b"test")]+[(n,b"payload") for n in ECO_PAYLOADS if n!=link.filename]+[(link,b"../escape.wav")]
        self.run_case("ecophon",entries,False)

if __name__=="__main__":
    unittest.main()
