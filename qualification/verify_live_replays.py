"""Independent PCM/control checks for offline Ecophon and Grimoire replays."""
import hashlib
import io
import json
from pathlib import Path
import stat
import struct
import sys
import wave
import zipfile


def sha(b):
    return hashlib.sha256(b).hexdigest()


def verify(kind, files):
    eco = kind == 'ecophon'
    assert eco or kind == 'grimoire'
    names = ('0', '1', '2') if eco else ('amber', 'iron', 'abyss')
    arms = ('arc', 'steady', 'takeover') if eco else ('factory', 'authored', 'imported')
    receipt = 'live-arc-replay.json' if eco else 'sketch-replay.json'
    expected = {f'{n}-{a}.wav' for n in names for a in arms} | {receipt}
    assert set(files) == expected, 'unexpected or missing replay file'
    doc = json.loads(files[receipt])
    block, count, tail = (2400, 280, 10) if eco else (1200, 160, 10)
    assert doc['schema'] == ('ecophon-live-arc-replay-v1' if eco else 'grimoire.orbit-sketch.local-replay.v1')
    assert doc['state_source'] == ('local native core, not device telemetry' if eco else 'offline JS controller and native C core, not device telemetry')
    if eco:
        assert [doc[k] for k in ('seed','sample_rate','frames_per_snapshot','prelude_blocks','score_blocks','mute_blocks','takeover_after','wire_protocol')] == [42,24000,2400,30,240,10,100,None]
    else:
        assert doc['sample_rate_hz'] == 24000 and doc['block_frames'] == block
        sketch = doc['document']
        assert sketch['format'] == 'grimoire.orbit-sketch' and sketch['version'] == 1
        assert len(sketch['points']) == 8 and all(len(p)==2 and all(type(v) is int and 0<=v<=127 for v in p) for p in sketch['points'])
    data = doc['regimes' if eco else 'presets']
    assert set(data) == set(names)
    result = {}
    for n in names:
        group = data[n] if eco else data[n]['arms']
        assert set(group) == set(arms)
        pcm, rows = {}, {}
        for a in arms:
            wav = files[f'{n}-{a}.wav']
            with wave.open(io.BytesIO(wav),'rb') as w:
                assert (w.getnchannels(),w.getsampwidth(),w.getframerate(),w.getnframes(),w.getcomptype()) == (1,2,24000,block*count,'NONE')
                raw = w.readframes(block*count)
            assert len(raw) == block*count*2 and any(raw[:-tail*block*2]) and not any(raw[-tail*block*2:])
            pcm[a] = raw
            g = group[a]
            assert g['wav_sha256' if eco else 'pcm_sha256'] == sha(wav if eco else raw)
            rows[a] = rs = g['rows' if eco else 'snapshots']
            assert len(rs) == count
            for i,r in enumerate(rs):
                b = raw[i*block*2:(i+1)*block*2]
                peak = max(abs(v[0]) for v in struct.iter_unpack('<h',b))
                assert r['pcm_sha256'] == sha(b) and peak <= (24000 if eco else 28000)
                assert r['frame_end' if eco else 'end_sample'] == (i+1)*block
                if eco:
                    assert len(r['agents'])==8 and len(r['resources'])==4 and len(r['counters'])==6 and r['counters'][0]==(i+1)*10
                    assert all(0<=v<=4096 for v in r['resources'])
                    for alive,patch,species,trait,energy in r['agents']:
                        assert alive in (0,1) and 0<=patch<4 and species in (0,1) and 0<=trait<16 and 0<=energy<=4096 and (alive or not energy)
                    assert sum(x[0] for x in r['agents']) == 5+r['counters'][1]-r['counters'][2]
                    assert r['muted'] == (i>=count-tail) and len(r['controls'])==4 and all(0<=v<=255 for v in r['controls']) and r['controls'][3]==0
                    if a=='takeover' and i>=130: assert r['controls']==[150,240,70,0]
                else:
                    assert r['block']==i and r['peak']==peak and 0<=r['env']<=32767 and 0<=r['energy']<=28000
                    assert r['gate']==int(i<140 or 145<=i<150) and 0<=r['x']<=127 and 0<=r['y']<=127
                    assert len(r['phase_u16'])==3 and all(0<=v<=65535 for v in r['phase_u16'])
                    if 80<=i<90: assert [r['x'],r['y']]==[60,40]
                    if i>=150: assert r['env']==r['energy']==peak==0
        x,y,z = arms
        pre = 30 if eco else 40
        assert all(pcm[a][:pre*block*2]==pcm[x][:pre*block*2] and rows[a][:pre]==rows[x][:pre] for a in arms)
        if eco:
            assert pcm[z][:130*block*2]==pcm[x][:130*block*2] and rows[z][:130]==rows[x][:130]
            assert len(set(pcm.values()))==3
            result[n]=[sum(s[0] for s in rows[a][269]['agents']) for a in arms]
        else:
            assert pcm[y]==pcm[z] and rows[y]==rows[z]
            assert all((a['controller']['phase'],a['controller']['carry'])==(b['controller']['phase'],b['controller']['carry']) for a,b in zip(rows[x],rows[y]))
            changed=sum(a!=b for a,b in zip(struct.iter_unpack('<h',pcm[x]),struct.iter_unpack('<h',pcm[y])))
            assert changed>50*block and changed==data[n]['changed_samples']
            result[n]=changed
    return {'kind':kind,'replay_sha256':sha(files[receipt]),'snapshots':len(names)*len(arms)*count,'result':result}


def load(path, prefix=''):
    if path.is_dir():
        return {p.name:p.read_bytes() for p in path.iterdir() if p.is_file()}
    with zipfile.ZipFile(path) as z:
        members=[i for i in z.infolist() if i.filename.startswith(prefix)]
        assert len(members)==10 and sum(i.file_size for i in members)<20_000_000
        assert len({i.filename.casefold() for i in members})==len(members)
        assert all(not i.is_dir() and not stat.S_ISLNK(i.external_attr>>16) for i in members)
        return {i.filename[len(prefix):]:z.read(i) for i in members}


if __name__=='__main__':
    kind, original, *fresh = sys.argv[1:]
    a=load(Path(original), 'live-arc/' if kind=='ecophon' and fresh else '')
    result=verify(kind,a)
    if fresh:
        b=load(Path(fresh[0]))
        assert a==b, 'fresh exact-source replay differs'
        assert result==verify(kind,b)
    print(json.dumps(result,sort_keys=True))
