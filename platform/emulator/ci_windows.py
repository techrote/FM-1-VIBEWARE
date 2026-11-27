"""Build and execute the same pinned targets natively on Windows, evidence only."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
import urllib.request
import wave
import zipfile

from elf_xip import flatten

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
EMU = '736aded65c8e2e9d652cf595fca248734483a877'
DINGHY = '92f17b28f2d05f2f78fd1b160b58475d518902c8'
MHAC = 'cc132a43b27c1d9f23bf50bca224567af49e208e'
TC = '0ffe01bde8aaefecee6ec9250cec741a2cd09d2ea2651f430850beefab7db322'
LINUX_TC = 'cb896562418a2be93edb9bac26af4bc81a106a32974002a78e6b9fc203c93990'
URL = 'https://github.com/jvitkauskas/pi32v2-llvm/releases/download/pi32v2-23.1.5-2/pi32v2-llvm-23.1.5-2-windows-x64.zip'
CORES = {
    'grimoire': ('core', '03102e8d82148a6dba871024f5944246e0c913e2', 'orbit', 'grimoire'),
    'ecophon': ('ecophon_core', 'acdc41839665271372cd69df1d09f5550556c87e', 'ecophon', 'ecophon'),
    'chronomorph': ('chronomorph_core', 'be57d9f77e9325271adbd4558dfd554c6cd81e19', 'chrono', 'chrono'),
}
BASE = '600-700:N3,900-1000:PLAY,3600-3700:HOME'
PRESET = '600-700:N3,900-1000:PLAY,1700-1900:SCL,3600-3700:HOME'
CASES = {
    'grimoire': [('orbit-n3', BASE), ('orbit-n3-repeat', BASE), ('orbit-n9', BASE.replace('N3', 'N9')), ('orbit-n3-uc25', BASE)],
    'ecophon': [('eco-low', BASE), ('eco-low-repeat', BASE), ('eco-high', BASE.replace('N3', 'N24')), ('eco-scarcity', PRESET), ('eco-scarcity-repeat', PRESET)],
    'chronomorph': [('chrono-low', BASE), ('chrono-low-repeat', BASE), ('chrono-warp', BASE.replace('N3', 'N24')), ('chrono-preset', PRESET), ('chrono-preset-repeat', PRESET), ('chrono-tempo', '600-700:N3,900-1000:PLAY,1700:K1:+12,3600-3700:HOME')],
}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args, cwd, log=None, env=None, timeout=900):
    args = [str(a) for a in args]
    p = subprocess.run(args, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout)
    if log is not None:
        log.write_bytes(p.stdout)
    if p.returncode:
        print(p.stdout.decode('utf-8', errors='replace'), flush=True)
        raise RuntimeError(f'{args[0]} exit {p.returncode}')
    return p.stdout.decode('utf-8', errors='replace').strip()


def checkout(url, path, pin):
    path.mkdir()
    run(['git', 'init', '-q'], path)
    run(['git', 'remote', 'add', 'origin', url], path)
    run(['git', 'fetch', '--depth=1', 'origin', pin], path)
    run(['git', 'checkout', '--detach', 'FETCH_HEAD'], path)
    require(run(['git', 'rev-parse', 'HEAD'], path) == pin, 'wrong checkout pin')


def check_linux_pins(linux, platform):
    pins = dict(line.split('=', 1) for line in (linux / 'pins.txt').read_text().splitlines())
    expected = dict(platform=platform, dinghy=DINGHY, mhac=MHAC, emu=EMU, toolchain_archive_sha256=LINUX_TC)
    expected.update({key: pin for key, pin, _, _ in CORES.values()})
    require(pins == expected, 'Linux evidence does not match exact Windows candidate pins')
    require((linux / 'downstream-status.txt').read_text().splitlines() == ['Ecophon exit=0', 'Chronomorph exit=0'], 'Linux downstream gate failed')
    return pins


def check_pcm(raw):
    require(len(raw) % 4 == 0 and len(raw) >= 44100 * 4 * 4, 'truncated stereo PCM')
    require(any(raw[:-22050 * 4]), 'no active audio')
    require(not any(raw[-22050 * 4:]), 'HOME tail is not silent')
    return len(raw) // 4


def check_wav(wav, reference):
    with wave.open(str(wav), 'rb') as f:
        require((f.getnchannels(), f.getsampwidth(), f.getframerate()) == (2, 2, 44100), 'unexpected WAV format')
        frames = check_pcm(f.readframes(f.getnframes()))
    require(sha(wav) == sha(reference), 'Windows WAV differs from same-run Linux reference')
    return dict(frames=frames, sha256=sha(wav))


def check_bench(metrics, pcm):
    frames = check_pcm(pcm)
    require(metrics['emulatedMs'] >= 4500 and metrics['audioFrames'] == frames, 'live benchmark duration/frame mismatch')
    require(all(isinstance(metrics[k], (int, float)) and math.isfinite(metrics[k]) and metrics[k] > 0 for k in ('wallSeconds', 'realtime', 'steadyRealtime')), 'invalid live timing')
    require(type(metrics['starvedHalves']) is int and metrics['starvedHalves'] >= 0, 'invalid starvation count')
    return frames


def build_target(name, work, dinghy, tc, results):
    _, pin, engine, adapter = CORES[name]
    core = work / (name + ' core')
    checkout('https://github.com/techrote/FM-1-VIBEWARE.git', core, pin)
    src = core / 'instruments' / name
    shutil.copyfile(HERE / (adapter + '_app.c'), dinghy / 'firmware/src/dinghy.c')
    clang = tc / 'clang.exe'
    flags = ['-target', 'pi32v2', '-mcpu=ac791n']
    app, dsp = work / (name + '-app.o'), work / (name + '-core.o')
    run([clang, *flags, '-Os', '-ffunction-sections', '-fno-builtin', '-Wall', '-Wno-unused-function', '-Ifirmware/hal', '-Ifirmware/src', '-Ifirmware/gen', '-I'+str(src), '-I'+str(HERE), '-DAPP_VER="dev"', '-DFELUCCA_ID="FM-1_990"', '-c', 'firmware/src/dinghy.c', '-o', app], dinghy, results / (name + '-compile-app.txt'))
    run([clang, *flags, '-Os', '-ffreestanding', '-fno-builtin', '-ffunction-sections', '-I'+str(HERE / 'include'), '-Wall', '-Wextra', '-Werror', '-c', src / (engine + '.c'), '-o', dsp], dinghy, results / (name + '-compile-core.txt'))
    objs = []
    for source in ('firmware/crt0.S', 'firmware/hal/fm1_vec.S', 'firmware/hal/fm1_isr.S'):
        obj = work / (Path(source).stem + '.o')
        run([clang, *flags, '-c', source, '-o', obj], dinghy)
        objs.append(obj)
    elf = work / (name + '.elf')
    run([tc / 'ld.lld.exe', '--gc-sections', '-e', '_start', '-T', 'firmware/app.ld', '-Map='+str(results / (name + '.map')), *objs, app, dsp, '-o', elf], dinghy, results / (name + '-link.txt'))
    run([tc / 'llvm-readelf.exe', '-h', '-l', elf], dinghy, results / (name + '-elf.txt'))
    run([tc / 'llvm-size.exe', '-A', elf], dinghy, results / (name + '-size.txt'))
    require(not run([tc / 'llvm-nm.exe', '-u', elf], dinghy), 'unresolved target symbols')
    raw, segments = flatten(elf.read_bytes())
    image = work / (name + '.xip.bin')
    image.write_bytes(raw)
    receipt = dict(entry='0x2000120', purpose='emulator-only', bytes=len(raw), xip_sha256=sha(image), elf_sha256=sha(elf), segments=segments)
    (results / (name + '-xip.json')).write_text(json.dumps(receipt, indent=2))
    return image, receipt


PANEL_HEADER = b'P6\n1280 820\n255\n'
PANEL_BYTES = 1280 * 820 * 3


def clean_env():
    # Prevent inherited emulator diagnostics, USB scripts, capture paths or
    # timing overrides from contaminating either the witness or owner launch.
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith('FM1_')}
    env['FM1_LCD_TIMED'] = '1'
    return env


def panel_digest(path):
    require(path.stat().st_size == len(PANEL_HEADER) + PANEL_BYTES, 'wrong panel image size')
    data = path.read_bytes()
    require(data.startswith(PANEL_HEADER), 'wrong panel PPM header')
    pixels = data[len(PANEL_HEADER):]
    require(min(pixels) != max(pixels), 'blank panel image')
    return hashlib.sha256(data).hexdigest()


def panel_receipt(cwd, results, name):
    # This is the upstream headless panel renderer, not a desktop GUI test.
    film = cwd / 'panel frames'
    expected = [film / f'{i:06}.ppm' for i in range(5)]
    require(sorted(film.glob('*.ppm')) == expected, 'incomplete panel timeline')
    paths = expected + [cwd / 'final.ppm']
    digests = [panel_digest(p) for p in paths]
    require(digests[0] != digests[2], 'panel never changed during performance')
    for tag, p in [('active', paths[2]), ('muted', paths[-1])]:
        shutil.copyfile(p, results / (name + '-panel-' + tag + '.ppm'))
    (results / (name + '-panel.json')).write_text(json.dumps(dict(
        kind='headless panel render, not desktop GUI',
        frames=[dict(ms=i*1000, sha256=d) for i,d in enumerate(digests[:5])],
        final_sha256=digests[-1], width=1280, height=820), indent=2))


def live_args(live, image):
    return [str(live), '--bin', str(image), '--entry', '0x02000120',
            '--midi', 'none', '--flash-chip', 'p25q80']


def target(name, work, dinghy, tc, results, linux, emu, live):
    image, receipt = build_target(name, work, dinghy, tc, results)
    original = json.loads((linux / (name + '-xip.json')).read_text())
    require((receipt['bytes'], receipt['xip_sha256']) == (original['bytes'], original['xip_sha256']), 'Windows XIP differs from same-run Linux build')
    env = clean_env()
    for case, keys in CASES[name]:
        cwd = work / case; cwd.mkdir()
        wav = results / (case + '.wav')
        chip = 'uc25hq80' if case.endswith('-uc25') else 'p25q80'
        run([emu, '--bin', image, '--entry', '0x02000120', '--ms', '4500', '--keys', keys, '--flash-chip', chip, '--wav', wav, '--quiet'], cwd, results / (case + '.log'), env, 300)
        (results / (case + '-match.json')).write_text(json.dumps(check_wav(wav, linux / wav.name), indent=2))
    live_witness(name, work, results, live, image)


def live_witness(name, work, results, live, image):
    cwd = work / (name + ' native live'); cwd.mkdir()
    env = clean_env()
    raw = cwd / 'bench.raw'
    metrics = results / (name + '-live.json')
    live_env = dict(env, FM1_BENCH_KEYS='600:N3,700:N3^,900:PLAY,1000:PLAY^,3600:HOME,3700:HOME^', FM1_BENCH_WAV=str(raw), FM1_BENCH_JSON=str(metrics), FM1_BENCH_FRAMES='panel frames,1000', FM1_BENCH_PANEL='final.ppm')
    run([*live_args(live, image), '--bench', '4500'], cwd, results / (name + '-live.log'), live_env, 300)
    pcm = raw.read_bytes()
    check_bench(json.loads(metrics.read_text()), pcm)
    with wave.open(str(results / (name + '-live.wav')), 'wb') as f:
        f.setparams((2, 2, 44100, 0, 'NONE', 'not compressed')); f.writeframes(pcm)
    panel_receipt(cwd, results, name)


def prepare(work, results):
    archive = work / 'compiler.zip'
    urllib.request.urlretrieve(URL, archive)
    require(sha(archive) == TC, 'Windows compiler archive digest mismatch')
    tcroot = work / 'compiler'; tcroot.mkdir()
    with zipfile.ZipFile(archive) as z:
        z.extractall(tcroot)  # fixed, digest-verified upstream archive
    matches = list(tcroot.rglob('clang.exe'))
    require(len(matches) == 1, 'ambiguous compiler layout')
    tc = matches[0].parent
    run([tc / 'clang.exe', '--version'], work, results / 'compiler.txt')
    dinghy, emusrc = work / 'dinghy source', work / 'emulator source'
    checkout('https://github.com/zvenson/dinghy.git', dinghy, DINGHY)
    checkout('https://github.com/joakimeriksson/fm1-emu.git', emusrc, EMU)
    run(['rustup', 'toolchain', 'install', '1.95.0', '--profile', 'minimal'], work, results / 'rustup.txt')
    run(['rustup', 'run', '1.95.0', 'cargo', 'build', '--release', '--locked', '-p', 'fm1-emu', '-p', 'fm1-live'], emusrc, results / 'cargo.txt', timeout=1800)
    emu, live = (emusrc / 'target/release' / (n + '.exe') for n in ('fm1-emu', 'fm1-live'))
    run([emu, '--version'], work, results / 'fm1-emu-version.txt')
    for exe in (emu, live):
        run([tc / 'llvm-readobj.exe', '--coff-imports', exe], work, results / (exe.stem + '-imports.txt'))
    return dinghy, tc, emu, live


def main(linux, results):
    require(os.name == 'nt', 'Windows native runner required')
    linux, results = linux.resolve(), results.resolve()
    results.mkdir()
    platform = run(['git', 'rev-parse', 'HEAD'], ROOT)
    pins = check_linux_pins(linux, platform)
    (results / 'pins.json').write_text(json.dumps(dict(pins, windows_toolchain_archive_sha256=TC), indent=2))
    with tempfile.TemporaryDirectory(prefix='VIBEWARE Windows virtual ') as d:
        work = Path(d).resolve()
        dinghy, tc, emu, live = prepare(work, results)
        statuses = {}
        for name in CORES:
            try:
                target(name, work, dinghy, tc, results, linux, emu, live)
                statuses[name] = 'PASS'
            except Exception as e:
                statuses[name] = 'FAIL: ' + repr(e)
                print(name, statuses[name], flush=True)
        (results / 'status.json').write_text(json.dumps(statuses, indent=2))
        require(all(s == 'PASS' for s in statuses.values()), 'one or more Windows virtual targets failed')


CONTROLS = {
    'grimoire': 'PLAY gate, note keys pitch, K1 material, SEL preset, HOME mute',
    'ecophon': 'PLAY ecology, K1 fertility, K2 pressure, note keys pressure, SEL regime, HOME mute',
    'chronomorph': 'PLAY transport, K1 tempo, K2 warp, K3 variation, SCL composition, HOME mute',
}


def play(name):
    require(os.name == 'nt', 'Windows native host required')
    print('Local source build only; emulator-only, NOT FLASHABLE. No MIDI or USB connection.', flush=True)
    print('Instrument: ' + name + ' / core ' + CORES[name][1], flush=True)
    print('Preparing pinned compiler, Dinghy and fm1-emu; network, Git, Rustup and native MSVC build tools required.', flush=True)
    with tempfile.TemporaryDirectory(prefix='VIBEWARE owner virtual ') as d:
        work = Path(d).resolve()
        results = work / 'private evidence'; results.mkdir()
        dinghy, tc, _, live = prepare(work, results)
        image, receipt = build_target(name, work, dinghy, tc, results)
        live_witness(name, work, results, live, image)
        print('Local target smoke PASS; XIP SHA256 ' + receipt['xip_sha256'], flush=True)
        print(CONTROLS[name] + '. Space = PLAY, 7 = HOME, Esc closes emulator.', flush=True)
        print('Launching native graphical panel; owner audio-device and manual control evaluation required.', flush=True)
        # No shell, no flash/USB/update switches, no inherited FM1_* variables,
        # no --bench. Keep the locally built files alive until the window exits.
        gui = work / 'owner panel'; gui.mkdir()
        subprocess.run(live_args(live, image), cwd=gui, env=clean_env(), check=True)


class Tests(unittest.TestCase):
    def test_panel(self):
        with tempfile.TemporaryDirectory(prefix='VIBEWARE panel fixture ') as d:
            p = Path(d); film = p / 'panel frames'; film.mkdir()
            out = p / 'evidence'; out.mkdir()
            data = PANEL_HEADER + bytes([0, 32, 255]) * (1280 * 820)
            changed = PANEL_HEADER + bytes([32, 0, 255]) * (1280 * 820)
            for i in range(5):
                (film / f'{i:06}.ppm').write_bytes(data if i < 2 else changed)
            (p / 'final.ppm').write_bytes(data)
            panel_receipt(p, out, 'test')
            self.assertEqual((out / 'test-panel-active.ppm').read_bytes(), changed)
            self.assertEqual((out / 'test-panel-muted.ppm').read_bytes(), data)
            self.assertEqual(len(json.loads((out / 'test-panel.json').read_text())['frames']), 5)
            for bad in (b'', b'P5' + data[2:], PANEL_HEADER + bytes(PANEL_BYTES)):
                (p / 'final.ppm').write_bytes(bad)
                with self.assertRaises(ValueError): panel_receipt(p, out, 'test')
            (p / 'final.ppm').write_bytes(data)
            (film / '000002.ppm').write_bytes(data)
            with self.assertRaises(ValueError): panel_receipt(p, out, 'test')
            (film / '000002.ppm').unlink()
            with self.assertRaises(ValueError): panel_receipt(p, out, 'test')

    def test_live_args(self):
        a = live_args(Path('path with spaces/fm1-live.exe'), Path('path with spaces/virtual.xip.bin'))
        self.assertEqual(a, ['path with spaces/fm1-live.exe'.replace('/', os.sep), '--bin',
                            'path with spaces/virtual.xip.bin'.replace('/', os.sep), '--entry',
                            '0x02000120', '--midi', 'none', '--flash-chip', 'p25q80'])
        self.assertFalse(set(a) & {'--flash', '--fwsc', '--fw', '--usb', '--bench'})
        from unittest.mock import patch
        with patch.dict(os.environ, {'FM1_USB_SEND':'unexpected', 'fm1_bench_wav':'unexpected'}):
            e = clean_env()
            self.assertEqual({k:v for k,v in e.items() if k.upper().startswith('FM1_')}, {'FM1_LCD_TIMED':'1'})


    def test_pcm(self):
        raw = b'\x01\x00\x02\x00' * (44100 * 4 - 22050) + bytes(22050 * 4)
        self.assertEqual(check_pcm(raw), 176400)
        for bad in (b'', raw[:-1], bytes(len(raw)), raw[:-1] + b'\x01'):
            with self.assertRaises(ValueError): check_pcm(bad)
        with tempfile.TemporaryDirectory(prefix='VIBEWARE fixture spaces ') as d:
            a, b = Path(d)/'a.wav', Path(d)/'b.wav'
            for p in (a, b):
                with wave.open(str(p), 'wb') as f:
                    f.setparams((2, 2, 44100, 0, 'NONE', 'not compressed')); f.writeframes(raw)
            self.assertEqual(check_wav(a, b)['frames'], 176400)
            b.write_bytes(b.read_bytes() + b'x')
            with self.assertRaises(ValueError): check_wav(a, b)
        metrics = dict(emulatedMs=4500, audioFrames=176400, wallSeconds=2.0, realtime=2.25, steadyRealtime=2.0, starvedHalves=0)
        self.assertEqual(check_bench(metrics, raw), 176400)
        for key, value in [('emulatedMs', 4499), ('audioFrames', 1), ('steadyRealtime', float('nan')), ('starvedHalves', -1)]:
            with self.assertRaises(ValueError): check_bench(dict(metrics, **{key: value}), raw)

    def test_pins(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d); platform = 'a'*40
            pins = dict(platform=platform, dinghy=DINGHY, mhac=MHAC, emu=EMU, toolchain_archive_sha256=LINUX_TC)
            pins.update({key: pin for key, pin, _, _ in CORES.values()})
            (p/'pins.txt').write_text('\n'.join(k+'='+v for k,v in pins.items())+'\n')
            (p/'downstream-status.txt').write_text('Ecophon exit=0\nChronomorph exit=0\n')
            self.assertEqual(check_linux_pins(p, platform), pins)
            with self.assertRaises(ValueError): check_linux_pins(p, 'b'*40)
            (p/'downstream-status.txt').write_text('Ecophon exit=1\nChronomorph exit=0\n')
            with self.assertRaises(ValueError): check_linux_pins(p, platform)


if __name__ == '__main__':
    if sys.argv[1:] == ['--test']:
        unittest.main(argv=[sys.argv[0]], verbosity=2)
    elif sys.argv[1:] == ['--list']:
        for name, controls in CONTROLS.items():
            print(name + ': ' + controls)
    elif len(sys.argv) == 3 and sys.argv[1] == '--play':
        parser = argparse.ArgumentParser(description='Local source-built Windows virtual audition (emulator only)')
        parser.add_argument('--play', choices=tuple(CORES), required=True)
        play(parser.parse_args().play)
    elif len(sys.argv) == 3 and not sys.argv[1].startswith('-') and not sys.argv[2].startswith('-'):
        main(Path(sys.argv[1]), Path(sys.argv[2]))
    else:
        raise SystemExit('usage: ci_windows.py <linux-evidence-dir> <new-windows-evidence-dir> | --test | --list | --play <instrument>')
