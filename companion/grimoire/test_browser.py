"""Real Chromium + Web Audio integration of the local native-core fixture.
Requires playwright and Chromium; no FM-1/CYD hardware claims.
"""
import argparse
import pathlib
import socket
import subprocess
import sys
import time
import urllib.request
from playwright.sync_api import sync_playwright


def run(library, executable, screenshot):
    root = pathlib.Path(__file__).resolve().parent
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    url = f'http://127.0.0.1:{port}'
    with subprocess.Popen([sys.executable, str(root / 'host.py'), str(library), '--port', str(port)],
                          stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) as host:
        try:
            for _ in range(100):
                try:
                    with urllib.request.urlopen(url, timeout=.2):
                        break
                except OSError:
                    if host.poll() is not None:
                        raise RuntimeError('host exited')
                    time.sleep(.05)
            else:
                raise RuntimeError('host did not start')
            with sync_playwright() as p:
                browser = p.chromium.launch(executable_path=executable, args=['--no-sandbox'])
                page = browser.new_page(viewport={'width': 600, 'height': 700})
                errors = []
                page.on('pageerror', lambda e: errors.append(str(e)))
                page.goto(url)
                page.locator('#start').click()
                page.wait_for_function('g > 0 && audio.state === "running"')
                first = page.evaluate('g')
                # Tap the actual Web Audio output bus, not decoded HTTP bytes.
                page.evaluate('''() => {window.meter=audio.createAnalyser();meter.fftSize=2048;
                  bus.connect(meter);const sink=audio.createGain();sink.gain.value=0;meter.connect(sink);sink.connect(audio.destination);window.peak=()=>{const a=new Float32Array(meter.fftSize);
                  meter.getFloatTimeDomainData(a);return Math.max(...a.map(Math.abs))}}''')
                page.evaluate('''() => {const original=draw; window.played=null; draw=d=>{window.played={x:d.x,y:d.y,gate:d.gate,preset:d.preset,source:d.state_source};original(d)}}''')
                def silence():
                    page.evaluate('window.quietSince = null')
                    page.wait_for_function('''() => {if(peak() >= .0001){quietSince=null;return false}
                      if(quietSince===null)quietSince=performance.now();return performance.now()-quietSince>200}''', timeout=5000)
                def gesture():
                    page.locator('#pad').scroll_into_view_if_needed()
                    box = page.locator('#pad').bounding_box()
                    page.mouse.move(box['x'] + box['width']*.25, box['y'] + box['height']*.3)
                    page.mouse.down()
                    page.wait_for_function('peak() > .02 && status.textContent.endsWith("gate")')
                    page.mouse.move(box['x'] + box['width']*.8, box['y'] + box['height']*.75, steps=12)
                    page.wait_for_timeout(60)
                    page.mouse.move(box['x'] + box['width']*.82, box['y'] + box['height']*.76)
                    page.wait_for_function('played && played.x>85 && played.y<45 && played.gate===1 && played.source==="local native core"')
                    assert page.evaluate('visuals.length <= 8 && sources.size <= 8')
                silence()
                # Ribbon has no autonomous gate; only explicit hold can sound.
                page.locator('#ribbonSpeed').select_option('4')
                page.wait_for_function('played && played.gate===0 && ribbon.phase>0')
                silence()
                page.locator('#holdGate').click()
                page.wait_for_function('played && played.gate===1 && peak()>.02')
                page.evaluate('window.ribbonFirstX=played.x')
                page.wait_for_function('played.gate===1 && played.x!==ribbonFirstX')
                # Changing the trajectory must keep the explicitly held gate and
                # advance the same clock; verify the bright arc via played native XY.
                page.locator('#ribbonShape').select_option('crown')
                page.wait_for_function('held && ribbon.shape==="crown" && ribbon.blend===0 && played.gate===1 && played.y>=96 && played.y<=120 && peak()>.02')
                page.locator('#ribbonShape').select_option('pendulum')
                page.wait_for_function('held && ribbon.shape==="pendulum" && ribbon.blend===0 && played.gate===1 && played.y>=24 && played.y<=48 && peak()>.02')
                page.locator('#pad').scroll_into_view_if_needed()
                box = page.locator('#pad').bounding_box()
                page.mouse.move(box['x']+box['width']*.95,box['y']+box['height']*.95)
                page.mouse.down()
                page.wait_for_function('ribbon.manual && played.gate===1 && played.x>115 && played.y<12')
                page.mouse.up()
                page.wait_for_function('!ribbon.manual && ribbon.blend===0 && played.gate===1 && played.x<110')
                page.locator('#holdGate').click()
                page.wait_for_function('played && played.gate===0')
                silence()
                page.locator('#holdGate').click()
                page.wait_for_function('played && played.gate===1 && peak()>.02')
                page.locator('#panic').click()
                page.wait_for_function('!held && ribbon.speed===0 && played && played.gate===0')
                silence()
                assert page.locator('#holdGate').is_disabled()
                assert page.locator('#ribbonSpeed').input_value()=='0'
                assert page.locator('#ribbonShape').input_value()=='ribbon'
                gesture()
                if screenshot:
                    page.screenshot(path=screenshot)
                page.mouse.up()
                page.wait_for_function('status.textContent.endsWith("release")')
                silence()
                page.locator('[data-p="2"]').click()
                page.wait_for_function('played && played.preset===2 && status.textContent.includes("Abyss")')
                gesture()
                page.evaluate('document.querySelector("#panic").click()')
                page.mouse.up()
                silence()
                page.wait_for_function('status.textContent.endsWith("release")')
                gesture()
                page.evaluate('window.dispatchEvent(new Event("blur"))')
                page.mouse.up()
                silence()
                gesture()
                # A real aborted HTTP fetch must clear pending audio/events and require reconnect.
                page.route('**/api', lambda route: route.abort())
                page.wait_for_function('g === 0 && status.textContent.startsWith("Disconnected:")')
                page.mouse.up()
                silence()
                assert page.evaluate('sources.size === 0 && visuals.length === 0 && queue.length === 0')
                page.unroute('**/api')
                page.locator('#start').click()
                page.wait_for_function(f'g > {first}')
                silence()
                gesture()
                page.mouse.up()
                silence()
                assert not errors, errors
                browser.close()
                print('Chromium actual Web Audio: XY/gate, clock-aligned bounded visuals, release, preset, panic, blur, HTTP abort and reconnect PASS')
        finally:
            host.terminate()
            host.wait(timeout=5)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('library', type=pathlib.Path)
    parser.add_argument('--chromium')
    parser.add_argument('--screenshot')
    args = parser.parse_args()
    run(args.library.resolve(), args.chromium, args.screenshot)
