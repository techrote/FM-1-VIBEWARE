"""Ecophon environment-memory performance, local native state only.

Compare smooth recall with abrupt recall, steady controls and manual takeover.
The score captures A/B before playback; overwrites A during its first recall;
then recalls the overwritten A after B. No habitat reset between cues.
"""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import struct
import wave

RATE, FRAMES, SEED = 24000, 2400, 42
PRELUDE, LENGTH, TAIL = 30, 150, 10
ORIGINS = ((180, 200, 40), (100, 20, 150), (230, 90, 85))
A, B = (0, 0, 255), (255, 220, 0)
MANUAL = (150, 240, 70)
ARMS = ('smooth', 'step', 'steady', 'takeover')


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def ramp(origin, target, n):
    return tuple((x*(40-n)+y*n)//40 for x, y in zip(origin, target))


def render(lib, preset, arm):
    lib.ecof_reset(SEED, preset)
    controls = ORIGINS[preset]
    slots = {'A': A, 'B': B}
    active = None
    samples, snap = (C.c_int16*FRAMES)(), (C.c_uint32*56)()
    pcm, rows = bytearray(), []
    for block in range(1, PRELUDE+LENGTH+TAIL+1):
        n = block-PRELUDE
        event = None
        if n in (1, 51, 101):
            slot = 'B' if n == 51 else 'A'
            event = 'recall-'+slot
            if arm in ('smooth', 'step') or (arm == 'takeover' and n < 71):
                active = (controls, slots[slot], n)
        if n == 21:
            # Capture current requested controls, not an ecological snapshot.
            slots['A'] = controls
            event = 'capture-A'
        if n == 71 and arm == 'takeover':
            event = 'manual'
            active, controls = None, MANUAL
        if active is not None:
            origin, target, start = active
            progress = n-start+1
            controls = target if arm == 'step' else ramp(origin, target, progress)
            if progress == 40 or arm == 'step':
                active = None
        muted = n > LENGTH
        if n == LENGTH+1:
            event = 'panic'
            lib.ecof_panic()
        require(lib.ecof_step(*controls, 0, samples, snap)==56, 'native step')
        s = list(snap)
        require(s[0]==block*10 and s[6:12]==[preset,0,int(muted),*controls], 'clock/control echo')
        agents = [s[i:i+5] for i in range(16,56,5)]
        require(sum(a[0] for a in agents)==5+s[1]-s[2], 'population accounting')
        require(all(0<=v<=4096 for v in s[12:16]), 'resources')
        require(all(a in (0,1) and 0<=p<4 and sp in (0,1) and 0<=t<16 and 0<=e<=4096 and (a or not e)
                    for a,p,sp,t,e in agents), 'agents')
        require(max(map(abs,samples))<=24000 and (not muted or not any(samples)), 'audio bounds/mute')
        raw = struct.pack('<2400h', *samples)
        pcm.extend(raw)
        rows.append(dict(frame_end=block*FRAMES, event=event, controls=[*controls,0],
                         slots={k:list(v) for k,v in slots.items()}, counters=s[:6], resources=s[12:16],
                         agents=agents, muted=muted, pcm_sha256=hashlib.sha256(raw).hexdigest()))
    return bytes(pcm), rows


def run(library, output):
    lib = C.CDLL(str(Path(library).resolve()))
    lib.ecof_reset.argtypes, lib.ecof_reset.restype = [C.c_uint32,C.c_uint], None
    lib.ecof_panic.argtypes, lib.ecof_panic.restype = [], None
    lib.ecof_step.argtypes = [C.c_uint]*4+[C.POINTER(C.c_int16),C.POINTER(C.c_uint32)]
    lib.ecof_step.restype = C.c_int
    output.mkdir(parents=True, exist_ok=True)
    receipt = dict(schema='ecophon-environment-memory-v1', state_source='local native core, not device telemetry',
                   wire_protocol=None, seed=SEED, sample_rate=RATE, frames_per_snapshot=FRAMES,
                   prelude_blocks=PRELUDE, score_blocks=LENGTH, mute_blocks=TAIL,
                   control_fields=['fertility','sharing','pressure','frozen'],
                   counter_fields=['ticks','births','deaths','gifts','moves','consumed'],
                   agent_fields=['alive','patch','species','trait','energy'], regimes={})
    for preset, origin in enumerate(ORIGINS):
        results = {arm:render(lib,preset,arm) for arm in ARMS}
        smooth = results['smooth']
        def row(n):
            return smooth[1][PRELUDE+n-1]
        captured = ramp(origin,A,20)
        require(row(21)['slots']['A']==list(captured), 'capture timing')
        require(row(40)['controls']==[*A,0], 'active recall mutated by capture')
        require(row(90)['controls']==[*B,0], 'B endpoint')
        require(row(140)['controls']==[*captured,0], 'overwritten A endpoint')
        for arm, result in results.items():
            require(render(lib,preset,arm)==result, 'repeat drift')
            require(result[0][:PRELUDE*FRAMES*2]==smooth[0][:PRELUDE*FRAMES*2] and
                    result[1][:PRELUDE]==smooth[1][:PRELUDE], 'matched prelude')
        cut = PRELUDE+70
        takeover = results['takeover']
        require(takeover[0][:cut*FRAMES*2]==smooth[0][:cut*FRAMES*2] and
                takeover[1][:cut]==smooth[1][:cut], 'takeover prefix')
        require(all(r['controls']==[*MANUAL,0] for r in takeover[1][PRELUDE+70:]), 'manual retention')
        require(len({r[0] for r in results.values()})==len(ARMS), 'PCM arms aliased')
        receipt['regimes'][str(preset)] = {}
        for arm, (pcm, rows) in results.items():
            path = output / f'{preset}-{arm}.wav'
            with wave.open(str(path),'wb') as w:
                w.setparams((1,2,RATE,0,'NONE','not compressed'))
                w.writeframes(pcm)
            receipt['regimes'][str(preset)][arm] = dict(wav_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), rows=rows)
        print('preset',preset,'final populations',*[sum(a[0] for a in results[k][1][PRELUDE+LENGTH-1]['agents']) for k in ARMS])
    payload = (json.dumps(receipt,sort_keys=True,separators=(',',':'))+'\n').encode()
    (output/'environment-memory-replay.json').write_bytes(payload)
    print('PASS twelve native renders, repeats, detached recall, matched prefixes and panic; replay SHA256',hashlib.sha256(payload).hexdigest())


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('library')
    p.add_argument('output',type=Path)
    a = p.parse_args()
    run(a.library,a.output)
