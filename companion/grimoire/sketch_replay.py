"""Offline Orbit Sketch comparison using the actual JS controller and C session."""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import wave

from replay import RATE, BLOCK, Session, bind, require

# Same 1200-frame cadence as the interactive host; this is not a wire protocol.
JS = r'''
const R = require(process.argv[1]).Ribbon;
const points = [[18,114],[35,96],[62,70],[95,105],[111,35],[77,14],[43,48],[20,82]];
const doc = R.encodeSketch(points);
function arm(mode) {
  const r = new R(), rows = [];
  r.setSpeed(2);
  for(let k=0;k<160;k++) {
    if(k===40 && mode!=='factory') {
      r.setSketch(mode==='imported' ? R.decodeSketch(doc) : points);
      r.setShape('sketch');
    }
    if(k===80)r.take(60,40);
    if(k===90)r.resume();
    if(k===150)r.reset();
    const xy=r.block();
    rows.push({xy: k===80 ? [60,40] : xy, phase:r.phase, carry:r.carry,
      manual:r.manual, blend:r.blend, shape:r.shape, speed:r.speed});
  }
  return rows;
}
console.log(JSON.stringify({document:JSON.parse(doc),factory:arm('factory'),
  authored:arm('authored'),imported:arm('imported')}));
'''


def schedule():
    path = Path(__file__).with_name('gesture.js').resolve()
    return json.loads(subprocess.check_output(['node', '-e', JS, str(path)], text=True))


def render(lib, preset, rows):
    s = Session()
    lib.os_init(C.byref(s))
    gen = lib.os_connect(C.byref(s), 1)
    require(gen == 1, 'connect')
    buf = (C.c_int16 * BLOCK)()
    pcm, states = bytearray(), []

    def event(op, a=0, b=0):
        require(lib.os_event(C.byref(s), gen, op, a, b) == 1, 'event rejected')

    event(3, preset)
    event(2, 1)
    for k, row in enumerate(rows):
        if k == 140:
            event(2, 0)
        if k == 145:
            event(2, 1)
        if k == 150:
            require(s.core.gate and s.core.env and s.core.energy, 'panic must interrupt active sound')
            event(4)
        if row['xy'] is not None:
            before = (tuple(s.core.phase), s.core.env, s.core.ticks, s.core.gate)
            event(1, *row['xy'])
            require(before == (tuple(s.core.phase), s.core.env, s.core.ticks, s.core.gate),
                    'XY changed native lifecycle')
        lib.os_render(C.byref(s), buf, BLOCK)
        c = s.core
        block = struct.pack('<1200h', *buf)
        peak = max(map(abs, buf))
        require(c.ticks == (k + 1) * BLOCK and c.preset == preset and c.gate == (k < 140 or 145 <= k < 150),
                'native lifecycle')
        require(c.env <= 32767 and c.energy <= 28000 and peak <= 28000, 'signal bounds')
        if 80 <= k < 90:
            require((c.x, c.y) == (60, 40), 'manual ownership')
        if k == 144:
            require(peak == c.env == 0, 'release tail')
        if k >= 150:
            require(peak == c.env == c.energy == 0, 'panic silence')
        pcm.extend(block)
        states.append({'block': k, 'end_sample': c.ticks, 'controller': row,
                       'x': c.x, 'y': c.y, 'gate': c.gate, 'env': c.env,
                       'energy': c.energy, 'phase_u16': [v >> 16 for v in c.phase],
                       'peak': peak, 'pcm_sha256': hashlib.sha256(block).hexdigest()})
    lib.os_disconnect(C.byref(s))
    require(lib.os_connect(C.byref(s), 2) == 0, 'version mismatch')
    require(lib.os_connect(C.byref(s), 1) == 2, 'reconnect')
    require(not lib.os_event(C.byref(s), gen, 2, 1, 0), 'stale gate accepted')
    lib.os_render(C.byref(s), buf, BLOCK)
    require(not any(buf), 'stale session sounded')
    return bytes(pcm), states


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('library')
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    data = schedule()
    require(data == schedule(), 'controller nondeterminism')
    require(data['authored'] == data['imported'], 'exchange changed controller trajectory')
    factory, authored = data['factory'], data['authored']
    require(factory[:40] == authored[:40], 'pre-apply changed controller')
    require(all((a['phase'], a['carry']) == (b['phase'], b['carry'])
                for a, b in zip(factory, authored)), 'controller clock reset')
    require(authored[40]['shape'] == 'sketch' and authored[40]['blend'] == 6 and
            authored[43]['blend'] == 0 and authored[93]['blend'] == 0, 'blend cadence')
    lib = bind(args.library)
    receipt = {'schema': 'grimoire.orbit-sketch.local-replay.v1',
               'state_source': 'offline JS controller and native C core, not device telemetry',
               'sample_rate_hz': RATE, 'block_frames': BLOCK, 'document': data['document'],
               'presets': {}}
    for preset, name in enumerate(('amber', 'iron', 'abyss')):
        arms = {arm: render(lib, preset, data[arm]) for arm in ('factory', 'authored', 'imported')}
        for arm, result in arms.items():
            require(result == render(lib, preset, data[arm]), 'native nondeterminism')
        require(arms['authored'] == arms['imported'], 'exchange changed native state or PCM')
        base, custom = arms['factory'][0], arms['authored'][0]
        require(base[:40*BLOCK*2] == custom[:40*BLOCK*2], 'pre-apply PCM changed')
        changed = sum(a != b for (a,), (b,) in zip(struct.iter_unpack('<h', base),
                                                    struct.iter_unpack('<h', custom)))
        require(changed > 50*BLOCK, 'sketch did not materially change PCM')
        receipt['presets'][name] = {'changed_samples': changed, 'arms': {}}
        for arm, (pcm, states) in arms.items():
            with wave.open(str(args.output / f'{name}-{arm}.wav'), 'wb') as wav:
                wav.setparams((1, 2, RATE, 0, 'NONE', 'not compressed'))
                wav.writeframes(pcm)
            receipt['presets'][name]['arms'][arm] = {
                'pcm_sha256': hashlib.sha256(pcm).hexdigest(), 'snapshots': states}
        print(f'{name}: {changed}/{len(base)//2} changed samples; authored/imported exact')
    out = (json.dumps(receipt, sort_keys=True, separators=(',', ':')) + '\n').encode()
    (args.output / 'sketch-replay.json').write_bytes(out)
    print('PASS: 1440 native snapshots; 9 WAVs; 12000 silent panic samples per arm; SHA256',
          hashlib.sha256(out).hexdigest())


if __name__ == '__main__':
    main()
