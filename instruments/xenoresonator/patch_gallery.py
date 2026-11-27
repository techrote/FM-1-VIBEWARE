"""Native factory-patch audition; fixed phrase, no target/transport claim."""
import ctypes as C
import hashlib
import json
import math
from pathlib import Path
import re
import struct
import sys
import wave

RATE, BLOCK = 24000, 1200
KEYS = ('p', 'e', 'd', 'c')


def patches():
    html = Path(__file__).with_name('live.html').read_text(encoding='utf-8')
    data = re.findall(r'<script type="application/json" id="patch-data">(.*?)</script>', html)
    assert len(data) == 1
    rows = json.loads(data[0])
    assert len(rows) == 6 and len({p['id'] for p in rows}) == 6
    for p in rows:
        assert set(p) == {'id', 'name', *KEYS}
        assert re.fullmatch('[a-z-]+', p['id']) and isinstance(p['name'], str)
        assert all(type(p[k]) is int and 0 <= p[k] <= (3 if k == 'p' else 127) for k in KEYS)
    return rows


def render(lib, patch, transition=None):
    lib.live_reset()
    samples, levels = (C.c_int16 * BLOCK)(), (C.c_uint32 * 6)()
    pcm, trace = bytearray(), []
    note, velocity = 48, 100
    for i in range(80):
        event = 0
        if transition is None and i in (0, 15, 30, 45):
            note, velocity = {0: (48, 100), 15: (55, 82), 30: (51, 118), 45: (60, 96)}[i]
            event = 1
        elif transition is None and i in (8, 23, 38, 53):
            event = 2
        elif transition is not None:
            event = 1 if i == 0 else 2 if i == 8 else 0
        if i == 70:
            lib.live_panic()
        selected = transition if transition is not None and i >= 1 else patch
        lib.live_block(*(selected[k] for k in KEYS), note, velocity, event, samples, levels)
        raw = struct.pack('<1200h', *samples)
        pcm.extend(raw)
        trace.append({'block': i, 'patch': selected['id'], 'event': event,
                      'note': note, 'velocity': velocity, 'peak': max(map(abs, samples)),
                      'rms_floor': math.isqrt(sum(s*s for s in samples)//BLOCK),
                      'levels': list(levels), 'pcm_sha256': hashlib.sha256(raw).hexdigest()})
    assert any(pcm[:BLOCK*2]) and max(t['peak'] for t in trace) < 24000
    assert not any(pcm[70*BLOCK*2:]) and all(not any(t['levels']) for t in trace[70:])
    return bytes(pcm), trace


def main():
    lib = C.CDLL(str(Path(sys.argv[1]).resolve(strict=True)))
    lib.live_block.argtypes = [C.c_uint]*7+[C.POINTER(C.c_int16), C.POINTER(C.c_uint32)]
    lib.live_block.restype = None
    for f in (lib.live_reset, lib.live_panic):
        f.argtypes, f.restype = [], None
    out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
    rows = patches()
    results = {}
    def save(name, result):
        pcm, trace = result
        with wave.open(str(out/(name+'.wav')), 'wb') as wav:
            wav.setparams((1, 2, RATE, 0, 'NONE', 'not compressed'))
            wav.writeframes(pcm)
        results[name] = {'pcm_sha256': hashlib.sha256(pcm).hexdigest(),
                         'peak': max(t['peak'] for t in trace), 'trace': trace}
    for patch in rows:
        result = render(lib, patch)
        assert result == render(lib, patch)
        save(patch['id'], result)
    assert len({v['pcm_sha256'] for v in results.values()}) == len(rows)
    # Matched one-strike control: same material, change only macro controls on block 1.
    a = render(lib, rows[0], rows[0]); b = render(lib, rows[0], rows[1])
    assert a[0][:BLOCK*2] == b[0][:BLOCK*2]
    assert a[0][BLOCK*2:BLOCK*4] != b[0][BLOCK*2:BLOCK*4]
    assert a[1][1]['event'] == b[1][1]['event'] == 0
    assert sum(t['event'] == 1 for t in a[1]) == sum(t['event'] == 1 for t in b[1]) == 1
    save('held-control', a); save('held-patch-change', b)
    receipt = {'schema': 'xenoresonator-native-patch-gallery/1', 'rate': RATE,
               'block_frames': BLOCK, 'frames': 80*BLOCK, 'device_telemetry': False,
               'patches': rows, 'results': results}
    (out/'receipt.json').write_bytes((json.dumps(receipt, sort_keys=True, separators=(',', ':'))+'\n').encode())
    print('PASS six distinct factory patches, deterministic repeat, held macro change without strike, panic silence')
    for name, result in results.items():
        print(name, result['peak'], result['pcm_sha256'])


if __name__ == '__main__':
    main()
