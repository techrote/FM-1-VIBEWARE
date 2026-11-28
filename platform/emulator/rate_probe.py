"""Generate instrumented hold/linear variants and check emulator evidence."""
import hashlib
import json
import re
import sys
import wave
from pathlib import Path

SIGNATURE = 'static void app_audio(int32_t *out,uint32_t n) {'
WRAPPER = '''
/* Emulator-only timing witness: same instrumentation for both variants. */
static volatile uint32_t vw_probe_metrics[5];
static void app_audio(int32_t *out,uint32_t n) {
    uint32_t active=(cmd&(1u<<17))==0 && (cmd&(1u<<16));
    uint32_t started=fm1_ticks();
    vw_probe_audio(out,n);
    uint32_t ticks=fm1_ticks()-started;
    vw_probe_metrics[0]++;
    if(ticks>vw_probe_metrics[1]) vw_probe_metrics[1]=ticks;
    if(active) {
        vw_probe_metrics[2]++;
        if(ticks>vw_probe_metrics[3]) vw_probe_metrics[3]=ticks;
    }
    if(n!=256u) vw_probe_metrics[4]++;
}
'''


def prepare(source, mode):
    if mode not in ('hold', 'linear') or source.count(SIGNATURE) != 1:
        raise ValueError('unexpected mode or adapter signature')
    source = source.replace(SIGNATURE, SIGNATURE.replace('app_audio', 'vw_probe_audio'))
    if mode == 'linear':
        for old, new in (('#include "rate.h"', '#include "rate_linear.h"'),
                         ('VwRate rate;', 'VwRateLinear rate;'),
                         ('vw_rate_clear(', 'vw_linear_clear('),
                         ('vw_rate_step(', 'vw_linear_step(')):
            if old not in source:
                raise ValueError('missing rate seam: '+old)
            source = source.replace(old, new)
    return source + '\n' + WRAPPER


def decode(log, addr):
    marker = f'dump {addr:#010x} (5 words):'
    if log.count(marker) != 1:
        raise ValueError('missing/ambiguous metric dump')
    row = log.split(marker, 1)[1].splitlines()[1].strip()
    match = re.fullmatch(r'(0x[0-9a-fA-F]{8}): ((?:[0-9a-fA-F]{8} ){4}[0-9a-fA-F]{8})', row)
    if not match or int(match[1], 16) != addr:
        raise ValueError('invalid metric row')
    blocks, peak, active, active_peak, wrong_size = (int(x,16) for x in match[2].split())
    if not (blocks > 100 and 100 < active <= blocks and 0 < active_peak <= peak and
            peak * 44100 < 256 * 24000000 and wrong_size == 0):
        raise ValueError('modeled callback timing or block witness failed')
    return dict(blocks=blocks, peak_ticks=peak, active_blocks=active,
                active_peak_ticks=active_peak, model_timer_hz=24000000,
                block_frames=256, wrong_size_blocks=wrong_size)


def check_wav(path):
    with wave.open(str(path), 'rb') as w:
        if (w.getnchannels(), w.getsampwidth(), w.getframerate()) != (2,2,44100) or w.getnframes()<176400:
            raise ValueError('unexpected PCM format or duration')
        pcm=w.readframes(w.getnframes())
    if not any(pcm[:-88200]) or any(pcm[-88200:]):
        raise ValueError('silent performance or nonzero HOME tail')
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compare(directory):
    result={}
    for mode in ('hold','linear'):
        cases={}
        addr=int((directory/f'{mode}-address.txt').read_text(),16)
        for case in ('n3','n3-repeat','n9'):
            stem=f'{mode}-{case}'
            cases[case]=dict(sha256=check_wav(directory/f'{stem}.wav'),
                             **decode((directory/f'{stem}.log').read_text(),addr))
        if cases['n3']['sha256']!=cases['n3-repeat']['sha256'] or cases['n3']['sha256']==cases['n9']['sha256']:
            raise ValueError('repeat or pitch contrast failed: '+mode)
        result[mode]=cases
    if result['hold']['n3']['sha256']==result['linear']['n3']['sha256']:
        raise ValueError('linear variant produced no PCM change')
    return dict(status='PASS', scope='instrumented virtual target; not physical or adopted', variants=result)


def self_test():
    fixture='#include "rate.h"\nVwRate rate;\n'+SIGNATURE+'\nvw_rate_clear(&rate);vw_rate_step(&rate,0,0);\n}'
    assert 'vw_probe_audio' in prepare(fixture,'hold') and 'vw_linear_step' not in prepare(fixture,'hold')
    linear=prepare(fixture,'linear')
    assert 'VwRateLinear rate;' in linear and 'vw_linear_step' in linear and 'vw_rate_step' not in linear
    log='dump 0x00123400 (5 words):\n  0x00123400: 00000100 00003000 000000c8 00002000 00000000\n'
    assert decode(log,0x123400)['active_blocks']==200
    for invalid in (log.replace('00003000','00030000'),log.replace('000000c8','00000000'),log.replace('00000000','00000001'),log+log,log.replace('0x00123400','0x00123404')):
        try: decode(invalid,0x123400)
        except ValueError: pass
        else: raise AssertionError('accepted malformed dump')
    for invalid in ('',fixture+fixture):
        try: prepare(invalid,'hold')
        except ValueError: pass
        else: raise AssertionError('accepted missing/duplicate signature')
    print('rate probe generator and metric decoder: PASS (including 7 negative cases)')


if __name__=='__main__':
    if sys.argv[1:]==['--test']:
        self_test()
    elif len(sys.argv)==5 and sys.argv[1]=='prepare':
        Path(sys.argv[4]).write_text(prepare(Path(sys.argv[2]).read_text(),sys.argv[3]))
    elif len(sys.argv)==3 and sys.argv[1]=='compare':
        print(json.dumps(compare(Path(sys.argv[2])),indent=2))
    else:
        raise SystemExit('rate_probe.py --test | prepare source hold|linear destination | compare directory')
