"""Render an exported Chronomorph scene bank through the local native core.

Usage: python scene_score.py LIB OUTDIR --bank BANK.json --seconds 2
       python scene_score.py LIB OUTDIR --self-test
Fresh seed/preset, not a recording of an existing live session. No device I/O.
"""
import argparse
import ctypes as C
import hashlib
import json
import pathlib
import struct
import wave

RATE, BLOCK = 24000, 1200


def integer(v, lo, hi):
    return type(v) is int and lo <= v <= hi


def decode(raw):
    if len(raw) > 2048:
        raise ValueError('bank too large')
    b = json.loads(raw)
    if (not isinstance(b, dict) or set(b) != {'format', 'version', 'slots'}
            or b['format'] != 'chronomorph-scenes' or not integer(b['version'], 1, 1)
            or not isinstance(b['slots'], list) or len(b['slots']) != 4):
        raise ValueError('bank schema')
    cues = []
    for slot, s in enumerate(b['slots']):
        if s is None:
            continue
        if (not isinstance(s, dict) or set(s) != {'bpm', 'warp', 'variation', 'patterns'}
                or not integer(s['bpm'], 40, 220) or not integer(s['warp'], -60, 60)
                or not integer(s['variation'], 0, 100) or not isinstance(s['patterns'], list)
                or len(s['patterns']) != 3):
            raise ValueError('scene controls')
        for p in s['patterns']:
            if (not isinstance(p, list) or len(p) != 2 or not integer(p[0], 1, 16)
                    or not integer(p[1], 0, (1 << p[0])-1)):
                raise ValueError('pattern bounds')
        cues.append((slot+1, s['bpm'], s['warp'], s['variation'], tuple(n for p in s['patterns'] for n in p)))
    if not cues:
        raise ValueError('empty bank')
    return cues


def bind(path):
    lib = C.CDLL(str(pathlib.Path(path).resolve(strict=True)))
    lib.live_reset.argtypes = [C.c_uint32, C.c_uint]
    lib.live_reset.restype = None
    lib.live_block.argtypes = [C.c_uint, C.c_int, C.c_uint, C.c_uint,
                               C.POINTER(C.c_uint32), C.POINTER(C.c_int16), C.POINTER(C.c_uint32)]
    lib.live_block.restype = C.c_int
    return lib


def render(lib, cues, seconds, seed, preset, fixed=False):
    lib.live_reset(seed, preset)
    pcm, trace = bytearray(), []
    span = seconds*20
    active = len(cues)*span
    for block in range(active+20):
        slot, bpm, warp, variation, pattern = cues[min(block//span, len(cues)-1)]
        if fixed:
            pattern = cues[0][4]
        playing = int(block < active)
        samples, state = (C.c_int16*BLOCK)(), (C.c_uint32*15)()
        if lib.live_block(bpm, warp, variation, playing, (C.c_uint32*6)(*pattern), samples, state) != 1:
            raise RuntimeError('native block rejected')
        lanes = [list(state[i:i+5]) for i in range(0, 15, 5)]
        if any(l[0] >= pattern[2*i] or l[2] > l[1] or l[3] >= 4 or l[4] >= 144000000
               for i, l in enumerate(lanes)):
            raise RuntimeError('native lane bounds')
        if trace and any(not 0 <= l[1]-p[1] <= 2 or not 0 <= l[2]-p[2] <= l[1]-p[1]
                         for l, p in zip(lanes, trace[-1]['lanes'])):
            raise RuntimeError('native tick/hit continuity')
        if not playing and (any(samples) or lanes != trace[-1]['lanes']):
            raise RuntimeError('stop witness failed')
        pcm.extend(struct.pack('<1200h', *samples))
        trace.append(dict(block=block, end_frame=(block+1)*BLOCK, slot=slot, playing=playing,
                          bpm=bpm, warp=warp, variation=variation, patterns=list(pattern), lanes=lanes))
    return bytes(pcm), trace


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(lib, raw, seconds, seed, preset, out, fixture=False):
    cues = decode(raw)
    if not integer(seconds, 1, 10) or not integer(seed, 1, 2147483647) or not integer(preset, 0, 2):
        raise ValueError('duration, seed or preset bounds')
    arms = [render(lib, cues, seconds, seed, preset, fixed) for fixed in (False, True)]
    for fixed, arm in zip((False, True), arms):
        if arm != render(lib, cues, seconds, seed, preset, fixed):
            raise RuntimeError('repeat mismatch')
    a, b = arms
    if any([(l[1], l[4]) for l in x['lanes']] != [(l[1], l[4]) for l in y['lanes']]
           for x, y in zip(a[1], b[1])):
        raise RuntimeError('matched clock mismatch')
    samples = [struct.unpack(f'<{len(pcm)//2}h', pcm) for pcm, _ in arms]
    span = seconds*RATE
    changes = [sum(x != y for x, y in zip(samples[0][i*span:(i+1)*span], samples[1][i*span:(i+1)*span]))
               for i in range(len(cues))]
    if changes[0] != 0 or (fixture and (len(changes) != 2 or changes[1] == 0 or not all(any(s) for s in samples))):
        raise RuntimeError('matched control failed')
    out = pathlib.Path(out)
    out.mkdir(parents=True, exist_ok=True)
    (out/'scene-bank.json').write_bytes(raw.encode('utf-8'))
    receipt = dict(rate=RATE, block_frames=BLOCK, seed=seed, preset=preset, seconds_per_cue=seconds,
                   slots=[c[0] for c in cues], frames=len(samples[0]), changed_samples=changes,
                   bank_sha256=digest(out/'scene-bank.json'), clock_phase_identity=True, repeat_identity=True, arms={})
    for name, (pcm, trace), s in zip(('saved-score', 'fixed-pattern-control'), arms, samples):
        wav, state = out/(name+'.wav'), out/(name+'.json')
        with wave.open(str(wav), 'wb') as w:
            w.setparams((1, 2, RATE, 0, 'NONE', 'not compressed'))
            w.writeframes(pcm)
        state.write_bytes((json.dumps(trace, separators=(',', ':'))+'\n').encode())
        peak = max(map(abs, s))
        if peak >= 32767:
            raise RuntimeError('clipping')
        receipt['arms'][name] = dict(peak=peak, wav_sha256=digest(wav), trace_sha256=digest(state))
    (out/'receipt.json').write_bytes((json.dumps(receipt, indent=2)+'\n').encode())
    print(json.dumps(receipt, indent=2))


def fixture():
    a = dict(bpm=96, warp=15, variation=9, patterns=[[3,5],[8,129],[5,11]])
    b = dict(bpm=173, warp=-47, variation=31, patterns=[[16,32769],[7,25],[4,9]])
    bank = dict(format='chronomorph-scenes', version=1, slots=[a,None,b,None])
    raw = json.dumps(bank, separators=(',', ':'))+'\n'
    invalid = ['{}', ' '*2049, raw.replace('"version":1','"version":true'),
               raw.replace('32769','65536'), raw.replace('"bpm":96','"bpm":221'),
               json.dumps(dict(bank, slots=[None]*4))]
    for bad in invalid:
        try:
            decode(bad)
        except ValueError:
            continue
        raise RuntimeError('invalid bank accepted')
    return raw


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('library')
    p.add_argument('outdir')
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--bank', type=pathlib.Path)
    mode.add_argument('--self-test', action='store_true')
    p.add_argument('--seconds', type=int, default=2)
    p.add_argument('--seed', type=int, default=17)
    p.add_argument('--preset', type=int, default=0)
    a = p.parse_args()
    if a.self_test:
        raw = fixture()
    else:
        with a.bank.open('rb') as f:
            raw = f.read(8193).decode('utf-8')
    run(bind(a.library), raw, a.seconds, a.seed, a.preset, a.outdir, a.self_test)


if __name__ == '__main__':
    main()
