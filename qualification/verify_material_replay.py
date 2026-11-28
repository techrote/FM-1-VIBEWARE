"""Independent held-recall PCM, event and state receipt verification."""
import hashlib
import json
import math
from pathlib import Path
import struct
import sys
import wave

ARMS = ('fixed', 'macros-only', 'full-recall')
BASE = [2, 105, 0, 100]
SLOTS = [[0, 55, 0, 78], [1, 72, 0, 35], [2, 118, 28, 12], [3, 110, 0, 92]]
NOTES = [[48, 55, 60, 43], [51, 58, 63, 46], [43, 50, 55, 36], [48, 51, 55, 48]]


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def verify(root):
    doc = json.loads((root/'receipt.json').read_bytes())
    assert doc['schema'] == 'xenoresonator-local-material-replay/1' and doc['device_telemetry'] is False
    assert [doc[k] for k in ('rate','block_frames','frames')] == [24000,1200,168000]
    assert doc['slots'] == [dict(schema='xenoresonator.material/1', **dict(zip('pedc', s))) for s in SLOTS]
    assert set(doc['results']) == set(ARMS)
    raw, traces = {}, {}
    for arm in ARMS:
        with wave.open(str(root/(arm+'.wav')), 'rb') as w:
            assert (w.getnchannels(),w.getsampwidth(),w.getframerate(),w.getnframes(),w.getcomptype()) == (1,2,24000,168000,'NONE')
            raw[arm] = pcm = w.readframes(168000)
        d = doc['results'][arm]
        assert len(pcm)==336000 and sha(pcm)==d['pcm_sha256']
        traces[arm] = rows = d['trace']
        assert len(rows)==140
        held, note, velocity, controls = False, 48, 110, BASE[:]
        peaks=[]
        for i,r in enumerate(rows):
            phrase, offset = divmod(i,30)
            action, event = 'none',0
            if phrase<4:
                if offset in (0,10,20,28):
                    j=(0,10,20,28).index(offset)
                    note,velocity=NOTES[phrase][j],(110,92,118,127)[j]
                    action,event,held,controls='strike',1,True,BASE[:]
                elif offset in (1,11,21):
                    action='recall'
                    if arm!='fixed': controls=[SLOTS[phrase][0] if arm=='full-recall' else BASE[0],*SLOTS[phrase][1:]]
                elif offset in (3,13,23):
                    action='manual-xy'
                    if arm!='fixed': controls=[controls[0],80,48,controls[3]]
                elif offset in (6,16,26): action,event,held='release',2,False
                elif offset==29: action,held='panic',False
            block=pcm[i*2400:(i+1)*2400]
            samples=struct.unpack('<1200h',block)
            peak=max(map(abs,samples)); peaks.append(peak)
            assert [r[k] for k in ('block','action','event','held','note','velocity','controls')]==[i,action,event,held,note,velocity,controls]
            assert r['pcm_sha256']==sha(block) and r['peak']==peak<24000
            assert r['rms_floor']==math.isqrt(sum(s*s for s in samples)//1200)
            assert len(r['levels'])==6 and all(type(v) is int and 0<=v<=131070 for v in r['levels'])
            if action=='panic' or i>=120:
                assert peak==0 and not any(r['levels'])
                if action=='panic': assert peaks[-2]>0
        assert max(peaks)==d['peak'] and max(peaks)>0
    witnesses=[]
    for k,slot in enumerate(SLOTS):
        i=k*30
        a,b,c=(traces[arm] for arm in ARMS)
        assert a[i]==b[i]==c[i]
        assert a[i+1]['pcm_sha256']!=b[i+1]['pcm_sha256']
        changed=b[i+1]['pcm_sha256']!=c[i+1]['pcm_sha256']
        assert changed==(slot[0]!=BASE[0])
        witnesses.append(dict(material=slot[0],macro_changed=True,material_changed=changed))
    assert witnesses==doc['witness']
    pairs={a+' vs '+b:sum(x!=y for x,y in zip(struct.iter_unpack('<h',raw[a]),struct.iter_unpack('<h',raw[b]))) for a,b in ((ARMS[0],ARMS[1]),(ARMS[1],ARMS[2]),(ARMS[0],ARMS[2]))}
    assert all(v>0 for v in pairs.values())
    return dict(snapshots=420,changed_samples=pairs,receipt_sha256=sha((root/'receipt.json').read_bytes()))


if __name__=='__main__':
    original=Path(sys.argv[1]); result=verify(original)
    if len(sys.argv)==3:
        fresh=Path(sys.argv[2]); assert result==verify(fresh)
        assert all((original/n).read_bytes()==(fresh/n).read_bytes() for n in [*(a+'.wav' for a in ARMS),'receipt.json'])
    print(json.dumps(result,sort_keys=True))
