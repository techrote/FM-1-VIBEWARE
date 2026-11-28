"""Independent validator for the pinned CYDaux bridge negative lifecycle receipts."""
import json, hashlib, re, stat, sys, zipfile
from pathlib import Path

PIN = '8c709af4e740a3f5700a8b8ca68492467f613016'
CYD = 'b33830ef50c52663d83a69bb1e5f25b109bc9053'
DIGEST = '7165ba5cdcd5981cc780f4f2212b668e6d02abc0d7e168997a2f6b87cbfc130a'
SILENT = ('panic', 'socket_drop', 'stale_session', 'version_profile_refusal', 'bridge_timeout', 'malformed_frame', 'malformed_stale_replay', 'malformed_recovery_panic')
SOUNDING = ('strike', 'malformed_recovery_strike')

def require(ok, reason):
    if not ok:
        raise ValueError(reason)

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def extract(path, dest):
    require(sha(path) == DIGEST, 'original artifact digest')
    with zipfile.ZipFile(path) as z:
        seen = set()
        require(sum(i.file_size for i in z.infolist()) < 64*1024*1024, 'expanded size')
        for i in z.infolist():
            n = i.filename
            require(n and all(re.fullmatch(r'[A-Za-z0-9_-][A-Za-z0-9_.-]*', x) for x in n.rstrip('/').split('/')), 'unsafe path')
            require(n.casefold() not in seen and not stat.S_ISLNK(i.external_attr >> 16), 'duplicate or symlink')
            seen.add(n.casefold())
            require(i.is_dir() or Path(n).suffix in ('.txt','.json','.log','.map','.wav','.bmp'), 'unexpected file type')
        z.extractall(dest)

def validate(report):
    require(report['status']=='PASS' and report['physical']=='NOT RUN', 'scope')
    require(report['timing']=='instruction-clock, explicit modeled advances', 'timing scope')
    require(type(report['messages']) is int and 0 < report['messages'] < 128, 'message bound')
    w=report['witnesses']
    require(w['identity']=='Emulated firmware', 'identity')
    require(w['bridge_refusals']==['protocol','token','preauth MIDI','unknown profile','out-of-range MIDI'], 'refusals')
    for name in SILENT+SOUNDING:
        p=w[name]
        n,k=p['samples'],p['nonzero']
        require(type(n) is int and type(k) is int and 0 < n < 4_000_000 and 0 <= k <= n, name+' bounds')
        require(isinstance(p['hash'],str) and re.fullmatch('[0-9a-f]{16}',p['hash']), name+' hash')
        zero=(14695981039346656037*pow(1099511628211,n,2**64))%(2**64)
        if name in SILENT:
            require(k==0 and p['hash']==f'{zero:016x}', name+' zero PCM')
        else:
            require(k>128 and p['hash']!=f'{zero:016x}', name+' sounding PCM')
    return report

def inspect(root):
    manifest=json.loads((root/'sha256.json').read_text())
    actual={p.relative_to(root).as_posix():sha(p) for p in root.rglob('*') if p.is_file() and p!=root/'sha256.json'}
    require(manifest==actual,'manifest mismatch')
    pins=dict(line.split('=',1) for line in (root/'pins.txt').read_text().splitlines())
    require(pins['integration']==PIN and pins['cydaux']==CYD and pins['emulator']=='736aded65c8e2e9d652cf595fca248734483a877','source pin mismatch')
    xip=json.loads((root/'xip.json').read_text())
    require(xip['purpose']=='emulator-only','target scope')
    report=validate(json.loads((root/'bridge-usb.json').read_text()))
    return {'pins':pins,'xip':xip,'bridge':report}

if __name__=='__main__':
    archive, original, rebuilt=map(Path,sys.argv[1:])
    extract(archive,original)
    a,b=inspect(original),inspect(rebuilt)
    require(a==b,'independent replay differs from author receipt')
    print(json.dumps({'status':'PASS','scope':'emulated bridge; physical NOT RUN','evidence':b},sort_keys=True))
