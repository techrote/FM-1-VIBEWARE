"""Independent checks of fixed authored saved-score and direction replay fixtures."""
import hashlib
import json
from pathlib import Path
import struct
import sys
import wave

RATE, BLOCK, CYCLE = 24000, 1200, 144000000


def require(ok, what):
    if not ok:
        raise ValueError(what)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read(root, name):
    return json.loads((root / name).read_bytes())


def pcm(root, name, frames):
    with wave.open(str(root / (name + '.wav')), 'rb') as w:
        require((w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes(), w.getcomptype())
                == (1, 2, RATE, frames, 'NONE'), name + ' WAV format')
        data = w.readframes(frames)
    require(len(data) == frames * 2, name + ' WAV length')
    return data, struct.unpack('<%dh' % frames, data)


def chrono(root, pin):
    require((root / 'source-revision.txt').read_text().strip() == pin, 'source pin')
    bank = read(root, 'scene-bank.json')
    require(bank == {'format': 'chronomorph-scenes', 'version': 1, 'slots': [
        {'bpm': 96, 'warp': 15, 'variation': 9, 'patterns': [[3, 5], [8, 129], [5, 11]]}, None,
        {'bpm': 173, 'warp': -47, 'variation': 31, 'patterns': [[16, 32769], [7, 25], [4, 9]]}, None]}, 'fixture bank')
    r = read(root, 'receipt.json')
    require((r['rate'], r['block_frames'], r['seed'], r['preset'], r['seconds_per_cue'], r['slots'], r['frames'])
            == (RATE, BLOCK, 17, 0, 2, [1, 3], 120000), 'fixture receipt')
    require(r['bank_sha256'] == sha((root / 'scene-bank.json').read_bytes()), 'bank digest')
    audio = []
    traces = []
    for name in ('saved-score', 'fixed-pattern-control'):
        data, samples = pcm(root, name, 120000)
        rows = read(root, name + '.json')
        require(len(rows) == 100, 'trace length')
        require(r['arms'][name] == {'peak': max(map(abs, samples)),
            'wav_sha256': sha((root / (name + '.wav')).read_bytes()),
            'trace_sha256': sha((root / (name + '.json')).read_bytes())}, 'arm digest/peak')
        require(0 < max(map(abs, samples)) < 32767 and not any(samples[96000:]), 'signal/panic tail')
        master, beat = CYCLE - 1, 7
        clocks, ticks, steps, cycles = [CYCLE - 1]*3, [0]*3, [0]*3, [0]*3
        prior_hits = [0]*3
        for k, row in enumerate(rows):
            scene = bank['slots'][0 if k < 40 else 2]
            patterns = bank['slots'][0]['patterns'] if name == 'fixed-pattern-control' else scene['patterns']
            bpm, warp = scene['bpm'], scene['warp']
            require((row['block'], row['end_frame'], row['slot'], row['playing'], row['bpm'], row['warp'], row['variation'], row['patterns'])
                    == (k, (k+1)*BLOCK, 1 if k < 40 else 3, int(k < 80), bpm, warp, scene['variation'], sum(patterns, [])), 'scene schedule')
            old_ticks = ticks.copy()
            for i, (length, _) in enumerate(patterns):
                steps[i] = steps[i] % length if ticks[i] else length - 1
            if k < 80:
                base = bpm * 4
                for _ in range(BLOCK):
                    advance, master = divmod(master + base*100, CYCLE)
                    beat = (beat + advance) % 8
                    w = warp if beat < 4 else -warp
                    for i, rate in enumerate((100, 100+w, 100-int(w/2))):
                        advance, clocks[i] = divmod(clocks[i] + base*rate, CYCLE)
                        if advance:
                            ticks[i] += 1
                            steps[i] = (steps[i]+1) % patterns[i][0]
                            cycles[i] = (cycles[i]+int(steps[i] == 0)) % 4
            require(len(row['lanes']) == 3, 'lanes')
            for i, lane in enumerate(row['lanes']):
                step, tick, hits, cycle, phase = lane
                require((step, tick, cycle, phase) == (steps[i], ticks[i], cycles[i], clocks[i]), 'independent clock model')
                require(0 <= hits-prior_hits[i] <= tick-old_ticks[i], 'hit bound')
                prior_hits[i] = hits
        audio.append(samples)
        traces.append(rows)
    changes = [sum(a != b for a,b in zip(audio[0][i:i+48000], audio[1][i:i+48000])) for i in (0,48000)]
    require(changes == r['changed_samples'] == [0,45561], 'matched pattern PCM intervention')
    require(traces[0][:40] == traces[1][:40], 'matched prelude trace')
    return {'clock_lanes_checked': 600, 'changed_samples': changes, 'silent_frames_per_arm': 24000}


def grimoire(root, pin):
    r = read(root, 'direction-replay.json')
    require(r['source_revision'] == pin and r['schema'] == 'grimoire.orbit-direction.local-replay.v1', 'source/schema')
    require((r['sample_rate_hz'], r['block_frames']) == (RATE, BLOCK) and set(r['presets']) == {'amber','iron','abyss'}, 'fixture format')
    changes = {}
    controller = {}
    for name, preset in r['presets'].items():
        require(set(preset['arms']) == {'forward','reverse'}, 'arm set')
        audio, traces = [], []
        for arm in ('forward','reverse'):
            data, samples = pcm(root, name+'-'+arm, 192000)
            rec = preset['arms'][arm]
            rows = rec['snapshots']
            require(len(rows) == 160 and sha(data) == rec['pcm_sha256'], 'trace/PCM digest')
            phase, carry = 0, 0
            controls = []
            for k, row in enumerate(rows):
                c = row['controller']
                direction = -1 if arm == 'reverse' and 40 <= k < 110 else 1
                if k < 150:
                    ticks, carry = divmod(carry + 5, 2)
                    phase = (phase + ticks*2*direction) % 256
                else:
                    phase, carry = 0, 0
                require((c['phase'],c['carry'],c['direction'],c['speed'],c['manual']) ==
                        (phase,carry,direction,2 if k < 150 else 0,80 <= k < 90), 'independent signed clock')
                block = samples[k*BLOCK:(k+1)*BLOCK]
                require((row['block'],row['end_sample'],row['gate'],row['peak'],row['pcm_sha256']) ==
                        (k,(k+1)*BLOCK,int(k < 140 or 145 <= k < 150),max(map(abs,block)),sha(data[k*BLOCK*2:(k+1)*BLOCK*2])), 'native block alignment')
                require(0 <= row['env'] <= 32767 and 0 <= row['energy'] <= 28000 and row['peak'] <= 28000, 'signal bounds')
                if c['xy'] is not None:
                    require(c['xy'] == [row['x'],row['y']], 'control mapping')
                if 80 <= k < 90:
                    require([row['x'],row['y']] == [60,40], 'manual control')
                if k == 144 or k >= 150:
                    require(row['peak'] == row['env'] == 0, 'release/panic silence')
                if k >= 150:
                    require(row['energy'] == 0, 'panic energy')
                controls.append(c)
            if arm in controller:
                require(controls == controller[arm], 'preset-dependent controller')
            controller[arm] = controls
            audio.append(samples)
            traces.append(rows)
        require(audio[0][:48000] == audio[1][:48000] and traces[0][:40] == traces[1][:40], 'prelude identity')
        changed = sum(a != b for a,b in zip(audio[0][48000:132000],audio[1][48000:132000]))
        require(changed > BLOCK and changed == preset['reverse_interval_changed_samples'], 'reversal PCM witness')
        changes[name] = changed
    return {'native_blocks_checked': 960, 'changed_samples': changes, 'silent_frames_per_arm': 12000}


if __name__ == '__main__':
    kind, folder, pin = sys.argv[1:]
    print(json.dumps({'chronomorph': chrono, 'grimoire': grimoire}[kind](Path(folder),pin),sort_keys=True))
