"""Native replay of the live Habitat Arc and explicit manual takeover.

Offline local-core fixture, not device telemetry or a wire protocol.
"""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import struct
import wave

FRAMES, RATE, SEED = 2400, 24000, 42
PRELUDE, SCORE, TAIL = 30, 240, 10
TAKEOVER = 100  # completed score blocks before manual control
ORIGINS = ((180, 200, 40), (100, 20, 150), (230, 90, 85))
BASE, DROUGHT, RECOVERY = (180, 200, 40), (0, 0, 255), (255, 220, 0)
MANUAL = (150, 240, 70)
ARMS = ('arc', 'steady', 'takeover')


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def ramp(a, b, n):
    return tuple((x*(40-n)+y*n)//40 for x, y in zip(a, b))


def schedule(origin, block, arm):
    if arm not in ARMS or not 1 <= block <= SCORE:
        raise ValueError('invalid score position')
    if arm == 'steady':
        return origin
    if arm == 'takeover' and block > TAKEOVER:
        return MANUAL
    if block <= 40:
        return ramp(origin, BASE, block)
    if block <= 80:
        return ramp(BASE, DROUGHT, block-40)
    if block <= 120:
        return DROUGHT
    if block <= 160:
        return ramp(DROUGHT, RECOVERY, block-120)
    return RECOVERY


def render(lib, preset, arm):
    origin = ORIGINS[preset]
    lib.ecof_reset(SEED, preset)
    samples, snap = (C.c_int16*FRAMES)(), (C.c_uint32*56)()
    pcm, rows = bytearray(), []
    for block in range(1, PRELUDE+SCORE+TAIL+1):
        muted = block > PRELUDE+SCORE
        score_block = block-PRELUDE
        if muted:
            if block == PRELUDE+SCORE+1:
                lib.ecof_panic()
            v = schedule(origin, SCORE, arm)
        else:
            v = origin if score_block <= 0 else schedule(origin, score_block, arm)
        require(lib.ecof_step(*v, 0, samples, snap)==56, 'native step rejected')
        s = list(snap)
        require(s[0]==block*10 and s[6:12]==[preset, 0, int(muted), *v], 'native echo or clock')
        agents = [s[i:i+5] for i in range(16, 56, 5)]
        require(all(0<=r<=4096 for r in s[12:16]), 'resource bounds')
        require(all(a in (0,1) and 0<=p<4 and sp in (0,1) and 0<=t<16 and 0<=e<=4096 and (a or not e)
                    for a,p,sp,t,e in agents), 'agent bounds')
        require(sum(a[0] for a in agents)==5+s[1]-s[2], 'population accounting')
        require(max(map(abs,samples))<=24000, 'headroom')
        require(not muted or not any(samples), 'panic tail')
        raw = struct.pack('<2400h', *samples)
        pcm.extend(raw)
        rows.append(dict(frame_end=block*FRAMES, controls=[*v,0], counters=s[:6], resources=s[12:16],
                         agents=agents, muted=muted, pcm_sha256=hashlib.sha256(raw).hexdigest()))
    return bytes(pcm), rows


def run(library, output):
    lib = C.CDLL(str(Path(library).resolve()))
    lib.ecof_reset.argtypes, lib.ecof_reset.restype = [C.c_uint32,C.c_uint], None
    lib.ecof_panic.argtypes, lib.ecof_panic.restype = [], None
    lib.ecof_step.argtypes = [C.c_uint]*4+[C.POINTER(C.c_int16),C.POINTER(C.c_uint32)]
    lib.ecof_step.restype = C.c_int
    output.mkdir(parents=True, exist_ok=True)
    receipt = dict(schema='ecophon-live-arc-replay-v1', state_source='local native core, not device telemetry',
                   wire_protocol=None, seed=SEED, sample_rate=RATE, frames_per_snapshot=FRAMES,
                   prelude_blocks=PRELUDE, score_blocks=SCORE, mute_blocks=TAIL, takeover_after=TAKEOVER,
                   control_fields=['fertility','sharing','pressure','frozen'],
                   counter_fields=['ticks','births','deaths','gifts','moves','consumed'],
                   agent_fields=['alive','patch','species','trait','energy'], regimes={})
    for preset, origin in enumerate(ORIGINS):
        results = {arm: render(lib,preset,arm) for arm in ARMS}
        arc, steady, takeover = (results[a] for a in ARMS)
        for arm, result in results.items():
            require(render(lib,preset,arm)==result, 'repeat drift')
            require(result[0][:PRELUDE*FRAMES*2]==arc[0][:PRELUDE*FRAMES*2] and
                    result[1][:PRELUDE]==arc[1][:PRELUDE], 'prelude mismatch')
        cut = PRELUDE+TAKEOVER
        require(takeover[0][:cut*FRAMES*2]==arc[0][:cut*FRAMES*2] and takeover[1][:cut]==arc[1][:cut], 'takeover prefix mismatch')
        require(all(r['controls']==[*MANUAL,0] for r in takeover[1][cut:]), 'manual control not retained')
        require(len({result[0] for result in results.values()})==3, 'PCM arms aliased')
        receipt['regimes'][str(preset)] = {}
        for arm, (pcm, rows) in results.items():
            path = output / f'{preset}-{arm}.wav'
            with wave.open(str(path),'wb') as w:
                w.setparams((1,2,RATE,0,'NONE','not compressed'))
                w.writeframes(pcm)
            receipt['regimes'][str(preset)][arm] = dict(wav_sha256=hashlib.sha256(path.read_bytes()).hexdigest(), rows=rows)
        print('preset',preset,'population at score end',*[sum(a[0] for a in results[k][1][PRELUDE+SCORE-1]['agents']) for k in ARMS])
    payload = (json.dumps(receipt,sort_keys=True,separators=(',',':'))+'\n').encode()
    (output/'live-arc-replay.json').write_bytes(payload)
    print('PASS nine distinct regime/arm renders, exact repeat, matched prefixes, manual takeover and silent panic; replay SHA256',hashlib.sha256(payload).hexdigest())


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('library')
    p.add_argument('output',type=Path)
    a = p.parse_args()
    run(a.library,a.output)
