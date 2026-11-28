"""Generate a bounded local Chronomorph clock/PCM replay from Tidal Interlock.
Usage: python companion_replay.py TIDAL_EVIDENCE OUTPUT.json
Offline actual-core state, not a device telemetry or wire protocol.
"""
import hashlib
import json
import math
import pathlib
import struct
import sys
import wave
import zlib

RATE, FRAMES, BLOCKS = 24000, 1200, 320
EXPECTED = {
    "tidal-interlock": ("dfadb7599551b54ea0243b64948f462fd80c1e521d85446b64671b9e9dc9d787", "d486c58e2430f7d48d4d60031c85855efe0989c256315ece33da043ed1d96f09"),
    "fixed-pattern-control": ("e34de50878f2bf80547725acadcfe35068ddc1a117d6bb52e6ee76b4e476f775", "3e7b8fe82d42982522f115b97486ea565d513a3f424e470aba8103b17f5fa457"),
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def arm(root, name):
    wav = root / (name + ".wav")
    trace = root / (name + ".json")
    for path, expected in zip((wav, trace), EXPECTED[name]):
        require(path.stat().st_size <= 800000, "oversize input")
        require(hashlib.sha256(path.read_bytes()).hexdigest() == expected, "source digest: " + path.name)
    rows = json.loads(trace.read_bytes())
    require(len(rows) == BLOCKS, "trace length")
    snapshots = []
    prev = [[0, 0, 0, 0, 0] for _ in range(3)]
    with wave.open(str(wav), "rb") as w:
        require((w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()) == (1, 2, RATE, BLOCKS * FRAMES), "PCM format")
        for i, row in enumerate(rows):
            require(row["block"] == i and row["end_frame"] == (i + 1) * FRAMES, "frame alignment")
            require(40 <= row["bpm"] <= 220 and -60 <= row["warp"] <= 60 and 0 <= row["variation"] <= 100 and row["playing"] in (0, 1), "control range")
            require(len(row["patterns"]) == 6 and len(row["lanes"]) == 3, "lane count")
            pcm = w.readframes(FRAMES)
            samples = struct.unpack("<1200h", pcm)
            lanes = []
            for j, lane in enumerate(row["lanes"]):
                length, mask = row["patterns"][2*j:2*j+2]
                step, ticks, hits, cycle, clock = lane
                dt, dh = ticks - prev[j][1], hits - prev[j][2]
                require(1 <= length <= 16 and 0 <= mask < 1 << length and 0 <= step < length and 0 <= cycle < 4 and 0 <= clock < 144000000, "lane bounds")
                require(0 <= dh <= dt <= 2 and hits <= ticks, "event delta")
                lanes.append([length, mask, step, ticks, hits, cycle, clock, dt, dh])
            if not row["playing"]:
                require(not any(samples) and row["lanes"] == prev, "stopped state")
            snapshots.append([row["end_frame"], row["bpm"], row["warp"], row["variation"], row["playing"], lanes, max(map(abs, samples)), math.isqrt(sum(s*s for s in samples)//FRAMES), f"{zlib.crc32(pcm):08x}"])
            prev = row["lanes"]
    return {"wav_sha256": EXPECTED[name][0], "trace_sha256": EXPECTED[name][1], "snapshots": snapshots}


def main(root, output):
    root = pathlib.Path(root)
    result = {"instrument": "chronomorph", "profile_version": 1, "fixture_version": 1,
              "source": "offline actual native core; not device telemetry", "sample_rate": RATE,
              "frames_per_snapshot": FRAMES, "snapshots_per_arm": BLOCKS,
              "snapshot_columns": ["end_frame", "bpm", "warp", "variation", "playing", "lanes", "pcm_peak", "pcm_rms_floor", "pcm_crc32"],
              "lane_columns": ["length", "mask", "step", "ticks", "hits", "cycle", "clock", "tick_delta", "hit_delta"],
              "clock_modulus": 144000000, "arms": {name: arm(root, name) for name in EXPECTED}}
    a, b = (result["arms"][name]["snapshots"] for name in EXPECTED)
    require(a[:80] == b[:80], "common introduction")
    for x, y in zip(a, b):
        require(x[:5] == y[:5] and [(l[3], l[6]) for l in x[5]] == [(l[3], l[6]) for l in y[5]], "clock continuity")
    data = (json.dumps(result, separators=(",", ":")) + "\n").encode()
    require(len(data) < 200000, "replay budget")
    pathlib.Path(output).write_bytes(data)
    print("640 snapshots; SHA256", hashlib.sha256(data).hexdigest())


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    main(*sys.argv[1:])
