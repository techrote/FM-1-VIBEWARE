"""Independent PCM-to-replay alignment; no dependency on instrument generators."""
import hashlib
import json
import math
from pathlib import Path
import struct
import sys
import wave
import zlib


def digest(data):
    return hashlib.sha256(data).hexdigest()


def verify(instrument, root):
    root = Path(root)
    replay = root / ('orbit-replay.json' if instrument == 'grimoire' else 'companion-replay.json')
    d = json.loads(replay.read_text(encoding='utf-8'))
    block = 2400 if instrument == 'ecophon' else 1200
    count = 320 if instrument == 'chronomorph' else 240
    if instrument == 'grimoire':
        assert d['state_source'] == 'offline native core, not device telemetry'
        assert d['block_frames'] == block and d['sample_rate_hz'] == 24000
        arms = {'orbit-passage': d['snapshots']}
    elif instrument == 'chronomorph':
        assert d['source'] == 'offline actual native core; not device telemetry'
        assert d['frames_per_snapshot'] == block and d['sample_rate'] == 24000
        assert set(d['arms']) == {'tidal-interlock', 'fixed-pattern-control'}
        arms = {k: v['snapshots'] for k, v in d['arms'].items()}
    elif instrument == 'xenoresonator':
        assert d['device_telemetry'] is False and d['source'] == 'offline-native-core'
        assert d['block_frames'] == block and d['rate'] == 24000
        assert set(d['arms']) == {'coupled', 'uncoupled'}
        arms = d['arms']
    elif instrument == 'ecophon':
        assert d['state_source'] == 'local native core, not device telemetry' and d['wire_protocol'] is None
        assert d['frames_per_snapshot'] == block and d['sample_rate'] == 24000
        assert set(d['arms']) == {'habitat-arc', 'steady-control', 'frozen-control'}
        arms = d['arms']
    else:
        raise ValueError(instrument)
    result = {}
    for name, rows in arms.items():
        assert len(rows) == count, name
        wav = root / (name + '.wav')
        with wave.open(str(wav), 'rb') as w:
            assert (w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes(), w.getcomptype()) == (1, 2, 24000, count * block, 'NONE')
            pcm = w.readframes(count * block)
        assert len(pcm) == count * block * 2 and any(pcm)
        if instrument == 'grimoire':
            assert digest(pcm) == d['pcm_sha256']
        elif instrument == 'xenoresonator':
            assert digest(pcm) == d['pcm_sha256'][name]
        elif instrument == 'chronomorph':
            assert digest(wav.read_bytes()) == d['arms'][name]['wav_sha256']
        quiet = 0
        for i, row in enumerate(rows):
            raw = pcm[i * block * 2:(i + 1) * block * 2]
            s = struct.unpack('<' + str(block) + 'h', raw)
            peak = max(map(abs, s))
            rms = math.isqrt(sum(v * v for v in s) // block)
            end = (i + 1) * block
            if instrument == 'chronomorph':
                assert row[0] == end and row[6:9] == [peak, rms, f'{zlib.crc32(raw):08x}']
                assert row[4] or not peak
            else:
                assert row['pcm_sha256'] == digest(raw)
                assert row['frame_end' if instrument == 'ecophon' else 'end_sample'] == end
                if instrument == 'grimoire':
                    assert (row['peak'], row['rms']) == (peak, rms)
                elif instrument == 'xenoresonator':
                    assert (row['pcm_peak'], row['pcm_rms_floor']) == (peak, rms)
                    if name == 'uncoupled':
                        assert row['mode_level_sampled_peak'][3:] == [0, 0, 0]
                    if row['event'] == 'panic':
                        assert not peak and not any(row['mode_level_sampled_peak'])
                else:
                    assert len(row['agents']) == 8 and len(row['resources']) == 4
                    assert all(0 <= v <= 4096 for v in row['resources'])
            quiet += not peak
        result[name] = {'blocks': count, 'zero_blocks': quiet, 'pcm_sha256': digest(pcm)}
    assert len({v['pcm_sha256'] for v in result.values()}) == len(arms)
    return {'instrument': instrument, 'replay_sha256': digest(replay.read_bytes()), 'arms': result}


if __name__ == '__main__':
    print(json.dumps(verify(sys.argv[1], sys.argv[2]), sort_keys=True))
