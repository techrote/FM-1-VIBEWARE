"""Independent local A/B morph receipt and PCM validation; no device claims."""
import hashlib
import json
import math
from pathlib import Path
import struct
import sys
import wave

ARMS = ('fixed', 'macros-only', 'full-morph', 'endpoint-step')
PAIRS = (((0,76,0,84),(2,110,0,12)), ((2,105,0,100),(1,60,0,30)), ((1,72,0,35),(1,118,0,92)))


def verify(root):
    r = json.loads((root/'receipt.json').read_text())
    assert r['schema'] == 'xenoresonator-local-material-morph/1' and r['device_telemetry'] is False
    assert (r['rate'],r['block_frames'],r['frames'],r['page_mapping_rows']) == (24000,1200,168000,384)
    assert r['pairs'] == json.loads(json.dumps(PAIRS)) and set(r['results']) == set(ARMS)
    blocks, traces = {}, {}
    for arm in ARMS:
        data = r['results'][arm]
        with wave.open(str(root/(arm+'.wav')), 'rb') as w:
            assert (w.getnchannels(),w.getsampwidth(),w.getframerate(),w.getnframes(),w.getcomptype()) == (1,2,24000,168000,'NONE')
            pcm = w.readframes(168000)
        assert len(pcm)==336000 and hashlib.sha256(pcm).hexdigest()==data['pcm_sha256']
        rows = data['trace']; assert len(rows)==140
        blocks[arm] = [pcm[i:i+2400] for i in range(0,len(pcm),2400)]
        traces[arm] = rows
        held=False
        for i,(row,raw) in enumerate(zip(rows,blocks[arm])):
            k,j=divmod(i,40)
            s=struct.unpack('<1200h',raw)
            assert row['block']==i and row['pcm_sha256']==hashlib.sha256(raw).hexdigest()
            assert row['peak']==max(map(abs,s)) and row['rms_floor']==math.isqrt(sum(v*v for v in s)//1200)
            assert len(row['levels'])==6 and all(type(v) is int and 0<=v<=131070 for v in row['levels'])
            if k<3:
                a,b=PAIRS[k]
                pos=min(j*8,127) if j<18 else max(0,120-(j-18)*8)
                if j==17: pos=127
                # Directional interpolation computed as signed delta, not copied weighted sum.
                macros=[x+math.floor((y-x)*pos/127+0.5) for x,y in zip(a[1:],b[1:])]
                expected={'fixed':list(a),'macros-only':[a[0],*macros],'full-morph':[a[0] if pos<64 else b[0],*macros],'endpoint-step':list(a if pos<64 else b)}[arm]
                assert row['position']==pos and row['controls']==expected
                event=1 if j in (0,7,15,25,32,38) else 2 if j in (6,14,23,31,37) else 0
                action='strike' if event==1 else 'release' if event==2 else 'panic' if j==39 else 'morph'
                if event==1: held=True
                if event==2 or j==39: held=False
                assert row['event']==event and row['action']==action and row['held']==held
                if j==39: assert not any(raw) and not any(row['levels']) and any(blocks[arm][i-1])
            else:
                assert row['position'] is None and row['action']=='tail' and row['event']==0 and not row['held']
                assert not any(raw) and not any(row['levels'])
        assert 0<data['peak']==max(row['peak'] for row in rows)<24000
    for k,(a,b) in enumerate(PAIRS):
        i=k*40
        assert len({blocks[arm][i] for arm in ARMS})==1
        assert blocks['full-morph'][i:i+8]==blocks['macros-only'][i:i+8]
        for j in (8,26):
            assert all(traces[arm][i+j]['held'] and traces[arm][i+j]['event']==0 and any(blocks[arm][i+j]) for arm in ARMS[1:])
            assert blocks['full-morph'][i+j]!=blocks['endpoint-step'][i+j]
        assert (blocks['full-morph'][i+8]==blocks['macros-only'][i+8])==(a[0]==b[0])
        assert blocks['fixed'][i+7]!=blocks['macros-only'][i+7]
        if a[0]==b[0]: assert blocks['full-morph'][i:i+40]==blocks['macros-only'][i:i+40]
    return {'blocks':560,'pcm_frames':672000,'held_transition_pairs':6,'silent_blocks':92,'device_telemetry':False,'pcm_sha256':{arm:r['results'][arm]['pcm_sha256'] for arm in ARMS}}


if __name__=='__main__':
    print(json.dumps(verify(Path(sys.argv[1])),sort_keys=True))
