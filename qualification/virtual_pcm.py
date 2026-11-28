"""Independent strict comparison against observed PLATFORM run 46039864752."""
import hashlib
import json
from pathlib import Path
import struct
import sys
import wave

BASELINE = {
    "scope-reference": "7bc82e8e554a31635f830358ac01539fad08796b7636af85521fbdfe5437104b",
    "orbit-n3": "dad86d9af4128a0150ff15ee5d3b70f4951c97efeb73dc19eada744cc11865b1",
    "orbit-n3-repeat": "dad86d9af4128a0150ff15ee5d3b70f4951c97efeb73dc19eada744cc11865b1",
    "orbit-n9": "922ff1e716e81bcbc9a17b982c7bd01382babfa9cf9461bd51e2161eca03ba33",
    "orbit-n3-uc25": "dad86d9af4128a0150ff15ee5d3b70f4951c97efeb73dc19eada744cc11865b1",
}

def inspect(path, expected):
    h=hashlib.sha256(path.read_bytes()).hexdigest()
    assert h==expected,(path,h,expected)
    with wave.open(str(path),"rb") as w:
        rate,frames,channels=w.getframerate(),w.getnframes(),w.getnchannels()
        assert rate==44100 and frames==179456 and channels in (1,2) and w.getsampwidth()==2
        data=w.readframes(frames)
        assert len(data)==frames*channels*2
    samples=struct.unpack("<"+"h"*(frames*channels),data)
    peak=max(map(abs,samples))
    assert 0<peak<32767
    assert any(samples[rate*channels:3*rate*channels]),"no sustained audible interval"
    assert not any(samples[-rate*channels//2:]),"nonzero 500ms HOME tail"
    return {"sha256":h,"frames":frames,"channels":channels,"rate":rate,"peak":peak,
            "nonzero_samples":sum(x!=0 for x in samples),"silent_tail_ms":500}

def main():
    root=Path(sys.argv[1])
    results={name:inspect(root/(name+".wav"),h) for name,h in BASELINE.items()}
    xip=json.loads((root/"grimoire-xip.json").read_text())
    assert xip["xip_sha256"]=="87dab6dde563f4001eaa4c394dc54a3fecf180c4d1d7567c3926e5c1a2a72866"
    assert xip["bytes"]==54896 and xip["purpose"]=="emulator-only"
    assert results["orbit-n3"]["sha256"]!=results["orbit-n9"]["sha256"]
    print(json.dumps({"pcm":results,"xip_sha256":xip["xip_sha256"],"purpose":"emulator-only; no physical or distribution qualification"},sort_keys=True))

if __name__=="__main__":
    main()
