"""Quantify actual Grimoire target interpolation A/B, not physical performance."""
import cmath
import hashlib
import json
import math
import struct
import sys
import wave
from pathlib import Path

RATE = 44100
N = 4096
START, END = RATE, 3 * RATE  # Common note-on interval; excludes PLAY/HOME edges.


def require(condition, message):
    if not condition:
        raise ValueError(message)


def fft(values):
    a = [complex(x) for x in values]
    n = len(a)
    require(n > 0 and n & (n - 1) == 0, 'FFT length must be a power of two')
    j = 0
    for i in range(1, n):
        bit = n >> 1
        while j & bit:
            j ^= bit
            bit >>= 1
        j ^= bit
        if i < j:
            a[i], a[j] = a[j], a[i]
    size = 2
    while size <= n:
        half = size // 2
        roots = [cmath.exp(-2j * math.pi * k / size) for k in range(half)]
        for i in range(0, n, size):
            for k, root in enumerate(roots):
                u, v = a[i + k], a[i + k + half] * root
                a[i + k], a[i + k + half] = u + v, u - v
        size *= 2
    return a[:n // 2 + 1]


def high_fraction(samples):
    require(len(samples) >= N, 'insufficient analysis samples')
    window = [0.5 - 0.5 * math.cos(2 * math.pi * k / (N - 1)) for k in range(N)]
    total = high = 0.0
    for i in range(0, len(samples) - N + 1, N // 2):
        bins = fft([samples[i + k] * window[k] for k in range(N)])
        for k, value in enumerate(bins[1:], 1):
            power = abs(value) ** 2 * (1 if k == N // 2 else 2)
            total += power
            if k * RATE >= 12000 * N:
                high += power
    require(total > 0, 'silent analysis interval')
    return high / total


def pcm(path):
    with wave.open(str(path), 'rb') as w:
        require((w.getnchannels(), w.getsampwidth(), w.getframerate()) == (2, 2, RATE), 'PCM format')
        frames = w.getnframes()
        raw = w.readframes(frames)
    require(frames >= 4 * RATE and len(raw) == frames * 4, 'PCM length')
    stereo = list(struct.iter_unpack('<hh', raw))
    require(all(l == r for l, r in stereo), 'Grimoire mono/stereo mismatch')
    mono = [l for l, _ in stereo]
    require(any(mono[START:END]) and not any(mono[-RATE // 2:]), 'performance or HOME tail')
    return mono


def sizes(path):
    sections = {}
    for line in path.read_text().splitlines():
        fields = line.split()
        if len(fields) == 3 and fields[0].startswith('.'):
            require(fields[0] not in sections, 'duplicate ELF section')
            sections[fields[0]] = int(fields[1])
    require(set(sections) == {'.text', '.ram_text', '.data', '.bss', '.pool', '.noinit'}, 'unexpected section inventory')
    return sections


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def analyze(root):
    probe = root / 'rate-probe'
    receipt = json.loads((probe / 'summary.json').read_text())
    require(receipt['status'] == 'PASS', 'probe gate not passed')
    variants = receipt['variants']
    sections = {m: sizes(probe / f'{m}-size.txt') for m in ('hold', 'linear')}
    results = {}
    for note in ('n3', 'n9'):
        arms = {}
        for mode in ('hold', 'linear'):
            path = probe / f'{mode}-{note}.wav'
            record = variants[mode][note]
            require(digest(path) == record['sha256'], 'PCM digest mismatch')
            if mode == 'hold':
                require(digest(path) == digest(root / f'orbit-{note}.wav'), 'instrumentation changed baseline PCM')
            if note == 'n3':
                repeat = probe / f'{mode}-n3-repeat.wav'
                require(digest(repeat) == digest(path) == variants[mode]['n3-repeat']['sha256'], 'repeat PCM mismatch')
                require(variants[mode]['n3-repeat'] == record, 'repeat timing mismatch')
            samples = pcm(path)
            arms[mode] = dict(frames=len(samples), peak=max(map(abs, samples)),
                              rms=math.sqrt(sum(x*x for x in samples[START:END]) / (END-START)),
                              high_fraction=high_fraction(samples[START:END]),
                              active_peak_ticks=record['active_peak_ticks'])
        h, l = arms['hold'], arms['linear']
        a, b = variants['hold'][note], variants['linear'][note]
        for key in ('blocks', 'active_blocks', 'model_timer_hz', 'block_frames', 'wrong_size_blocks'):
            require(a[key] == b[key], 'unmatched modeled callback schedule: ' + key)
        require(h['frames'] == l['frames'], 'unmatched PCM duration')
        require(h['high_fraction'] > 0 and l['high_fraction'] > 0, 'zero high-band power')
        results[note] = dict(arms=arms, high_band_delta_db=10*math.log10(l['high_fraction']/h['high_fraction']),
                             active_peak_delta_percent=100*(l['active_peak_ticks']/h['active_peak_ticks']-1))
    return dict(status='PASS', scope='matched virtual Grimoire observations only; no adoption or physical claim',
                analysis_frames=[START, END], fft_frames=N, cutoff_hz=12000,
                section_bytes=sections, section_delta={k: sections['linear'][k]-v for k,v in sections['hold'].items()},
                notes=results)


def self_test():
    a = [math.sin(2*math.pi*1000*i/RATE) for i in range(2*N)]
    b = [math.sin(2*math.pi*16000*i/RATE) for i in range(2*N)]
    require(high_fraction(a) < 1e-6 and high_fraction(b) > .999, 'frequency classification')
    require(all(abs(x-y) < 1e-12 for x,y in zip(fft([1,0,0,0]), [1,1,1])), 'impulse FFT')
    for invalid in ([0]*N, [1]*10):
        try:
            high_fraction(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError('invalid spectrum accepted')
    print('rate quality self-test PASS')


if __name__ == '__main__':
    if sys.argv[1:] == ['--test']:
        self_test()
    elif len(sys.argv) == 2:
        print(json.dumps(analyze(Path(sys.argv[1])), indent=2))
    else:
        raise SystemExit('rate_quality.py --test | platform-results')
