"""Prepare a private local audition collection; never redistribute firmware or binaries."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

QA_REF = 'e6a3a79461c7f2672b266685c1ed3081f384c17c'
QA_FILES = {
    'selector.py': '11a8841289b54601bf8ab0316e93fe3040b0bc06',
    'native-packages.json': '7b170ae24ecc120aff51bac6447299476d293115',
    'SELECTOR.md': '240f0c783c08b8e0ed4e7dd4cc0226ff96582f2c',
}
# source, author run, artifact, original archive SHA256, entrypoint, DLL
PINS = {
    'chronomorph': ('e57e0ca4ddc3070315a78d8835010b9488c3d176', 46130204509, 15257079145, 'df06eeeae7ddbc47454b209213d2f17960ee1a84d4b64c723e63a2fa18b8202c', 'live.py', 'chronomorph-live.dll'),
    'ecophon': ('eaf276c015fc81185076647762ddf1fd97aa7960', 46126318152, 15256006594, '51d547b3368998380b362b812ea371167bac528045d20ab158e47df4c4c4e6e1', 'live.py', 'ecof.dll'),
    'xenoresonator': ('571da84e6fd7d47efb6341cf836ede6367ad4fc8', 46101786743, 15246065654, 'c2357be924e5e6070c587976e9e9a2edcd03b978e62264f1f37a90ec543e8256', 'live.py', 'live.dll'),
    'grimoire': ('7cc0999c5fe7a110dd9988636ea573a282170e8a', 46104126354, 15245854227, '3d9b56c57aa1a4bc3378d287baf11570208b2b5c85855a28d44ed029defe5adb', 'host.py', 'orbit.dll'),
}
LIMIT = 50_000_000


def blob_sha(data):
    return hashlib.sha1(f'blob {len(data)}\0'.encode() + data).hexdigest()


def verify_selector(root):
    for name, expected in QA_FILES.items():
        if blob_sha((root / name).read_bytes()) != expected:
            raise ValueError(f'QA source identity mismatch: {name}')
    records = json.loads((root / 'native-packages.json').read_text(encoding='utf-8'))['packages']
    if len(records) != len(PINS) or {p['id'] for p in records} != set(PINS):
        raise ValueError('QA pin inventory mismatch')
    for p in records:
        if tuple(p[k] for k in ('source', 'run', 'artifact', 'sha256', 'entry', 'library')) != PINS[p['id']] or not p['qa_run']:
            raise ValueError('QA pin mismatch')


def verify_archives(root):
    records = []
    for name, (source, run, artifact, digest, entry, dll) in PINS.items():
        path = root / (name + '.zip')
        if not path.is_file() or path.stat().st_size > LIMIT:
            raise ValueError(f'Missing or oversized archive: {name}')
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError(f'Original archive SHA-256 mismatch: {name}')
        with zipfile.ZipFile(path) as z:
            infos = z.infolist()
            if len(infos) > 200 or sum(i.file_size for i in infos) > LIMIT or z.testzip() is not None:
                raise ValueError(f'Invalid ZIP integrity/bounds: {name}')
            if not {entry, dll} <= set(z.namelist()):
                raise ValueError(f'Missing native payload: {name}')
            records.append(dict(id=name, source=source, run=run, artifact=artifact, sha256=digest, size=len(raw), entries=len(infos)))
    return dict(schema=1, kind='private-native-audition', qa_ref=QA_REF, archives=records)


def prepare(archives, out):
    if out.exists():
        raise FileExistsError(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    # Stage then verify copied bytes, so input changes cannot silently enter the collection.
    with tempfile.TemporaryDirectory(prefix='.vibeware-', dir=out.parent) as tmp:
        stage = Path(tmp) / 'collection'
        stage.mkdir()
        for name in PINS:
            src = archives / (name + '.zip')
            if not src.is_file() or src.stat().st_size > LIMIT:
                raise ValueError(f'Missing or oversized archive: {name}')
            shutil.copyfile(src, stage / src.name)
        receipt = verify_archives(stage)
        (stage / 'collection.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
        os.rename(stage, out)
    return receipt


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('command', choices=('check', 'prepare', 'probe', 'launch'))
    ap.add_argument('archives', type=Path)
    ap.add_argument('--out', type=Path)
    ap.add_argument('--selector', type=Path, default=Path(__file__).with_name('qa-selector'))
    ap.add_argument('--instrument', choices=PINS)
    a = ap.parse_args()
    if a.command == 'prepare':
        if a.out is None:
            ap.error('--out is required')
        result = prepare(a.archives, a.out)
    else:
        result = verify_archives(a.archives)
    print(json.dumps(result, indent=2), flush=True)
    if a.command in ('probe', 'launch'):
        verify_selector(a.selector)
        if a.command == 'launch' and a.instrument is None:
            ap.error('--instrument is required for launch')
        for name in [a.instrument] if a.instrument else PINS:
            cmd = [sys.executable, str((a.selector / 'selector.py').resolve()), name, str((a.archives / (name + '.zip')).resolve())]
            if a.command == 'probe':
                cmd.append('--probe')
            subprocess.run(cmd, check=True)


if __name__ == '__main__':
    main()
