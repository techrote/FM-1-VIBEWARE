"""Matched live Grimoire target transition witness; no physical claims."""
import hashlib
import json
import struct
import sys
import wave
from pathlib import Path

from rate_probe import decode

RATE = 44100
# Emulator key times (ms): PLAY 900, optional SCL 1700, HOME 2700,
# PLAY 3900, HOME 5200; capture ends at 6200. The existing reference
# capture starts about 430 ms after emulator start. These conservative
# PCM windows exclude edges even for offsets between 0 and 500 ms.
WINDOWS = dict(prefix=(0, 1000), preset=(1850, 2100),
               muted=(2850, 3250), restart=(4000, 4350))


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def window(samples, name):
    a, b = WINDOWS[name]
    return samples[a * RATE // 1000:b * RATE // 1000]


def read_pcm(path):
    with wave.open(str(path), 'rb') as w:
        require((w.getnchannels(), w.getsampwidth(), w.getframerate()) ==
                (2, 2, RATE), 'unexpected PCM format')
        frames = w.getnframes()
        data = w.readframes(frames)
    require(frames >= RATE * 11 // 2 and len(data) == frames * 4,
            'truncated transition capture')
    stereo = list(struct.iter_unpack('<hh', data))
    require(all(l == r for l, r in stereo), 'stereo mismatch')
    return [l for l, _ in stereo]


def validate(control, switched, repeat):
    require(len(control) == len(switched) == len(repeat) >= RATE * 11 // 2,
            'unmatched or truncated transition capture')
    require(switched == repeat, 'transition repeat differs')
    prefix = window(control, 'prefix')
    require(prefix == window(switched, 'prefix') and any(prefix),
            'pre-preset active PCM mismatch or silence')
    a, b = window(control, 'preset'), window(switched, 'preset')
    require(any(a) and any(b) and a != b, 'live material selection not witnessed')
    results = {}
    for name, samples in (('control', control), ('switched', switched)):
        middle = window(samples, 'muted')
        restart = window(samples, 'restart')
        tail = samples[-RATE // 2:]
        require(not any(middle), name + ': HOME did not silence mid-performance')
        require(any(restart), name + ': restart produced no audio')
        require(not any(tail), name + ': final HOME tail not silent')
        peak = max(map(abs, samples))
        require(peak < 32767, name + ': full-scale clipping')
        results[name] = dict(peak=peak, middle_silent_frames=len(middle),
                             restart_nonzero_frames=sum(x != 0 for x in restart),
                             final_silent_frames=len(tail))
    return dict(frames=len(control), preset_changed_frames=sum(x != y for x, y in zip(a,b)),
                **results)


def analyze(root):
    result = {}
    for mode in ('hold', 'linear'):
        addr = int((root / f'{mode}-address.txt').read_text(), 16)
        samples, metrics, hashes = {}, {}, {}
        for case in ('lifecycle-control', 'lifecycle-switch', 'lifecycle-repeat'):
            stem = f'{mode}-{case}'
            path = root / f'{stem}.wav'
            samples[case] = read_pcm(path)
            hashes[case] = hashlib.sha256(path.read_bytes()).hexdigest()
            metrics[case] = decode((root / f'{stem}.log').read_text(), addr)
        require(metrics['lifecycle-switch'] == metrics['lifecycle-repeat'],
                mode + ': nondeterministic modeled callback receipt')
        require(hashes['lifecycle-switch'] == hashes['lifecycle-repeat'],
                mode + ': WAV bytes differ on repeat')
        result[mode] = dict(**validate(samples['lifecycle-control'],
                                      samples['lifecycle-switch'],
                                      samples['lifecycle-repeat']),
                            sha256=hashes, modeled_callbacks=metrics)
    return dict(status='PASS', scope='instrumented emulator lifecycle only; not adoption or physical',
                pcm_windows_ms=WINDOWS, modes=result)


def self_test():
    n = 6 * RATE
    control = [100] * n
    for a,b in ((2800,3300),(5400,6000)):
        control[a*RATE//1000:b*RATE//1000] = [0] * ((b-a)*RATE//1000)
    switched = control.copy()
    a,b = WINDOWS['preset']
    switched[a*RATE//1000:b*RATE//1000] = [200] * ((b-a)*RATE//1000)
    assert validate(control, switched, switched)['preset_changed_frames'] > 0
    failures = []
    failures.append((control, control, control))  # aliased intervention
    failures.append((control, switched, control))  # nonrepeat
    failures.append((control[:-1], switched, switched))  # truncated
    for name, value in (('prefix', 101), ('muted', 1), ('restart', 0)):
        bad = switched.copy()
        a,b = WINDOWS[name]
        bad[a*RATE//1000:b*RATE//1000] = [value] * ((b-a)*RATE//1000)
        failures.append((control,bad,bad))
    bad = switched.copy()
    bad[-1] = 1
    failures.append((control,bad,bad))
    bad = switched.copy()
    bad[-RATE] = 32767
    failures.append((control,bad,bad))
    for args in failures:
        try:
            validate(*args)
        except ValueError:
            pass
        else:
            raise AssertionError('accepted corrupted lifecycle fixture')
    print('lifecycle validator self-test PASS (8 negative cases; synthetic only)')


if __name__ == '__main__':
    if sys.argv[1:] == ['--test']:
        self_test()
    elif len(sys.argv) == 2:
        print(json.dumps(analyze(Path(sys.argv[1])), indent=2))
    else:
        raise SystemExit('rate_lifecycle.py --test | rate-probe-directory')
