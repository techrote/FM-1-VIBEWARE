"""Independent Ecophon environment-memory PCM and state verification."""
import hashlib
import json
from pathlib import Path
import struct
import sys
import wave

ARMS = ('smooth', 'step', 'steady', 'takeover')
ORIGINS = ((180, 200, 40), (100, 20, 150), (230, 90, 85))
A, B, MANUAL = (0, 0, 255), (255, 220, 0), (150, 240, 70)
BLOCK, COUNT = 2400, 190


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def controls_at(origin, arm, n):
    def lerp(start, end, t):
        return tuple((a*(40-t)+b*t)//40 for a,b in zip(start,end))
    captured = origin if arm == 'steady' else A if arm == 'step' else lerp(origin,A,20)
    if n < 1 or arm == 'steady':
        return origin
    if arm == 'takeover' and n >= 71:
        return MANUAL
    start, end, elapsed = ((origin,A,n) if n <= 50 else
                           (A,B,n-50) if n <= 100 else (B,captured,n-100))
    return end if arm == 'step' else lerp(start,end,min(elapsed,40))


def verify(root):
    root = Path(root)
    receipt = root/'environment-memory-replay.json'
    doc = json.loads(receipt.read_bytes())
    require([doc[k] for k in ('schema','state_source','wire_protocol','seed','sample_rate',
                             'frames_per_snapshot','prelude_blocks','score_blocks','mute_blocks')]
            == ['ecophon-environment-memory-v1','local native core, not device telemetry',None,
                42,24000,BLOCK,30,150,10], 'metadata')
    require(set(doc['regimes']) == {'0','1','2'}, 'regime inventory')
    require({p.name for p in root.glob('*.wav')} == {f'{i}-{a}.wav' for i in range(3) for a in ARMS}, 'WAV inventory')
    populations = {}
    for i, origin in enumerate(ORIGINS):
        group = doc['regimes'][str(i)]
        require(set(group) == set(ARMS), 'arm inventory')
        pcm, traces = {}, {}
        for arm in ARMS:
            path = root/f'{i}-{arm}.wav'
            item = group[arm]
            require(sha(path.read_bytes()) == item['wav_sha256'], 'WAV digest')
            with wave.open(str(path),'rb') as w:
                require((w.getnchannels(),w.getsampwidth(),w.getframerate(),w.getnframes(),w.getcomptype())
                        == (1,2,24000,BLOCK*COUNT,'NONE'), 'WAV format')
                raw = w.readframes(BLOCK*COUNT)
            require(len(raw)==2*BLOCK*COUNT and any(raw[:180*BLOCK*2]) and not any(raw[180*BLOCK*2:]), 'audio/tail')
            pcm[arm] = raw
            rows = traces[arm] = item['rows']
            require(len(rows)==COUNT, 'trace length')
            for j,row in enumerate(rows):
                n = j-29
                expected = controls_at(origin,arm,n)
                captured = controls_at(origin,arm,20) if n>=21 else A
                event = {1:'recall-A',21:'capture-A',51:'recall-B',101:'recall-A',151:'panic'}.get(n)
                if arm=='takeover' and n==71:
                    event='manual'
                require(row['controls']==[*expected,0] and row['slots']=={'A':list(captured),'B':list(B)}
                        and row['event']==event and row['muted']==(n>150), 'control schedule')
                block=raw[j*BLOCK*2:(j+1)*BLOCK*2]
                require(row['frame_end']==(j+1)*BLOCK and row['pcm_sha256']==sha(block)
                        and max(abs(v[0]) for v in struct.iter_unpack('<h',block))<=24000, 'PCM alignment')
                c, agents, resources = row['counters'],row['agents'],row['resources']
                require(len(c)==6 and c[0]==(j+1)*10 and all(type(v) is int and v>=0 for v in c), 'counters')
                if j:
                    require(all(a>=b for a,b in zip(c,rows[j-1]['counters'])), 'counter regression')
                require(len(resources)==4 and all(0<=v<=4096 for v in resources), 'resource bounds')
                require(len(agents)==8 and all(a in (0,1) and 0<=p<4 and s in (0,1) and 0<=t<16 and 0<=e<=4096
                                               and (a or not e) for a,p,s,t,e in agents), 'agent bounds')
                require(sum(a[0] for a in agents)==5+c[1]-c[2], 'population accounting')
        require(len(set(pcm.values()))==4, 'aliased arms')
        for arm in ARMS:
            cut = 100 if arm=='takeover' else 30
            require(pcm[arm][:cut*BLOCK*2]==pcm['smooth'][:cut*BLOCK*2]
                    and traces[arm][:cut]==traces['smooth'][:cut], 'matched prefix')
        populations[str(i)] = {a:sum(v[0] for v in traces[a][179]['agents']) for a in ARMS}
    return {'snapshots':3*4*COUNT,'receipt_sha256':sha(receipt.read_bytes()),'populations':populations}


if __name__=='__main__':
    original = Path(sys.argv[1])
    result = verify(original)
    if len(sys.argv)==3:
        fresh=Path(sys.argv[2])
        require(result==verify(fresh),'fresh receipt differs')
        for p in [*original.glob('*.wav'),original/'environment-memory-replay.json']:
            require(p.read_bytes()==(fresh/p.name).read_bytes(),f'fresh bytes differ: {p.name}')
    print(json.dumps(result,sort_keys=True))
