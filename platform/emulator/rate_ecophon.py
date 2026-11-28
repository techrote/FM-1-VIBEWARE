"""Ecophon-specific second consumer for the isolated rate experiment."""
import json
import math
import sys
from pathlib import Path

from rate_probe import prepare
from rate_lifecycle import analyze, read_pcm, require
from rate_quality import digest, high_fraction, sizes


def runtime_variant(source, mode, instrument='Ecophon'):
    if mode not in ('hold', 'linear'):
        raise ValueError('unknown rate mode')
    if mode == 'hold':
        return source
    for old, new, count in (
        ('#include "rate.h"', '#include "rate_linear.h"', 1),
        ('VwRate rate;', 'VwRateLinear rate;', 1),
        ('vw_rate_clear(', 'vw_linear_clear(', 2),
        ('vw_rate_step(', 'vw_linear_step(', 1),
    ):
        require(source.count(old) == count, f'unexpected {instrument} rate seam: ' + old)
        source = source.replace(old, new)
    return source


def app_variant(source):
    # The generic wrapper's original Grimoire play/panic bits are NOT Ecophon's.
    old = 'uint32_t active=(cmd&(1u<<17))==0 && (cmd&(1u<<16));'
    result = prepare(source, 'hold')
    require(result.count(old) == 1, 'unexpected timing wrapper')
    return result.replace(old, 'uint32_t active=(cmd&(1u<<18))!=0;')


def report(root, instrument='Ecophon'):
    receipt = analyze(root)
    for case in ('lifecycle-control', 'lifecycle-switch'):
        require(digest(root / f'baseline-{case}.wav') ==
                receipt['modes']['hold']['sha256'][case],
                f'instrumentation changed uninstrumented {instrument} PCM: ' + case)
    for case in ('lifecycle-control', 'lifecycle-switch', 'lifecycle-repeat'):
        a, b = (receipt['modes'][m]['modeled_callbacks'][case] for m in ('hold', 'linear'))
        for key in ('blocks', 'active_blocks', 'block_frames', 'model_timer_hz', 'wrong_size_blocks'):
            require(a[key] == b[key], 'unmatched callback schedule: ' + case + '/' + key)
    arms = {}
    for mode in ('hold', 'linear'):
        samples = read_pcm(root / f'{mode}-lifecycle-control.wav')
        # Analyze only the unmodified, playing control before first HOME.
        band = high_fraction(samples[44100:88200])
        require(band > 0, 'zero high-band power')
        arms[mode] = dict(frames=len(samples), high_fraction=band,
                          sections=sizes(root / f'{mode}-size.txt'))
    a, b = arms['hold'], arms['linear']
    require(a['frames'] == b['frames'], 'unmatched PCM duration')
    require(receipt['modes']['hold']['sha256']['lifecycle-control'] !=
            receipt['modes']['linear']['sha256']['lifecycle-control'], 'rate change aliased')
    receipt.update(scope=f'{instrument} virtual lifecycle experiment only; no adoption or physical claim',
                   arms=arms, high_band_delta_db=10*math.log10(b['high_fraction']/a['high_fraction']),
                   analysis_frames=[44100,88200], cutoff_hz=12000,
                   section_delta={k:b['sections'][k]-v for k,v in a['sections'].items()})
    return receipt


if __name__ == '__main__':
    if len(sys.argv) == 6 and sys.argv[1] == 'prepare':
        source, header, out, mode = sys.argv[2:]
        out = Path(out)
        out.mkdir(parents=True, exist_ok=False)
        (out / 'dinghy.c').write_text(app_variant(Path(source).read_text()))
        (out / 'ecophon_runtime.h').write_text(runtime_variant(Path(header).read_text(), mode))
    elif len(sys.argv) == 2:
        print(json.dumps(report(Path(sys.argv[1])), indent=2))
    else:
        raise SystemExit('rate_ecophon.py prepare app runtime output hold|linear | evidence-directory')
