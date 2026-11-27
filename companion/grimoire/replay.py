"""Offline, actual-core Orbit Passage widget replay; never device telemetry."""
import argparse
import ctypes as C
import hashlib
import json
import math
from pathlib import Path
import struct
import wave

RATE, BLOCK = 24000, 1200
NOTES = (24, 48, 72, 60, 96, 72, 48, 36)


class Orbit(C.Structure):
    _fields_ = [("phase", C.c_uint32 * 3), ("env", C.c_uint32),
                ("energy", C.c_uint32), ("ticks", C.c_uint32),
                ("low", C.c_int32), ("x", C.c_uint8), ("y", C.c_uint8),
                ("preset", C.c_uint8), ("gate", C.c_uint8)]


class Session(C.Structure):
    _fields_ = [("core", Orbit), ("generation", C.c_uint32),
                ("connected", C.c_uint8)]


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def bind(path):
    lib = C.CDLL(str(Path(path).resolve()))
    for name, args, result in (
        ("os_init", [C.POINTER(Session)], None),
        ("os_connect", [C.POINTER(Session), C.c_uint], C.c_uint32),
        ("os_disconnect", [C.POINTER(Session)], None),
        ("os_event", [C.POINTER(Session), C.c_uint32, C.c_uint, C.c_uint, C.c_uint], C.c_int),
        ("os_render", [C.POINTER(Session), C.POINTER(C.c_int16), C.c_size_t], None),
    ):
        fn = getattr(lib, name)
        fn.argtypes, fn.restype = args, result
    return lib


def render(lib):
    s = Session()
    lib.os_init(C.byref(s))
    generation = lib.os_connect(C.byref(s), 1)
    require(generation == 1, "initial session")
    buf = (C.c_int16 * BLOCK)()
    frames, pcm = [], bytearray()

    def event(op, a=0, b=0):
        require(lib.os_event(C.byref(s), generation, op, a, b) == 1, "event rejected")

    for p in range(3):
        event(3, p)
        require(not s.core.gate and not s.core.env and not s.core.ticks, "preset reset")
        event(1, NOTES[0], 20)
        event(2, 1)
        for k in range(80):
            if k < 64 and k % 8 == 0:
                before = (tuple(s.core.phase), s.core.env, s.core.ticks, s.core.gate)
                event(1, NOTES[(k // 8 + p) % 8], 20 + (k * 7 + p * 23) % 108)
                require(before == (tuple(s.core.phase), s.core.env, s.core.ticks, s.core.gate),
                        "XY reset phase or envelope")
            if k == 64:
                event(2, 0)
            if k == 76:
                event(4)
            lib.os_render(C.byref(s), buf, BLOCK)
            c = s.core
            block = struct.pack("<1200h", *buf)
            peak = max(map(abs, buf))
            require(c.preset == p and c.ticks == (k + 1) * BLOCK and c.gate == (k < 64),
                    "unexpected local state")
            require(0 <= c.x <= 127 and 0 <= c.y <= 127 and c.env <= 32767 and
                    c.energy <= 28000 and peak <= 28000, "snapshot outside bounds")
            if k >= 68:
                require(peak == 0 and c.env == 0, "release tail")
            if k >= 76:
                require(c.energy == 0, "panic energy")
            pcm.extend(block)
            frames.append({"end_sample": len(pcm) // 2, "preset_epoch": p,
                           "ticks": c.ticks, "preset": c.preset, "x": c.x, "y": c.y,
                           "gate": c.gate, "env": c.env, "energy": c.energy,
                           "phase_u16": [v >> 16 for v in c.phase], "peak": peak,
                           "rms": math.isqrt(sum(v * v for v in buf) // BLOCK),
                           "pcm_sha256": hashlib.sha256(block).hexdigest()})
    # Reconnect safety is local session evidence, separate from the score.
    lib.os_disconnect(C.byref(s))
    require(lib.os_connect(C.byref(s), 2) == 0, "unsupported version accepted")
    require(lib.os_connect(C.byref(s), 1) == 2, "reconnect generation")
    before = bytes(s)
    for gen, op, a, b in ((1, 2, 1, 0), (2, 1, 128, 0), (2, 3, 3, 0)):
        require(not lib.os_event(C.byref(s), gen, op, a, b) and bytes(s) == before,
                "invalid or stale event changed local state")
    lib.os_render(C.byref(s), buf, BLOCK)
    require(not any(buf), "reconnect replayed sound")
    return {"schema": "grimoire.orbit-passage.local-replay.v1",
            "state_source": "offline native core, not device telemetry",
            "sample_rate_hz": RATE, "block_frames": BLOCK, "snapshot_rate_hz": RATE // BLOCK,
            "pcm_encoding": "mono signed 16-bit little-endian",
            "pcm_sha256": hashlib.sha256(pcm).hexdigest(), "snapshots": frames}, bytes(pcm)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("library")
    parser.add_argument("reference_wav")
    parser.add_argument("output")
    args = parser.parse_args()
    lib = bind(args.library)
    replay, pcm = render(lib)
    require((replay, pcm) == render(lib), "non-deterministic replay")
    with wave.open(args.reference_wav, "rb") as f:
        require((f.getnchannels(), f.getsampwidth(), f.getframerate(), f.getnframes()) ==
                (1, 2, RATE, RATE * 12), "reference WAV format")
        require(pcm == f.readframes(f.getnframes()), "score PCM differs from reference WAV")
    data = (json.dumps(replay, separators=(",", ":"), sort_keys=True) + "\n").encode("utf-8")
    Path(args.output).write_bytes(data)
    print(f"PASS: {len(replay['snapshots'])} snapshots; {len(pcm)//2} matched PCM frames; "
          f"replay SHA256 {hashlib.sha256(data).hexdigest()}")


if __name__ == "__main__":
    main()
