"""Generate bounded offline Ecophon companion snapshots from actual native PCM.

This is a replay fixture, NOT a transport or device telemetry format.
"""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import struct
from performance import ARMS, BLOCKS, FRAMES, RATE, SEED, controls


def require(ok, reason):
    if not ok:
        raise RuntimeError(reason)


def replay(lib, arm, inject_invalid=False):
    lib.ecof_reset(SEED, 0)
    pcm = (C.c_int16 * FRAMES)()
    snap = (C.c_uint32 * 56)()
    rows = []
    for block in range(BLOCKS):
        v = controls(block, arm)
        if inject_invalid and block % 17 == 0:
            old = bytes(pcm), bytes(snap)
            require(lib.ecof_step(256, *v[1:], pcm, snap) == 0, "invalid control accepted")
            require((bytes(pcm), bytes(snap)) == old, "invalid control changed output")
        require(lib.ecof_step(*v, pcm, snap) == 56, "snapshot width")
        s = list(snap)
        agents = [s[i:i+5] for i in range(16, 56, 5)]
        require(s[0] == (block+1)*10 and s[6:12] == [0, v[3], 0, *v[:3]], "control/tick echo")
        require(all(0 <= r <= 4096 for r in s[12:16]), "resource range")
        require(all(a in (0,1) and 0 <= p < 4 and sp in (0,1) and 0 <= t < 16 and 0 <= e <= 4096 and (a or not e)
                    for a,p,sp,t,e in agents), "agent range")
        require(sum(a[0] for a in agents) == 5+s[1]-s[2], "population accounting")
        require(not rows or all(a >= b for a,b in zip(s[1:6], rows[-1]["counters"][1:])), "counter regression")
        if v[3] and rows:
            require(agents == rows[-1]["agents"] and s[1:6] == rows[-1]["counters"][1:], "frozen agent drift")
        require(max(map(abs, pcm)) <= 24000, "PCM headroom")
        raw = struct.pack("<2400h", *pcm)
        rows.append(dict(frame_end=(block+1)*FRAMES, controls=list(v), counters=s[:6],
                         resources=s[12:16], agents=agents, pcm_sha256=hashlib.sha256(raw).hexdigest()))
    lib.ecof_panic()
    require(lib.ecof_step(*controls(BLOCKS-1, arm), pcm, snap) == 56 and snap[8] == 1 and not any(pcm), "panic silence")
    return rows


def run(library, output):
    lib = C.CDLL(str(Path(library).resolve()))
    lib.ecof_reset.argtypes = [C.c_uint32, C.c_uint]
    lib.ecof_reset.restype = None
    lib.ecof_panic.argtypes = []
    lib.ecof_panic.restype = None
    lib.ecof_step.argtypes = [C.c_uint]*4 + [C.POINTER(C.c_int16), C.POINTER(C.c_uint32)]
    lib.ecof_step.restype = C.c_int
    arms = {arm: replay(lib, arm) for arm in ARMS}
    for arm, rows in arms.items():
        require(replay(lib, arm, True) == rows, "invalid control/reset altered replay")
        require(rows[:40] == arms[ARMS[0]][:40], "unmatched prefix")
    require(len({tuple(r["pcm_sha256"] for r in rows) for rows in arms.values()}) == len(ARMS), "audio arms aliased")
    data = dict(schema="ecophon-offline-replay-v1", state_source="local native core, not device telemetry",
                wire_protocol=None, sample_rate=RATE, frames_per_snapshot=FRAMES, seed=SEED,
                control_fields=["fertility","sharing","pressure","frozen"],
                counter_fields=["ticks","births","deaths","gifts","moves","consumed"],
                agent_fields=["alive","patch","species","trait","energy"], arms=arms)
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(data, sort_keys=True, separators=(",", ":"))+"\n").encode("utf-8")
    output.write_bytes(payload)
    print("PASS 720 snapshots, matched prefix, population accounting, frozen agents, invalid control rejection, reset and panic")
    print("Replay SHA256", hashlib.sha256(payload).hexdigest())


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("library")
    p.add_argument("output", type=Path)
    a = p.parse_args()
    run(a.library, a.output)
