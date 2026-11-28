"""Matched local orbit direction replay through the actual native C session."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import wave

from replay import RATE, BLOCK, bind, require
from sketch_replay import render

# Same reference clock, block cadence and lifecycle as sketch_replay.
# No new device transport or target command.
JS = r'''
const R = require(process.argv[1]).Ribbon;
function arm(reverse) {
  const r = new R(), rows = [];
  r.setSpeed(2);
  for (let k=0;k<160;k++) {
    if (reverse && k===40) r.setDirection(-1);
    if (reverse && k===110) r.setDirection(1);
    if (k===80) r.take(60,40);
    if (k===90) r.resume();
    if (k===150) r.reset();
    const phase=r.phase,carry=r.carry;
    const xy=r.block();
    const ticks=r.speed?Math.floor((carry+5)/2):0;
    if (r.phase !== (phase+ticks*r.speed*r.direction+256)%256 ||
        r.carry !== (r.speed?(carry+5)%2:carry)) throw Error('signed clock');
    rows.push({xy:k===80?[60,40]:xy,phase:r.phase,carry:r.carry,
      manual:r.manual,blend:r.blend,shape:r.shape,speed:r.speed,direction:r.direction});
  }
  return rows;
}
console.log(JSON.stringify({forward:arm(false),reverse:arm(true)}));
'''


def schedule():
    path = Path(__file__).with_name('gesture.js').resolve()
    return json.loads(subprocess.check_output(['node', '-e', JS, str(path)], text=True))


def changed(a, b):
    return sum(x != y for (x,), (y,) in zip(struct.iter_unpack('<h', a),
                                           struct.iter_unpack('<h', b), strict=True))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('library')
    parser.add_argument('output', type=Path)
    parser.add_argument('--revision', required=True)
    args = parser.parse_args()
    require(len(args.revision) == 40 and all(c in '0123456789abcdef' for c in args.revision),
            'exact source revision required')
    args.output.mkdir(parents=True, exist_ok=True)
    data = schedule()
    require(data == schedule(), 'controller nondeterminism')
    forward, reverse = data['forward'], data['reverse']
    require(forward[:40] == reverse[:40], 'direction changed prelude')
    require(all(x['carry'] == y['carry'] for x, y in zip(forward, reverse)), 'fractional clock changed')
    require(all(row['direction'] == (-1 if 40 <= k < 110 else 1)
                for k, row in enumerate(reverse)), 'direction schedule')
    require(all(row['manual'] == (80 <= k < 90) for k, row in enumerate(reverse)), 'manual schedule')
    lib = bind(args.library)
    receipt = {'schema': 'grimoire.orbit-direction.local-replay.v1',
               'state_source': 'offline JS controller and actual native C core; not device telemetry',
               'source_revision': args.revision, 'sample_rate_hz': RATE,
               'block_frames': BLOCK, 'presets': {}}
    for preset, name in enumerate(('amber', 'iron', 'abyss')):
        arms = {arm: render(lib, preset, data[arm]) for arm in data}
        for arm, result in arms.items():
            require(result == render(lib, preset, data[arm]), 'native nondeterminism')
        a, b = arms['forward'][0], arms['reverse'][0]
        require(len(a) == len(b) == 160*BLOCK*2, 'PCM length')
        require(a[:40*BLOCK*2] == b[:40*BLOCK*2], 'pre-reversal PCM changed')
        n = changed(a[40*BLOCK*2:110*BLOCK*2], b[40*BLOCK*2:110*BLOCK*2])
        require(n > BLOCK, 'reverse interval did not materially change actual PCM')
        require(a[-10*BLOCK*2:] == b[-10*BLOCK*2:] == bytes(10*BLOCK*2), 'panic tail')
        receipt['presets'][name] = {'reverse_interval_changed_samples': n, 'arms': {}}
        for arm, (pcm, states) in arms.items():
            with wave.open(str(args.output / f'{name}-{arm}.wav'), 'wb') as wav:
                wav.setparams((1, 2, RATE, 0, 'NONE', 'not compressed'))
                wav.writeframes(pcm)
            receipt['presets'][name]['arms'][arm] = {
                'pcm_sha256': hashlib.sha256(pcm).hexdigest(), 'snapshots': states}
        print(f'{name}: {n}/{70*BLOCK} changed reverse-interval samples, exact prelude and panic tail')
    out = (json.dumps(receipt, sort_keys=True, separators=(',', ':')) + '\n').encode()
    (args.output / 'direction-replay.json').write_bytes(out)
    print('PASS: 960 native snapshots; six WAVs; exact repeated native renders; SHA256',
          hashlib.sha256(out).hexdigest())


if __name__ == '__main__':
    main()
