"""Chronomorph consumer of the existing matched rate lifecycle qualification."""
import json
import sys
from pathlib import Path

from rate_ecophon import report, runtime_variant
from rate_lifecycle import require
from rate_probe import prepare


def app_variant(source):
    # Chronomorph publishes PLAY in bit 24, not Grimoire's gate/panic bits.
    old = 'uint32_t active=(cmd&(1u<<17))==0 && (cmd&(1u<<16));'
    result = prepare(source, 'hold')
    require(result.count(old) == 1, 'unexpected timing wrapper')
    return result.replace(old, 'uint32_t active=(cmd&(1u<<24))!=0;')


def make_variant(app, header, mode):
    return app_variant(app), runtime_variant(header, mode, 'Chronomorph')


def self_test(app, header):
    hold, h = make_variant(app, header, 'hold')
    linear, l = make_variant(app, header, 'linear')
    require(hold == linear and h == header, 'hold variant changed source')
    require(hold.count('uint32_t active=(cmd&(1u<<24))!=0;') == 1,
            'Chronomorph transport bit not witnessed')
    require('VwRateLinear rate;' in l and l.count('vw_linear_clear(') == 2
            and l.count('vw_linear_step(') == 1, 'linear seam mismatch')
    for bad_app, bad_header in ((app + app, header),
                                (app, header.replace('vw_rate_step(', 'missing(')),
                                (app, header + '\n/* vw_rate_clear( */')):
        try:
            make_variant(bad_app, bad_header, 'linear')
        except ValueError:
            pass
        else:
            raise ValueError('accepted corrupted adapter seam')
    print('Chronomorph rate generator PASS (3 negative cases; source only)')


if __name__ == '__main__':
    if len(sys.argv) == 4 and sys.argv[1] == '--test':
        self_test(Path(sys.argv[2]).read_text(), Path(sys.argv[3]).read_text())
    elif len(sys.argv) == 6 and sys.argv[1] == 'prepare':
        source, header, out, mode = sys.argv[2:]
        app, runtime = make_variant(Path(source).read_text(), Path(header).read_text(), mode)
        out = Path(out)
        out.mkdir(parents=True, exist_ok=False)
        (out / 'dinghy.c').write_text(app)
        (out / 'chrono_runtime.h').write_text(runtime)
    elif len(sys.argv) == 2:
        print(json.dumps(report(Path(sys.argv[1]), 'Chronomorph'), indent=2))
    else:
        raise SystemExit('rate_chronomorph.py --test app runtime | prepare app runtime output hold|linear | evidence-directory')
