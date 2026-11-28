"""Offline CYDaux fixture from actual-core Material Passage, not wire/device telemetry."""
import hashlib
import json
import math
from pathlib import Path
import struct
import sys
import wave

RATE, BLOCK, COUNT = 24000, 1200, 240
COLUMNS = ['block','event','material','excitation','damping','coupling','note',
           'velocity','A0','A1','A2','B0','B1','B2']
DIGESTS = {
    'coupled': 'b41928a6101470c2a92ce657aeb7dd94ae6ad80435015c11b914cbafebcde1e6',
    'uncoupled': '8c524cbed46cc533a354189cdc9b47a8292854a3ee3d5616717f38e322aba4f7',
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def build(directory):
    receipt = json.loads((directory / 'receipt.json').read_text(encoding='utf-8'))
    require((receipt['rate'], receipt['block'], receipt['frames']) ==
            (RATE, BLOCK, BLOCK * COUNT), 'receipt format')
    require(receipt['trace_columns'] == COLUMNS, 'trace layout')
    arms = {}
    for name, expected in DIGESTS.items():
        meta = receipt['results'][name]
        with wave.open(str(directory / (name + '.wav')), 'rb') as wav:
            require((wav.getnchannels(), wav.getsampwidth(), wav.getframerate(),
                     wav.getnframes(), wav.getcomptype()) ==
                    (1, 2, RATE, BLOCK * COUNT, 'NONE'), 'WAV format')
            pcm = wav.readframes(BLOCK * COUNT)
        require(len(pcm) == BLOCK * COUNT * 2, 'truncated PCM')
        require(hashlib.sha256(pcm).hexdigest() == meta['pcm_sha256'] == expected,
                'PCM digest: ' + name)
        trace = meta['trace']
        require(len(trace) == COUNT, 'trace length')
        rows = []
        for i, row in enumerate(trace):
            require(len(row) == 14 and all(type(v) is int for v in row), 'trace row')
            block, event, material, excitation, damping, coupling, note, velocity, *levels = row
            require(block == i and event in (0, 1, 2) and 0 <= material <= 3,
                    'event/material/index')
            require(all(0 <= v <= 127 for v in (excitation, damping, coupling))
                    and 36 <= note <= 84 and 1 <= velocity <= 127, 'control range')
            require(all(0 <= v <= 131070 for v in levels), 'mode range')
            chunk = pcm[i * BLOCK * 2:(i + 1) * BLOCK * 2]
            samples = struct.unpack('<1200h', chunk)
            peak = max(map(abs, samples))
            require(peak < 24000, 'headroom')
            if name == 'uncoupled':
                require(coupling == 0 and not any(levels[3:]), 'uncoupled body B')
            if i >= 215:
                require(event == 0 and peak == 0 and not any(levels), 'panic silence')
            rows.append({'end_sample': (i + 1) * BLOCK,
                         'event': 'panic' if i == 215 else ('none','strike','release')[event],
                         'material': material, 'excitation': excitation, 'damping': damping,
                         'coupling': coupling, 'note': note, 'velocity': velocity,
                         'mode_level_sampled_peak': levels, 'pcm_peak': peak,
                         'pcm_rms_floor': math.isqrt(sum(s*s for s in samples) // BLOCK),
                         'pcm_sha256': hashlib.sha256(chunk).hexdigest()})
        require(max(r['pcm_peak'] for r in rows) == meta['peak'], 'peak receipt')
        arms[name] = rows
    a, b = arms['coupled'], arms['uncoupled']
    require(a[:40] == b[:40], 'matched pre-intervention state')
    require(a[40]['event'] == 'none' and a[40]['coupling'] == 127
            and any(a[40]['mode_level_sampled_peak'][3:])
            and a[40]['pcm_sha256'] != b[40]['pcm_sha256'], 'coupling witness')
    require(all(r[214]['pcm_peak'] > 0 for r in (a,b)), 'nonvacuous panic')
    require(all(sum(row['event'] == 'strike' for row in r) == 17 for r in (a,b)), 'strike count')
    return {'schema': 'xenoresonator-local-replay/1', 'source': 'offline-native-core',
            'device_telemetry': False, 'rate': RATE, 'block_frames': BLOCK,
            'mode_level_semantics': 'max of five 10ms boundary magnitude samples, not instantaneous or RMS',
            'xy': {'x': 'excitation', 'y': 'damping'}, 'pcm_sha256': DIGESTS, 'arms': arms}


if __name__ == '__main__':
    result = build(Path(sys.argv[1]))
    Path(sys.argv[2]).write_bytes((json.dumps(result, sort_keys=True, separators=(',', ':')) + '\n').encode('utf-8'))
