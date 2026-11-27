"""Ecophon population-feedback performance; actual local native core, not a wire protocol."""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import struct
import wave

RATE, FRAMES, BLOCKS = 24000, 2400, 320
BASE = (180, 200, 40, 0)
SEEDS = (42, 1, 17, 255, 4294967295)


def target(block):
    return 5 if block < 120 else 3 if block < 220 else 6


def regulate(previous, living, goal):
    """Bounded negative feedback, no clock or RNG. One update per completed block.

    Pressure follows population error; fertility acts oppositely. A one-agent
    dead band and bounded 12-unit slew limit violent environmental transitions.
    """
    if (type(living) is not int or type(goal) is not int or not 0 <= living <= 8
            or not 1 <= goal <= 8 or len(previous) != 4 or previous[3] != 0
            or any(type(v) is not int or not 0 <= v <= 255 for v in previous)):
        raise ValueError("invalid population")
    err = living - goal
    if err > 1:
        wanted = (75, 100, 160, 0)
    elif err < -1:
        wanted = (255, 220, 0, 0)
    else:
        wanted = (180, 190, 60, 0)
    return tuple(max(v-12, min(v+12, w)) for v, w in zip(previous, wanted))


def open_core(library):
    lib = C.CDLL(str(Path(library).resolve()))
    lib.ecof_reset.argtypes = [C.c_uint32, C.c_uint]
    lib.ecof_reset.restype = None
    lib.ecof_panic.argtypes = []
    lib.ecof_panic.restype = None
    lib.ecof_step.argtypes = [C.c_uint]*4 + [C.POINTER(C.c_int16), C.POINTER(C.c_uint32)]
    lib.ecof_step.restype = C.c_int
    return lib


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def render(lib, seed, mode, yoked=None):
    if mode not in ('feedback', 'steady', 'yoked') or (mode == 'yoked' and len(yoked or ()) != BLOCKS):
        raise ValueError('invalid arm')
    lib.ecof_reset(seed, 0)
    buf = (C.c_int16 * FRAMES)()
    snap = (C.c_uint32 * 56)()
    pcm, rows = bytearray(), []
    controls, living = BASE, 5
    for block in range(BLOCKS):
        goal = target(block)
        if block >= 40:
            if mode == 'feedback':
                controls = regulate(controls, living, goal)
            elif mode == 'yoked':
                controls = tuple(yoked[block])
        require(lib.ecof_step(*controls, buf, snap) == 56, 'native step rejected')
        s = list(snap)
        require(s[0] == 10*(block+1) and s[7:12] == [0, 0, *controls[:3]], 'invalid control/tick echo')
        living = sum(s[16:56:5])
        require(0 <= living <= 8 and living == 5+s[1]-s[2], 'population accounting')
        require(all(0 <= r <= 4096 for r in s[12:16]), 'resource bounds')
        require(max(map(abs, buf)) <= 24000, 'headroom')
        raw = struct.pack('<2400h', *buf)
        pcm.extend(raw)
        rows.append(dict(frame_end=(block+1)*FRAMES, goal=goal, living=living,
                         controls=list(controls), births=s[1], deaths=s[2], resources=s[12:16],
                         pcm_sha256=hashlib.sha256(raw).hexdigest()))
    lib.ecof_panic()
    require(lib.ecof_step(*controls, buf, snap) == 56 and snap[8] == 1 and not any(buf), 'panic not silent')
    return bytes(pcm), rows


def metrics(rows):
    return dict(error=sum(abs(r['living']-r['goal']) for r in rows[40:]),
                empty_blocks=sum(r['living']==0 for r in rows[40:]),
                living_at_end=rows[-1]['living'], births=rows[-1]['births'], deaths=rows[-1]['deaths'])


def run(library, output):
    for living in range(9):
        for goal in range(1,9):
            for base in ((0,0,0,0), (255,255,255,0), BASE):
                v = regulate(base, living, goal)
                require(all(0 <= x <= 255 and abs(x-y) <= 12 for x,y in zip(v,base)) and v[3]==0, 'regulator bounds')
    for base, living, goal in ((BASE,-1,5),(BASE,5,0),(BASE,True,5),((256,0,0,0),5,5)):
        try:
            regulate(base,living,goal)
        except ValueError:
            pass
        else:
            raise RuntimeError('invalid regulator input accepted')
    lib = open_core(library)
    output.mkdir(parents=True, exist_ok=True)
    reference = render(lib, SEEDS[0], 'feedback')
    require(reference == render(lib, SEEDS[0], 'feedback'), 'feedback repeat drift')
    schedule = [r['controls'] for r in reference[1]]
    summary = {}
    for seed in SEEDS:
        arms = {mode: render(lib, seed, mode, schedule) for mode in ('feedback', 'steady', 'yoked')}
        ref = arms['feedback']
        for mode, (pcm, rows) in arms.items():
            require(pcm[:40*FRAMES*2] == ref[0][:40*FRAMES*2] and rows[:40] == ref[1][:40], 'unmatched prefix')
            require(len(pcm)==BLOCKS*FRAMES*2, 'wrong length')
            require(any(pcm), 'no audio')
        require(ref[0] != arms['steady'][0], 'feedback not audible in PCM')
        require(ref == render(lib, seed, 'feedback'), 'seed repeat drift')
        require(all(all(abs(a-b)<=12 for a,b in zip(x['controls'],y['controls']))
                    for x,y in zip(ref[1],ref[1][1:])), 'control slew exceeded')
        if seed == SEEDS[0]:
            require(ref == arms['yoked'], 'yoked reference mismatch')
        summary[str(seed)] = {mode: metrics(rows) for mode, (_, rows) in arms.items()}
        if seed == SEEDS[0]:
            for mode in ('feedback', 'steady'):
                pcm, rows = arms[mode]
                with wave.open(str(output / ('population-'+mode+'.wav')), 'wb') as w:
                    w.setparams((1, 2, RATE, 0, 'NONE', 'not compressed'))
                    w.writeframes(pcm)
                (output / ('population-'+mode+'.json')).write_bytes((json.dumps(rows, sort_keys=True, separators=(',', ':'))+'\n').encode())
    require(any(summary[str(s)]['feedback'] != summary[str(s)]['yoked'] for s in SEEDS[1:]), 'no feedback-specific effect')
    (output / 'population-summary.json').write_bytes((json.dumps(summary, sort_keys=True, separators=(',', ':'))+'\n').encode())
    print(json.dumps(summary, indent=2))
    print('PASS actual-core population control, matched prefix, seeded repetition, yoked reference, bounded state and silent panic')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('library')
    p.add_argument('output', type=Path)
    a = p.parse_args()
    run(a.library, a.output)
