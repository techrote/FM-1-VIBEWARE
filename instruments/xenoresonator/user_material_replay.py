"""Actual native held-recall score; local authoring semantics, not device telemetry."""
import ctypes as C
import hashlib
import json
import math
from pathlib import Path
import struct
import sys
import wave

RATE, BLOCK, SPAN, TAIL = 24000, 1200, 30, 20
BASE = (2, 105, 0, 100)
# Ordered p/e/d/c documents; note and velocity belong to the score, not the slot.
SLOTS = ((0, 55, 0, 78), (1, 72, 0, 35), (2, 118, 28, 12), (3, 110, 0, 92))
NOTES = ((48, 55, 60, 43), (51, 58, 63, 46),
         (43, 50, 55, 36), (48, 51, 55, 48))
ARMS = ('fixed', 'macros-only', 'full-recall')


def render(lib, arm):
    lib.live_reset()
    pcm, trace = bytearray(), []
    samples, levels = (C.c_int16 * BLOCK)(), (C.c_uint32 * 6)()
    held = False
    controls, note, velocity = BASE, 48, 110
    for i in range(len(SLOTS)*SPAN + TAIL):
        phrase, offset = divmod(i, SPAN)
        event, action = 0, 'none'
        if phrase < len(SLOTS):
            if offset in (0, 10, 20, 28):
                controls = BASE
                index = (0, 10, 20, 28).index(offset)
                note, velocity = NOTES[phrase][index], (110, 92, 118, 127)[index]
                event, held, action = 1, True, 'strike'
            elif offset in (1, 11, 21):
                assert held
                action = 'recall'
                if arm != 'fixed':
                    slot = SLOTS[phrase]
                    controls = slot if arm == 'full-recall' else (BASE[0], *slot[1:])
            elif offset in (3, 13, 23):
                assert held
                action = 'manual-xy'
                if arm != 'fixed':
                    controls = (controls[0], 80, 48, controls[3])
            elif offset in (6, 16, 26):
                event, held, action = 2, False, 'release'
            elif offset == 29:
                assert held
                lib.live_panic()
                held, action = False, 'panic'
        lib.live_block(*controls, note, velocity, event, samples, levels)
        raw = struct.pack('<1200h', *samples)
        pcm.extend(raw)
        trace.append(dict(block=i, action=action, event=event, held=held,
                          controls=list(controls), note=note, velocity=velocity,
                          levels=list(levels), peak=max(map(abs, samples)),
                          rms_floor=math.isqrt(sum(s*s for s in samples)//BLOCK),
                          pcm_sha256=hashlib.sha256(raw).hexdigest()))
    return bytes(pcm), trace


def main():
    lib = C.CDLL(str(Path(sys.argv[1]).resolve(strict=True)))
    for fn in (lib.live_reset, lib.live_panic):
        fn.argtypes, fn.restype = [], None
    lib.live_block.argtypes = [C.c_uint]*7 + [C.POINTER(C.c_int16), C.POINTER(C.c_uint32)]
    lib.live_block.restype = None
    out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
    results = {arm: render(lib, arm) for arm in ARMS}
    for arm, (pcm, trace) in results.items():
        assert (pcm, trace) == render(lib, arm), arm + ' repeat'
        assert len(pcm) == (len(SLOTS)*SPAN + TAIL)*BLOCK*2
        assert sum(t['event'] == 1 for t in trace) == 16
        assert sum(t['event'] == 2 for t in trace) == 12
        assert max(t['peak'] for t in trace) < 24000
        assert all(0 <= v <= 131070 for t in trace for v in t['levels'])
        for k in range(len(SLOTS)):
            row = k*SPAN + 29
            assert trace[row-1]['peak'] > 0 and trace[row]['action'] == 'panic'
            assert not trace[row]['peak'] and not any(trace[row]['levels'])
        assert not any(pcm[-TAIL*BLOCK*2:]) and all(not any(t['levels']) for t in trace[-TAIL:])
    fixed, macros, full = (results[arm][1] for arm in ARMS)
    witness = []
    for k, slot in enumerate(SLOTS):
        start = k*SPAN
        assert fixed[start] == macros[start] == full[start], 'matched first strike'
        a, b, c = (t[start+1] for t in (fixed, macros, full))
        assert all(t['event'] == 0 and t['held'] for t in (a,b,c))
        assert a['pcm_sha256'] != b['pcm_sha256'], 'macro response'
        assert (b['pcm_sha256'] == c['pcm_sha256']) == (slot[0] == BASE[0]), 'material isolation'
        assert b['controls'][1:] == c['controls'][1:]
        witness.append(dict(material=slot[0], macro_changed=True,
                            material_changed=b['pcm_sha256'] != c['pcm_sha256']))
    receipt = dict(schema='xenoresonator-local-material-replay/1', device_telemetry=False,
                   rate=RATE, block_frames=BLOCK, frames=len(results['fixed'][0])//2,
                   slots=[dict(schema='xenoresonator.material/1', **dict(zip('pedc', s))) for s in SLOTS],
                   witness=witness, results={})
    for arm, (pcm, trace) in results.items():
        with wave.open(str(out/(arm+'.wav')), 'wb') as wav:
            wav.setparams((1, 2, RATE, 0, 'NONE', 'not compressed'))
            wav.writeframes(pcm)
        receipt['results'][arm] = dict(pcm_sha256=hashlib.sha256(pcm).hexdigest(),
                                       peak=max(t['peak'] for t in trace), trace=trace)
    (out/'receipt.json').write_bytes((json.dumps(receipt, sort_keys=True, separators=(',', ':'))+'\n').encode())
    print('PASS', len(SLOTS), 'matched held recalls; 3 arms; exact repeat and panic tail')
    for arm, data in receipt['results'].items():
        print(arm, data['peak'], data['pcm_sha256'])


if __name__ == '__main__':
    main()
