"""Fourth-consumer rate A/B, using the unchanged #15 USB harness in private checkouts."""
import hashlib
import json
import math
import struct
import subprocess
import sys
import wave
from pathlib import Path

PIN = '3449ead4dd13d91ba0a57262a48349f38d6c465c'
APP = 'ab64fc8b2e41d04e2713dff1e3cdbf85f7d2396d'
HOLD = '5f568b0e76df2f1082c5b6c037617674c95c5629'
LINEAR = '5c819bf6d473e8ca2956b062ff72a02f6e2c015c'
SEAMS = (('#include "rate.h"', '#include "rate_linear.h"', 1),
         ('static VwRate rate;', 'static VwRateLinear rate;', 1),
         ('vw_rate_clear(', 'vw_linear_clear(', 2),
         ('vw_rate_step(', 'vw_linear_step(', 1))


def require(ok, why):
    if not ok:
        raise ValueError(why)


def blob(raw):
    return hashlib.sha1(f'blob {len(raw)}\0'.encode() + raw).hexdigest()


def variant(source, mode):
    require(mode in ('hold', 'linear'), 'unknown mode')
    for old, new, count in SEAMS:
        require(source.count(old) == count, 'unexpected Xeno adapter seam: ' + old)
        if mode == 'linear':
            source = source.replace(old, new)
    return source


def prepare(root, linear, mode):
    head = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    require(head == PIN, 'wrong private checkout')
    app = root / 'platform/companion/xeno_app.c'
    hold = root / 'platform/emulator/rate.h'
    raw, lin = app.read_bytes(), linear.read_bytes()
    require(blob(raw) == APP and blob(hold.read_bytes()) == HOLD and blob(lin) == LINEAR,
            'frozen source blob mismatch')
    out = variant(raw.decode(), mode).encode()
    if mode == 'linear':
        app.write_bytes(out)
        (hold.parent / 'rate_linear.h').write_bytes(lin)
    return dict(reference=PIN, mode=mode, source_blob=APP, generated_blob=blob(out),
                hold_blob=HOLD, linear_blob=LINEAR)


def pcm(path):
    with wave.open(str(path), 'rb') as w:
        require((w.getnchannels(), w.getsampwidth(), w.getframerate()) == (2, 2, 44100), 'PCM format')
        n = w.getnframes()
        data = w.readframes(n)
    require(len(data) == 4*n, 'truncated PCM')
    return list(struct.iter_unpack('<hh', data))


def onset(frames):
    first = next((i for i, v in enumerate(frames) if v != (0, 0)), len(frames))
    require(len(frames)-first >= 4096, 'missing audible analysis interval')
    return frames[first:first+4096]


def metrics(path):
    pairs = [line.split('=') for line in path.read_text().splitlines()]
    require(all(len(p) == 2 for p in pairs), 'bad metrics')
    values = {k: int(v) for k, v in pairs}
    require(len(values) == len(pairs), 'duplicate metrics')
    require(values['target_audio_blocks'] > 100 and
            0 < values['target_audio_max_ticks'] < 256*24000000/44100, 'callback deadline')
    return values


def report(hold, linear):
    from rate_quality import high_fraction, sizes
    results = {}
    for mode, root in (('hold', hold), ('linear', linear)):
        receipt = json.loads((root/'rate-provenance.json').read_text())
        require(receipt['reference'] == PIN and receipt['mode'] == mode and
                receipt['source_blob'] == APP and receipt['hold_blob'] == HOLD and
                receipt['linear_blob'] == LINEAR, 'wrong experiment provenance')
        manifest = json.loads((root/'sha256.json').read_text())
        for name, digest in manifest.items():
            path = root/name
            require(path.resolve().is_relative_to(root.resolve()) and path.is_file() and
                    hashlib.sha256(path.read_bytes()).hexdigest() == digest, 'artifact digest mismatch: '+name)
        arms, prefixes = {}, {}
        for clock in ('instruction', 'strict'):
            p = root/clock
            q = json.loads((p/'qualification.json').read_text())
            require(q['status'] == 'PASS' and q['mode'] == clock and q['usb_audio_underruns'] == 0,
                    'USB harness gate')
            required = {'PCM repeat', 'coupling contrast', 'panic tail', 'lease expiry',
                        'new session recovery', 'actual readback', 'modeled callback deadline'}
            require(required.issubset(q['checks']), 'missing USB checks')
            raw = [onset(pcm(p/f'xeno-{name}.wav')) for name in ('uncoupled','repeat','coupled')]
            require(raw[0] == raw[1] and raw[0] != raw[2], 'repeat/control PCM mismatch')
            prefixes[clock] = raw
            arms[clock] = dict(metrics=metrics(p/'target-metrics.txt'), i2s_frames=q['i2s_frames'],
                               usb_audio_frames=q['usb_audio_frames'])
        require(prefixes['instruction'] == prefixes['strict'], 'clock model PCM mismatch')
        bands = {}
        for name, frames in zip(('uncoupled','coupled'), (prefixes['strict'][0],prefixes['strict'][2])):
            require(all(l == r for l,r in frames), 'unexpected stereo divergence')
            mono = [l for l,_ in frames]
            bands[name] = dict(high_fraction=high_fraction(mono), peak=max(map(abs,mono)),
                               rms=math.sqrt(sum(v*v for v in mono)/len(mono)),
                               pcm_sha256=hashlib.sha256(struct.pack('<4096h',*mono)).hexdigest())
        results[mode] = dict(clocks=arms, sections=sizes(root/'target-size.txt'), bands=bands)
    h,l = results['hold'],results['linear']
    for name in ('uncoupled','coupled'):
        require(h['bands'][name]['pcm_sha256'] != l['bands'][name]['pcm_sha256'], 'rate variant aliased')
    return dict(status='PASS', scope='actual USB emulator experiment; no adoption or physical claim',
                reference=PIN, analysis='4096 frames from first nonzero stereo frame; >=12kHz power fraction',
                modes=results, section_delta={k:l['sections'][k]-v for k,v in h['sections'].items()})


def self_test():
    s = '\n'.join(old*count for old,_,count in SEAMS)
    require(variant(s,'hold') == s, 'hold source changed')
    l = variant(s,'linear')
    require(all(l.count(new)==count for _,new,count in SEAMS), 'linear seam counts')
    for bad in (s+s, s.replace('vw_rate_step(', 'missing('), ''):
        try:
            variant(bad,'linear')
        except ValueError:
            pass
        else:
            raise AssertionError('bad adapter accepted')
    try:
        onset([(0,0)]*5000)
    except ValueError:
        pass
    else:
        raise AssertionError('silent capture accepted')
    assert onset([(0,0)]*7+[(1,1)]*4096)==[(1,1)]*4096
    print('Xeno rate generator and onset gates PASS (synthetic)')


if __name__ == '__main__':
    if sys.argv[1:] == ['--test']:
        self_test()
    elif len(sys.argv)==5 and sys.argv[1]=='prepare':
        print(json.dumps(prepare(Path(sys.argv[2]),Path(sys.argv[3]),sys.argv[4]),indent=2))
    elif len(sys.argv)==4 and sys.argv[1]=='report':
        print(json.dumps(report(Path(sys.argv[2]),Path(sys.argv[3])),indent=2))
    else:
        raise SystemExit('rate_xeno.py --test | prepare checkout rate_linear.h hold|linear | report hold-dir linear-dir')
