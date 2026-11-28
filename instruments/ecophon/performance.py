"""Render an authored ecological performance and matched native-core controls.

Uses the local fixture ABI only; no device telemetry or wire protocol.
"""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import struct
import wave

FRAMES = 2400
RATE = 24000
BLOCKS = 240
SEED = 42
BASE = (180, 200, 40)
DROUGHT = (0, 0, 255)
RECOVERY = (255, 220, 0)
ARMS = ("habitat-arc", "steady-control", "frozen-control")


def ramp(a, b, n, length):
    return tuple((x * (length - n) + y * n) // length for x, y in zip(a, b))


def controls(block, arm):
    if arm not in ARMS or not 0 <= block < BLOCKS:
        raise ValueError("invalid score position")
    if block < 40 or arm == "steady-control":
        return (*BASE, 0)
    if block < 80:
        v = ramp(BASE, DROUGHT, block - 39, 40)
    elif block < 120:
        v = DROUGHT
    elif block < 160:
        v = ramp(DROUGHT, RECOVERY, block - 119, 40)
    else:
        v = RECOVERY
    return (*v, int(arm == "frozen-control"))


def render(lib, arm):
    lib.ecof_reset(SEED, 0)
    pcm = bytearray()
    timeline = []
    samples = (C.c_int16 * FRAMES)()
    snap = (C.c_uint32 * 56)()
    for block in range(BLOCKS):
        v = controls(block, arm)
        if lib.ecof_step(*v, samples, snap) != 56:
            raise RuntimeError("native fixture rejected score")
        s = list(snap)
        if s[0] != (block + 1) * 10 or s[7] != v[3] or s[9:12] != list(v[:3]):
            raise RuntimeError("native snapshot does not match score")
        if max(map(abs, samples)) > 24000:
            raise RuntimeError("headroom exceeded")
        pcm.extend(struct.pack("<2400h", *samples))
        timeline.append(dict(ticks=s[0], births=s[1], deaths=s[2], gifts=s[3],
                             moves=s[4], consumed=s[5], controls=list(v), resources=s[12:16],
                             living=sum(s[16:56:5]), energy=sum(s[i+4] for i in range(16,56,5) if s[i])))
    lib.ecof_panic()
    if lib.ecof_step(*BASE, 0, samples, snap) != 56 or any(samples):
        raise RuntimeError("panic not silent")
    return bytes(pcm), timeline


def run(library, output):
    lib = C.CDLL(str(Path(library).resolve()))
    lib.ecof_reset.argtypes = [C.c_uint32, C.c_uint]
    lib.ecof_reset.restype = None
    lib.ecof_panic.argtypes = []
    lib.ecof_panic.restype = None
    lib.ecof_step.argtypes = [C.c_uint]*4 + [C.POINTER(C.c_int16), C.POINTER(C.c_uint32)]
    lib.ecof_step.restype = C.c_int
    results = {arm: render(lib, arm) for arm in ARMS}
    prefix = 40 * FRAMES * 2
    reference = results[ARMS[0]]
    for arm, result in results.items():
        if render(lib, arm) != result:
            raise RuntimeError("nondeterministic performance: " + arm)
        if result[0][:prefix] != reference[0][:prefix] or result[1][:40] != reference[1][:40]:
            raise RuntimeError("unmatched pre-intervention state")
    if len({pcm for pcm, _ in results.values()}) != len(ARMS):
        raise RuntimeError("causal PCM arms aliased")
    frozen = results["frozen-control"][1]
    for name in ("births", "deaths", "gifts", "moves", "consumed", "living", "energy"):
        if any(row[name] != frozen[39][name] for row in frozen[40:]):
            raise RuntimeError("frozen interaction advanced: " + name)
    arc = reference[1]
    if arc[119]["deaths"] <= arc[39]["deaths"] or arc[-1]["births"] <= arc[119]["births"]:
        raise RuntimeError("score did not exhibit loss and recovery")
    output.mkdir(parents=True, exist_ok=True)
    receipt = dict(seed=SEED, sample_rate=RATE, frames_per_block=FRAMES,
                   state_source="local native core, not FM-1 telemetry", arms={})
    for arm, (pcm, timeline) in results.items():
        path = output / (arm + ".wav")
        with wave.open(str(path), "wb") as w:
            w.setparams((1, 2, RATE, 0, "NONE", "not compressed"))
            w.writeframes(pcm)
        receipt["arms"][arm] = dict(wav_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                                    checkpoints=[timeline[i] for i in (39,79,119,159,239)], timeline=timeline)
    (output / "performance.json").write_text(json.dumps(receipt, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    for arm, data in receipt["arms"].items():
        print(arm, data["wav_sha256"], [(x["ticks"],x["living"],x["births"],x["deaths"]) for x in data["checkpoints"]])
    print("PASS exact repeat, matched prefix, distinct PCM, frozen counters, loss/recovery and silent panic")
    return receipt


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("library")
    p.add_argument("output", type=Path)
    a = p.parse_args()
    run(a.library, a.output)
