"""Native A/B performance score; local control intent, not device telemetry."""
import ctypes as C
import hashlib
import json
import math
from pathlib import Path
import struct
import subprocess
import sys
import wave

RATE, BLOCK, SPAN, TAIL = 24000, 1200, 40, 20
PAIRS = (((0, 76, 0, 84), (2, 110, 0, 12)),
         ((2, 105, 0, 100), (1, 60, 0, 30)),
         ((1, 72, 0, 35), (1, 118, 0, 92)))
POSITIONS = (0,8,16,24,32,40,48,56,64,72,80,88,96,104,112,120,127,127,
             120,112,104,96,88,80,72,64,56,48,40,32,24,16,8,0,0,0,0,0,0,0)
STRIKES = {0:48, 7:55, 15:60, 25:53, 32:43, 38:48}
RELEASES = (6,14,23,31,37)
ARMS = ('fixed', 'macros-only', 'full-morph', 'endpoint-step')


def morph(a, b, pos):
    return (a[0] if pos < 64 else b[0],
            *((x*(127-pos)+y*pos+63)//127 for x,y in zip(a[1:], b[1:])))


def check_page(lib):
    # Frozen predecessor page mapping: preserve the original comparison receipt.
    fn = "function applyMorph(position){\n  if(!userPatch||!morphB||!Number.isInteger(position)||position<0||position>127)return false;\n  const values={p:position<64?userPatch.p:morphB.p};\n  for(const k of ['e','d','c'])values[k]=Math.floor((userPatch[k]*(127-position)+morphB[k]*position+63)/127);\n  for(const k of userKeys)$(k).value=values[k];\n  $('morph').value=position;customPatch();dot();\n  $('morph-status').textContent='Morph requested '+position+'/127 — manual edits may supersede';\n  return true;\n}\n"
    script = '''const pairs=JSON.parse(process.argv[1]);
const userKeys=['p','e','d','c'], dom={};
const $=k=>dom[k]??=( {} );
let userPatch,morphB;function customPatch(){} function dot(){}
''' + fn + '''
let rows=[];for(const [a,b] of pairs){
userPatch=Object.fromEntries(userKeys.map((k,i)=>[k,a[i]]));
morphB=Object.fromEntries(userKeys.map((k,i)=>[k,b[i]]));
for(let p=0;p<128;p++){if(!applyMorph(p))throw Error('reject');rows.push(userKeys.map(k=>Number($(k).value)));}}
console.log(JSON.stringify(rows));'''
    actual = json.loads(subprocess.check_output(['node','-e',script,json.dumps(PAIRS)], text=True))
    assert actual == [list(morph(a,b,p)) for a,b in PAIRS for p in range(128)]
    # Also prove the current native memory mapping against all historical rows.
    lib.live_memory_store.argtypes = [C.c_uint]*5
    lib.live_memory_store.restype = C.c_int
    lib.live_memory_block.argtypes = [C.c_uint]*2+[C.POINTER(C.c_int16),C.POINTER(C.c_uint32)]
    lib.live_memory_block.restype = C.c_int
    lib.live_memory_read.argtypes = [C.c_uint,C.POINTER(C.c_uint32)]
    lib.live_memory_read.restype = C.c_int
    lib.live_reset.argtypes,lib.live_reset.restype = [],None
    lib.live_memory_clear.argtypes,lib.live_memory_clear.restype = [],None
    pcm,levels,patch = (C.c_int16*BLOCK)(),(C.c_uint32*6)(),(C.c_uint32*4)()
    rows=[]
    for a,b in PAIRS:
        lib.live_reset()
        assert lib.live_memory_store(0,*a) and lib.live_memory_store(1,*b)
        for pos in range(128):
            assert lib.live_memory_block(1,pos,pcm,levels) and lib.live_memory_read(2,patch)
            rows.append(list(patch))
    assert rows == actual
    lib.live_memory_clear()
    return len(actual)


def render(lib, arm):
    lib.live_reset()
    pcm, trace = bytearray(), []
    samples, levels = (C.c_int16 * BLOCK)(), (C.c_uint32 * 6)()
    held = False
    controls, note, velocity = PAIRS[0][0], 48, 110
    for i in range(len(PAIRS)*SPAN + TAIL):
        phrase, off = divmod(i, SPAN)
        event, action, pos = 0, 'tail', None
        if phrase < len(PAIRS):
            a,b = PAIRS[phrase]
            if off == 0:
                lib.live_reset()
            pos = POSITIONS[off]
            full = morph(a,b,pos)
            controls = {'fixed':a, 'macros-only':(a[0],*full[1:]),
                        'full-morph':full, 'endpoint-step':a if pos < 64 else b}[arm]
            action = 'morph'
            if off in STRIKES:
                note, velocity = STRIKES[off]+phrase, 110
                event, held, action = 1, True, 'strike'
            elif off in RELEASES:
                event, held, action = 2, False, 'release'
            elif off == SPAN-1:
                lib.live_panic()
                held, action = False, 'panic'
        lib.live_block(*controls, note, velocity, event, samples, levels)
        raw = struct.pack('<1200h', *samples)
        pcm.extend(raw)
        trace.append(dict(block=i, action=action, event=event, held=held,
                          position=pos, controls=list(controls), note=note, velocity=velocity,
                          levels=list(levels), peak=max(map(abs,samples)),
                          rms_floor=math.isqrt(sum(s*s for s in samples)//BLOCK),
                          pcm_sha256=hashlib.sha256(raw).hexdigest()))
    return bytes(pcm), trace


def main():
    lib = C.CDLL(str(Path(sys.argv[1]).resolve(strict=True)))
    page_rows = check_page(lib)
    for fn in (lib.live_reset,lib.live_panic):
        fn.argtypes,fn.restype = [],None
    lib.live_block.argtypes = [C.c_uint]*7+[C.POINTER(C.c_int16),C.POINTER(C.c_uint32)]
    lib.live_block.restype = None
    out = Path(sys.argv[2]); out.mkdir(parents=True,exist_ok=True)
    results = {arm:render(lib,arm) for arm in ARMS}
    for arm,(pcm,trace) in results.items():
        assert (pcm,trace) == render(lib,arm), arm+' repeat'
        assert len(pcm) == (len(PAIRS)*SPAN+TAIL)*BLOCK*2
        assert sum(t['event']==1 for t in trace)==len(PAIRS)*len(STRIKES)
        assert sum(t['event']==2 for t in trace)==len(PAIRS)*len(RELEASES)
        assert 0 < max(t['peak'] for t in trace) < 24000
        assert all(0<=v<=131070 for t in trace for v in t['levels'])
        for k in range(len(PAIRS)):
            row=k*SPAN+SPAN-1
            assert trace[row-1]['peak']>0 and trace[row]['action']=='panic'
            assert not trace[row]['peak'] and not any(trace[row]['levels'])
        assert not any(pcm[-TAIL*BLOCK*2:]) and all(not any(t['levels']) for t in trace[-TAIL:])
    fixed,macros,full,step=(results[arm][1] for arm in ARMS)
    witness=[]
    for k,(a,b) in enumerate(PAIRS):
        start=k*SPAN
        assert fixed[start]==macros[start]==full[start]==step[start], 'matched first strike'
        assert full[start:start+8]==macros[start:start+8], 'pre-midpoint identity'
        for off in (8,26):
            f,m,s=(t[start+off] for t in (full,macros,step))
            assert all(t['held'] and not t['event'] for t in (f,m,s))
            assert all(t["peak"]>0 for t in (f,m,s)), "nonvacuous held response"
            assert f['controls'][1:]==m['controls'][1:]
            assert f['pcm_sha256']!=s['pcm_sha256'], 'smooth versus step'
        f,m=(t[start+8] for t in (full,macros))
        assert (f['pcm_sha256']==m['pcm_sha256'])==(a[0]==b[0]), 'material isolation'
        assert fixed[start+7]['pcm_sha256']!=macros[start+7]['pcm_sha256'], 'macro response'
        if a[0]==b[0]:
            assert full[start:start+SPAN]==macros[start:start+SPAN], 'same-material control'
        witness.append(dict(pair=k, material_changed=a[0]!=b[0], midpoint_blocks=[start+8,start+26]))
    receipt=dict(schema='xenoresonator-local-material-morph/1',device_telemetry=False,
                 rate=RATE,block_frames=BLOCK,frames=len(results['fixed'][0])//2,
                 page_mapping_rows=page_rows,pairs=PAIRS,witness=witness,results={})
    for arm,(pcm,trace) in results.items():
        with wave.open(str(out/(arm+'.wav')),'wb') as wav:
            wav.setparams((1,2,RATE,0,'NONE','not compressed')); wav.writeframes(pcm)
        receipt['results'][arm]=dict(pcm_sha256=hashlib.sha256(pcm).hexdigest(),
                                    peak=max(t['peak'] for t in trace),trace=trace)
    (out/'receipt.json').write_bytes((json.dumps(receipt,sort_keys=True,separators=(',',':'))+'\n').encode())
    print('PASS',page_rows,'historical page/native memory mapping rows; four native arms; exact repeat and panic tail')
    for arm,data in receipt['results'].items():
        print(arm,data['peak'],data['pcm_sha256'])


if __name__=='__main__':
    main()
