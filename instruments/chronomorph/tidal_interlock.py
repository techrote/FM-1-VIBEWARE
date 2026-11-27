"""Actual native Chronomorph score and matched pattern-ablation witness.

Run with a built live_bridge library: python tidal_interlock.py LIB OUTDIR.
No device transport or new ABI; each row is one 50 ms local core block.
"""
import ctypes as C
import hashlib
import json
import pathlib
import struct
import sys
import wave

RATE = 24000
FRAMES = 1200
BLOCKS = 320
ORIGINAL = (7, 73, 5, 21, 11, 1321)


def controls(block, edited):
    # Shared tempo/warp/variation/transport, only patterns differ between arms.
    bpm, warp, variation = (112, 24, 12) if block < 80 else (132, -36, 18)
    if block >= 160:
        bpm, warp, variation = 96, 54, 30
    if block >= 220:
        bpm, warp, variation = 152, -24, 6
    playing = int(not (200 <= block < 220 or block >= 300))
    pattern = ORIGINAL
    if edited:
        if 80 <= block < 160:
            pattern = (7, 19, 5, 11, 11, 595)
        elif 160 <= block < 220:
            pattern = (7, 41, 5, 9, 11, 1093)
        elif block >= 220:
            pattern = (9, 293, 7, 73, 13, 4693)
    return bpm, warp, variation, playing, pattern


def render(lib, edited):
    lib.live_reset(17, 0)
    pcm, trace = bytearray(), []
    for block in range(BLOCKS):
        bpm, warp, variation, playing, pattern = controls(block, edited)
        samples = (C.c_int16 * FRAMES)()
        snapshot = (C.c_uint32 * 15)()
        assert lib.live_block(bpm, warp, variation, playing,
                              (C.c_uint32 * 6)(*pattern), samples, snapshot) == 1
        lanes = [list(snapshot[i:i+5]) for i in range(0, 15, 5)]
        for i, lane in enumerate(lanes):
            assert lane[0] < pattern[2*i] and lane[3] < 4 and lane[4] < 144000000
            assert lane[2] <= lane[1]
        if not playing:
            assert not any(samples)
            assert trace and lanes == trace[-1]["lanes"]
        pcm.extend(struct.pack("<1200h", *samples))
        trace.append(dict(block=block, end_frame=(block+1)*FRAMES,
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
    assert (a, ta) == render(lib, True)
    assert (b, tb) == render(lib, False)
    assert a[:4*RATE*2] == b[:4*RATE*2]
    # Pattern edits must not disturb tick counts or fractional clock phase.
    for x, y in zip(ta, tb):
        assert [(l[1], l[4]) for l in x["lanes"]] == [(l[1], l[4]) for l in y["lanes"]]
    sa = struct.unpack(f"<{BLOCKS*FRAMES}h", a)
    sb = struct.unpack(f"<{BLOCKS*FRAMES}h", b)
    changes = {}
    for start, end in [(0, 4), (4, 8), (8, 10), (10, 11), (11, 15), (15, 16)]:
        n = sum(x != y for x, y in zip(sa[start*RATE:end*RATE], sb[start*RATE:end*RATE]))
        assert (n > 0) == (start in (4, 8, 11))
        changes[f"{start}-{end}s"] = n
    assert any(sa[11*RATE:15*RATE]) and any(sb[11*RATE:15*RATE])
    out = pathlib.Path(out)
    out.mkdir(parents=True, exist_ok=True)
    receipt = {"rate": RATE, "frames": len(sa), "changed_samples": changes,
               "trace_columns": ["step", "ticks", "hits", "cycle", "clock"],
               "clock_phase_identity": True, "repeat_identity": True, "arms": {}}
    for name, pcm, trace, samples in [("tidal-interlock", a, ta, sa), ("fixed-pattern-control", b, tb, sb)]:
        path = out / (name + ".wav")
        with wave.open(str(path), "wb") as w:
            w.setparams((1, 2, RATE, 0, "NONE", "not compressed"))
            w.writeframes(pcm)
        trace_path = out / (name + ".json")
        trace_path.write_bytes((json.dumps(trace, separators=(",", ":")) + "\n").encode())
        peak = max(map(abs, samples))
        assert 0 < peak < 32767
        receipt["arms"][name] = dict(peak=peak, hits=[l[2] for l in trace[-1]["lanes"]],
            wav_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            trace_sha256=hashlib.sha256(trace_path.read_bytes()).hexdigest())
    (out / "receipt.json").write_bytes((json.dumps(receipt, indent=2) + "\n").encode())
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    main(*sys.argv[1:])
