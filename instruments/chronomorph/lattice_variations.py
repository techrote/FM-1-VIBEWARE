"""Render the four live factory cues through the actual native bridge.

Usage: python lattice_variations.py LIB OUTDIR
The matched arm keeps the opening pattern but follows identical temporal
controls. No device transport; each snapshot is local core state.
"""
import ctypes as C
import hashlib
import json
import pathlib
import struct
import sys
import wave

RATE, FRAMES, BLOCKS = 24000, 1200, 420
CUES = (
    (112, 24, 12, (7, 73, 5, 21, 11, 1321)),
    (124, -36, 25, (7, 19, 5, 11, 11, 585)),
    (84, 48, 38, (9, 293, 7, 73, 13, 4693)),
    (72, -12, 4, (7, 9, 5, 4, 11, 129)),
)


def render(lib, edited):
    lib.live_reset(17, 0)
    pcm, trace = bytearray(), []
    for block in range(BLOCKS):
        cue = min(block // 100, 3)
        bpm, warp, variation, pattern = CUES[cue]
        if not edited:
            pattern = CUES[0][3]
        playing = int(block < 400)
        samples = (C.c_int16 * FRAMES)()
        snapshot = (C.c_uint32 * 15)()
        assert lib.live_block(bpm, warp, variation, playing,
                              (C.c_uint32 * 6)(*pattern), samples, snapshot) == 1
        lanes = [list(snapshot[i:i+5]) for i in range(0, 15, 5)]
        for i, lane in enumerate(lanes):
            assert lane[0] < pattern[2*i] and lane[2] <= lane[1]
            assert lane[3] < 4 and lane[4] < 144000000
            if trace:
                assert 0 <= lane[1] - trace[-1]['lanes'][i][1] <= 2
        if not playing:
            assert not any(samples) and lanes == trace[-1]['lanes']
        pcm.extend(struct.pack('<1200h', *samples))
        trace.append(dict(block=block, end_frame=(block+1)*FRAMES, cue=cue+1,
                          bpm=bpm, warp=warp, variation=variation, playing=playing,
                          patterns=list(pattern), lanes=lanes))
    return bytes(pcm), trace


def main(library, out):
    lib = C.CDLL(str(pathlib.Path(library).resolve(strict=True)))
    lib.live_reset.argtypes = [C.c_uint32, C.c_uint]
    lib.live_reset.restype = None
    lib.live_block.argtypes = [C.c_uint, C.c_int, C.c_uint, C.c_uint,
                               C.POINTER(C.c_uint32), C.POINTER(C.c_int16),
                               C.POINTER(C.c_uint32)]
    lib.live_block.restype = C.c_int
    a, ta = render(lib, True)
    b, tb = render(lib, False)
    assert (a, ta) == render(lib, True) and (b, tb) == render(lib, False)
    for x, y in zip(ta, tb):
        assert [(l[1], l[4]) for l in x['lanes']] == [(l[1], l[4]) for l in y['lanes']]
    sa = struct.unpack(f'<{BLOCKS*FRAMES}h', a)
    sb = struct.unpack(f'<{BLOCKS*FRAMES}h', b)
    changes = []
    for start, end in ((0, 5), (5, 10), (10, 15), (15, 20), (20, 21)):
        x, y = sa[start*RATE:end*RATE], sb[start*RATE:end*RATE]
        n = sum(i != j for i, j in zip(x, y))
        assert (n > 0) == (start in (5, 10, 15))
        assert bool(any(x)) == bool(any(y)) == (start < 20)
        changes.append(n)
    out = pathlib.Path(out)
    out.mkdir(parents=True, exist_ok=True)
    bank = dict(format='chronomorph-scenes', version=1, slots=[
        dict(bpm=b, warp=w, variation=v, patterns=[list(p[i:i+2]) for i in (0, 2, 4)])
        for b, w, v, p in CUES])
    (out/'scene-bank.json').write_bytes((json.dumps(bank, separators=(',', ':'))+'\n').encode())
    receipt = dict(rate=RATE, frames=len(sa), changed_samples=changes,
                   clock_phase_identity=True, repeat_identity=True, arms={})
    for name, pcm, trace, samples in [('lattice-variations', a, ta, sa),
                                      ('fixed-pattern-control', b, tb, sb)]:
        path = out/(name+'.wav')
        with wave.open(str(path), 'wb') as w:
            w.setparams((1, 2, RATE, 0, 'NONE', 'not compressed'))
            w.writeframes(pcm)
        trace_path = out/(name+'.json')
        trace_path.write_bytes((json.dumps(trace, separators=(',', ':'))+'\n').encode())
        peak = max(map(abs, samples))
        assert 0 < peak < 32767
        receipt['arms'][name] = dict(peak=peak, hits=[l[2] for l in trace[-1]['lanes']],
            wav_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            trace_sha256=hashlib.sha256(trace_path.read_bytes()).hexdigest())
    (out/'receipt.json').write_bytes((json.dumps(receipt, indent=2)+'\n').encode())
    print(json.dumps(receipt, indent=2))


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    main(*sys.argv[1:])
