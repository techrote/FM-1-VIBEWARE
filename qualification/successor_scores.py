"""Exact-source score reproduction and independent PCM alignment for successor archives."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

from ecophon_archive import ECO_ARC_FILES, ECO_SUCCESSOR_FILES, extract
from verify_replay import verify


def run(*args, cwd):
    subprocess.run([str(x) for x in args], cwd=cwd, check=True, timeout=180)


def compare(fresh, original, names):
    result = {}
    for name in names:
        a, b = (fresh/name).read_bytes(), (original/name).read_bytes()
        # Only the receipt's platform newline convention is allowed to differ.
        if name.endswith(('.json', '.csv')):
            a, b = a.replace(b'\r\n', b'\n'), b.replace(b'\r\n', b'\n')
        assert a == b, name
        result[name] = hashlib.sha256(a).hexdigest()
    return result


def main():
    instrument, source, native, native_digest, score, score_digest, *extra = sys.argv[1:]
    assert extra in ([], ['--live-arc']) and (not extra or instrument == 'ecophon')
    source = Path(source).resolve()
    native = Path(native).resolve()
    core = source/'instruments'/instrument
    windows = os.name == 'nt'
    flags = ['gcc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror']
    if not windows:
        flags += ['-fsanitize=undefined', '-fno-sanitize-recover=all']
    libflags = ['-shared'] + (['-Wl,--export-all-symbols'] if windows else ['-fPIC'])
    with tempfile.TemporaryDirectory(prefix='QA successor scores with spaces ') as td:
        root = Path(td)
        original, fresh = root/'original', root/'fresh'
        original.mkdir()
        fresh.mkdir()
        lib = root/('qa.dll' if windows else 'qa.so')
        receipts = {}
        if instrument == 'ecophon':
            extract(native, original, native_digest, allowed_nested=ECO_SUCCESSOR_FILES + (ECO_ARC_FILES if extra else ()))
            run(*flags, *libflags, core/'ecophon.c', core/'fixture.c', '-o', lib, cwd=root)
            for generator, target in [('performance.py', 'performances'), ('feedback.py', 'feedback')]:
                run(sys.executable, core/generator, lib, fresh/target, cwd=root)
            run(sys.executable, core/'companion_fixture.py', lib, fresh/'performances/companion-replay.json', cwd=root)
            receipts.update(compare(fresh, original, ECO_SUCCESSOR_FILES))
            replay_root = original/'performances'
        elif instrument == 'grimoire':
            ui = source/'companion/grimoire'
            extract(native, original, native_digest, ignored=('__pycache__/host.cpython-312.pyc',))
            ribbon = root/'original ribbon'
            ribbon.mkdir()
            extract(Path(score).resolve(), ribbon, score_digest)
            run(*flags, *libflags, core/'orbit.c', ui/'session.c', '-o', lib, cwd=root)
            exe = root/'performance.exe'
            run(*flags, core/'orbit.c', ui/'session.c', core/'performance.c', '-o', exe, cwd=root)
            run(exe, fresh/'orbit-passage.wav', cwd=root)
            run(sys.executable, ui/'replay.py', lib, fresh/'orbit-passage.wav', fresh/'orbit-replay.json', cwd=root)
            receipts.update(compare(fresh, original, ['orbit-passage.wav','orbit-replay.json']))
            run(*flags, core/'orbit.c', ui/'session.c', core/'ribbon.c', '-o', exe, cwd=root)
            run(exe, fresh/'ribbon.wav', fresh/'fixed-y.wav', fresh/'ribbon.csv', cwd=root)
            receipts.update(compare(fresh, ribbon, ['ribbon.wav','fixed-y.wav','ribbon.csv']))
            replay_root = original
        else:
            extract(Path(score).resolve(), original, score_digest)
            if instrument == 'chronomorph':
                run(*flags, *libflags, core/'chrono.c', core/'live_bridge.c', '-o', lib, cwd=root)
                generator = 'tidal_interlock.py'
                names = ['tidal-interlock.wav','fixed-pattern-control.wav',
                         'tidal-interlock.json','fixed-pattern-control.json','receipt.json']
            elif instrument == 'xenoresonator':
                run(*flags, *libflags, core/'xeno.c', core/'live_bridge.c', '-o', lib, cwd=root)
                generator = 'material_passage.py'
                names = ['coupled.wav','uncoupled.wav','receipt.json']
            else:
                raise ValueError(instrument)
            run(sys.executable, core/generator, lib, fresh, cwd=root)
            run(sys.executable, core/'companion_replay.py', fresh, fresh/'companion-replay.json', cwd=root)
            receipts.update(compare(fresh, original, names+['companion-replay.json']))
            replay_root = original
        old = verify(instrument, replay_root)
        new = verify(instrument, fresh/'performances' if instrument=='ecophon' else fresh)
        assert old == new, 'fresh replay alignment receipt differs'
        print(json.dumps({'score_files': receipts, 'replay': old}, sort_keys=True))


if __name__ == '__main__':
    main()
