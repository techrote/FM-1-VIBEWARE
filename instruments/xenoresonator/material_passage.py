"""Authored 12 s native performance and matched uncoupled control; no wire ABI."""
import array
import ctypes as C
import hashlib
import json
from pathlib import Path
import sys
import wave

RATE, BLOCK, COUNT = 24000, 1200, 240
# (50 ms block, note, velocity, material, excitation, damping)
STRIKES = {
    0: (48, 96, 0, 72, 4), 13: (55, 78, 0, 48, 10),
    26: (51, 112, 1, 95, 3), 39: (60, 118, 2, 110, 0),
    55: (48, 96, 2, 100, 2), 63: (55, 72, 2, 66, 6),
    76: (63, 110, 2, 100, 2), 90: (58, 86, 1, 72, 5),
    104: (43, 118, 3, 120, 0), 111: (50, 82, 3, 100, 8),
    118: (55, 96, 3, 115, 0), 130: (48, 114, 2, 100, 1),
    146: (60, 96, 0, 60, 4), 159: (67, 82, 1, 58, 6),
    174: (63, 110, 2, 100, 0), 190: (48, 118, 2, 110, 0),
    214: (36, 127, 3, 127, 0),
}
RELEASES = {9, 22, 35, 48, 61, 73, 86, 101, 108, 116, 125,
            142, 155, 170, 185, 204}


def render(lib, coupled):
    lib.live_reset()
    pcm, trace = array.array('h'), []
    samples, levels = (C.c_int16 * BLOCK)(), (C.c_uint32 * 6)()
    note, velocity, material, excitation, damping = STRIKES[0]
    for i in range(COUNT):
        event = 0
        if i in STRIKES:
            note, velocity, material, excitation, damping = STRIKES[i]
            event = 1
        elif i in RELEASES:
            event = 2
        # Engage coupling during an existing strike, not by retriggering it.
        coupling = (0 if i < 40 else 127 if i < 104 else
                    80 if i < 174 else 110) if coupled else 0
        if i == 191:
            damping = 100  # live damping of previous strike
        if i == 215:
            lib.live_panic()  # interrupt active strike
        lib.live_block(material, excitation, damping, coupling, note, velocity,
                       event, samples, levels)
        pcm.extend(samples)
        trace.append([i, event, material, excitation, damping, coupling, note,
                      velocity, *levels])
    return pcm, trace


def raw(pcm):
    copy = array.array('h', pcm)
    if sys.byteorder != 'little':
        copy.byteswap()
    return copy.tobytes()


def main():
    lib = C.CDLL(str(Path(sys.argv[1]).resolve()))
    lib.live_reset.argtypes = lib.live_panic.argtypes = []
    lib.live_reset.restype = lib.live_panic.restype = None
    lib.live_block.argtypes = [C.c_uint] * 7 + [C.POINTER(C.c_int16), C.POINTER(C.c_uint32)]
    lib.live_block.restype = None
    out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
    a, ta = render(lib, True)
    b, tb = render(lib, False)
    assert (a, ta) == render(lib, True) and (b, tb) == render(lib, False)
    assert len(a) == len(b) == RATE * 12
    assert a[:40*BLOCK] == b[:40*BLOCK] and any(a[:40*BLOCK])
    assert ta[40][1] == 0 and any(ta[40][-3:])
    assert not any(v for row in tb for v in row[-3:])
    assert a[40*BLOCK:41*BLOCK] != b[40*BLOCK:41*BLOCK]
    assert all(not any(p[215*BLOCK:]) and any(p[214*BLOCK:215*BLOCK]) for p in (a,b))
    assert all(not any(row[-6:]) for t in (ta,tb) for row in t[215:])
    assert all(max(map(abs,p)) < 24000 for p in (a,b))
    results = {}
    for name, p, trace in [('coupled', a, ta), ('uncoupled', b, tb)]:
        data = raw(p)
        with wave.open(str(out / (name + '.wav')), 'wb') as w:
            w.setparams((1, 2, RATE, 0, 'NONE', 'not compressed'))
            w.writeframes(data)
        results[name] = {'pcm_sha256': hashlib.sha256(data).hexdigest(),
                         'peak': max(map(abs,p)), 'trace': trace}
    receipt = {'rate': RATE, 'block': BLOCK, 'frames': len(a),
               'matched_prefix_frames': 40*BLOCK,
               'changed_first_intervention_frames': sum(x != y for x,y in zip(a[40*BLOCK:41*BLOCK], b[40*BLOCK:41*BLOCK])),
               'panic_silent_frames': (COUNT-215)*BLOCK,
               'trace_columns': ['block','event','material','excitation','damping','coupling','note','velocity','A0','A1','A2','B0','B1','B2'],
               'results': results}
    (out / 'receipt.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k:v for k,v in receipt.items() if k != 'results'}, sort_keys=True))


if __name__ == '__main__':
    main()
