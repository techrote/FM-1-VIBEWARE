"""Independent PCM/clock witness for the Lattice Variations exact-source score."""
import hashlib
import json
from pathlib import Path
import struct
import sys
import wave

NAMES = ("lattice-variations", "fixed-pattern-control")
RATE, BLOCK, COUNT = 24000, 1200, 420

def verify(root):
    root = Path(root)
    receipt = json.loads((root/"receipt.json").read_text())
    bank = json.loads((root/"scene-bank.json").read_text())
    assert bank["format"] == "chronomorph-scenes" and bank["version"] == 1
    assert len(bank["slots"]) == 4
    assert receipt["rate"] == RATE and receipt["frames"] == BLOCK*COUNT
    samples, traces = [], []
    for name in NAMES:
        wav, trace = root/(name+".wav"), root/(name+".json")
        arm = receipt["arms"][name]
        assert hashlib.sha256(wav.read_bytes()).hexdigest() == arm["wav_sha256"]
        assert hashlib.sha256(trace.read_bytes()).hexdigest() == arm["trace_sha256"]
        with wave.open(str(wav), "rb") as w:
            assert (w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()) == (1, 2, RATE, BLOCK*COUNT)
            pcm = struct.unpack("<%dh" % (BLOCK*COUNT), w.readframes(BLOCK*COUNT))
        assert 0 < max(map(abs, pcm)) == arm["peak"] < 32767
        assert not any(pcm[400*BLOCK:])
        tr = json.loads(trace.read_text())
        assert len(tr) == COUNT
        for i, snap in enumerate(tr):
            cue = min(i//100, 3)
            slot = bank["slots"][cue]
            pat = bank["slots"][0 if name == NAMES[1] else cue]["patterns"]
            assert snap["block"] == i and snap["end_frame"] == (i+1)*BLOCK
            assert snap["cue"] == cue+1 and snap["playing"] == int(i < 400)
            assert [snap[k] for k in ("bpm","warp","variation")] == [slot[k] for k in ("bpm","warp","variation")]
            assert snap["patterns"] == [v for pair in pat for v in pair]
            assert len(snap["lanes"]) == 3
            for j, lane in enumerate(snap["lanes"]):
                assert len(lane) == 5 and 0 <= lane[0] < pat[j][0]
                assert 0 <= lane[2] <= lane[1] and 0 <= lane[3] < 4 and 0 <= lane[4] < 144000000
                if i:
                    assert 0 <= lane[1] - tr[i-1]["lanes"][j][1] <= 2
            if i >= 400:
                assert snap["lanes"] == tr[i-1]["lanes"]
        assert arm["hits"] == [l[2] for l in tr[-1]["lanes"]]
        samples.append(pcm)
        traces.append(tr)
    for a, b in zip(*traces):
        assert [(l[1],l[4]) for l in a["lanes"]] == [(l[1],l[4]) for l in b["lanes"]]
    changes = []
    for start,end in ((0,5),(5,10),(10,15),(15,20),(20,21)):
        a,b = [s[start*RATE:end*RATE] for s in samples]
        diff = sum(x != y for x,y in zip(a,b))
        assert (diff > 0) == (start in (5,10,15))
        assert bool(any(a)) == bool(any(b)) == (start < 20)
        changes.append(diff)
    assert changes == receipt["changed_samples"]
    return {"changed_samples": changes, "clock_blocks": COUNT, "silent_tail_samples_per_arm": RATE}

def compare(original, fresh):
    original, fresh = Path(original), Path(fresh)
    names = [n+ext for n in NAMES for ext in (".wav",".json")] + ["scene-bank.json","receipt.json"]
    for name in names:
        assert (original/name).read_bytes() == (fresh/name).read_bytes(), name
    a,b = verify(original),verify(fresh)
    assert a == b
    return a

if __name__ == "__main__":
    print(json.dumps(compare(*sys.argv[1:]), sort_keys=True))
