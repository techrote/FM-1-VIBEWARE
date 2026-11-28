import io
import pathlib
import subprocess
import sys
import urllib.error
import urllib.request
import wave

root = pathlib.Path(__file__).resolve().parent
proc = subprocess.Popen([sys.executable, str(root/'audition.py'), sys.argv[1], '--port', '0'], stdout=subprocess.PIPE, text=True)
try:
    url = proc.stdout.readline().strip()
    assert url.startswith('http://127.0.0.1:')
    def get(path):
        with urllib.request.urlopen(url+path, timeout=10) as response:
            return response.read()
    assert b'Xenoresonator' in get('/')
    base = '/render?p=2&e=76&d=12&c={}&n=48&v=110&phrase=0'
    a = get(base.format(90)); b = get(base.format(0))
    assert a == get(base.format(90)) and a != b
    for data in (a,b):
        with wave.open(io.BytesIO(data)) as w:
            assert w.getparams()[:4] == (1,2,24000,48000)
            assert any(w.readframes(48000))
    for bad in (base.format(128), base.format('0&c=1'), base.format('-1'), '/render?p=1'):
        try:
            get(bad)
        except urllib.error.HTTPError as e:
            assert e.code == 400
        else:
            raise AssertionError(bad)
    print('PASS localhost actual-core deterministic WAV, coupling response and four malformed controls')
finally:
    proc.terminate()
    proc.wait(timeout=10)
