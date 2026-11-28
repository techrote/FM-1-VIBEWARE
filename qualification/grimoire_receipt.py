"""Independent PCM and provenance checks for frozen Grimoire #24 receipts."""
import hashlib
import io
import json
from pathlib import Path
import sys
import wave
import zipfile

PINS = {'integration':'dceed6756bcc6784fdbd116f1a76e5b726ac936a',
        'cydaux':'5c3d7960ee76132cca95c92394010403f8bd638f',
        'grimoire':'ca1b83a5f6c8f1e87dea671f93f7e2a6d3bc432f',
        'dinghy':'92f17b28f2d05f2f78fd1b160b58475d518902c8',
        'emulator':'736aded65c8e2e9d652cf595fca248734483a877',
        'toolchain_archive':'cb896562418a2be93edb9bac26af4bc81a106a32974002a78e6b9fc203c93990'}
ARCHIVE = 'b02bd1176686e68a3502a34ea2a561c7a04c1544153b2d3e7b758a058b90a1db'
XIP = '5b06bc2fd0c341440af7ead962ede7fe1d22c7a48118723c67b2df0d40becaa8'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def inspect(read):
    pins = dict(line.split('=',1) for line in read('pins.txt').decode().splitlines())
    assert all(pins.get(k)==v for k,v in PINS.items()), pins
    manifest = json.loads(read('sha256.json'))
    assert manifest and all(sha(read(k))==v for k,v in manifest.items()), 'manifest mismatch'
    xip = json.loads(read('xip.json'))
    assert (xip['purpose'],xip['bytes'],xip['xip_sha256']) == ('emulator-only',57540,XIP)
    assert read('grimoire.map').strip()
    result = {'pins':pins,'xip':XIP,'modes':{}}
    for mode in ('instruction','strict'):
        info = json.loads(read(f'{mode}/qualification.json'))
        assert info['mode']==mode and info['status']=='PASS' and info['usb_audio_underruns']==0
        assert info['source']=='actual pi32v2 firmware in fm1-emu USB model'
        assert 'panel ownership across stale release and expiry' in info['checks']
        waves = {}
        for name in ('y0','repeat','y127','standalone','full-session'):
            raw = read(f'{mode}/grimoire-{name}.wav')
            with wave.open(io.BytesIO(raw),'rb') as w:
                assert (w.getnchannels(),w.getsampwidth(),w.getframerate(),w.getcomptype()) == (2,2,44100,'NONE')
                n=w.getnframes(); pcm=w.readframes(n)
            assert len(pcm)==n*4 and any(pcm)
            waves[name]=pcm
        def onset(pcm):
            first=next(i for i in range(0,len(pcm),4) if any(pcm[i:i+4]))
            out=pcm[first:first+8192]
            assert len(out)==8192
            return out
        assert onset(waves['y0'])==onset(waves['repeat'])
        assert onset(waves['y0'])!=onset(waves['y127'])
        for name in ('standalone','full-session'):
            assert not any(waves[name][-2205*4:]), name
        full=waves['full-session']
        assert len(full)==info['i2s_frames']*4 and len(full)>44100*4*6
        # The late panel-owned interval precedes HOME by 0.5–1.0 s.
        late=full[-44100*4:-22050*4]
        assert sum(any(late[i:i+4]) for i in range(0,len(late),4))>1000, 'late panel audio absent'
        result['modes'][mode]={name:sha(pcm) for name,pcm in waves.items()}
    return result


def main():
    original, rebuilt = map(Path,sys.argv[1:])
    assert sha(original.read_bytes())==ARCHIVE, 'original archive mismatch'
    with zipfile.ZipFile(original) as z:
        names=z.namelist()
        assert len(names)==len(set(names)) and z.testzip() is None
        a=inspect(z.read)
    b=inspect(lambda name:(rebuilt/name).read_bytes())
    assert a==b, 'original and rebuilt PCM or provenance differ'
    print(json.dumps(b,sort_keys=True))


if __name__=='__main__':
    main()
