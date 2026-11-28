"""Independent PCM/trace verification of an actual-core factory gallery."""
import hashlib
import json
import math
from pathlib import Path
import struct
import sys
import wave


def verify(root):
    root = Path(root)
    r = json.loads((root/'receipt.json').read_text())
    assert r['schema'] == 'xenoresonator-native-patch-gallery/1'
    assert (r['rate'], r['block_frames'], r['frames'], r['device_telemetry']) == (24000, 1200, 96000, False)
    patches = {p['id'] for p in r['patches']}
    assert len(patches) == 6 and len(r['patches']) == 6
    assert set(r['results']) == patches | {'held-control', 'held-patch-change'}
    assert {p.name for p in root.glob('*.wav')} == {name+'.wav' for name in r['results']}
    raw = {}
    for name, result in r['results'].items():
        with wave.open(str(root/(name+'.wav')), 'rb') as w:
            assert (w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes(), w.getcomptype()) == (1, 2, 24000, 96000, 'NONE')
            pcm = w.readframes(96000)
        assert len(pcm) == 192000 and hashlib.sha256(pcm).hexdigest() == result['pcm_sha256']
        assert len(result['trace']) == 80
        peaks = []
        for i, t in enumerate(result['trace']):
            block = pcm[i*2400:(i+1)*2400]
            s = struct.unpack('<1200h', block)
            peak = max(map(abs, s))
            peaks.append(peak)
            assert t['block'] == i and t['patch'] in patches
            assert t['pcm_sha256'] == hashlib.sha256(block).hexdigest()
            assert t['peak'] == peak and t['rms_floor'] == math.isqrt(sum(v*v for v in s)//1200)
            assert len(t['levels']) == 6 and all(type(v) is int and v >= 0 for v in t['levels'])
            if i >= 70:
                assert not any(block) and not any(t['levels'])
        assert 0 < max(peaks) == result['peak'] < 24000
        raw[name] = pcm
    assert len({raw[name] for name in patches}) == 6
    a, b = raw['held-control'], raw['held-patch-change']
    assert a[:2400] == b[:2400] and a[2400:4800] != b[2400:4800]
    for name in ('held-control', 'held-patch-change'):
        trace = r['results'][name]['trace']
        assert [t['block'] for t in trace if t['event'] == 1] == [0]
        assert trace[1]['event'] == 0
    return {'wav_count': len(raw), 'verified_blocks': 80*len(raw), 'distinct_patches': len(patches)}


if __name__ == '__main__':
    print(json.dumps(verify(sys.argv[1]), sort_keys=True))
