"""Guarded bare emulator XIP conversion. No install/update packaging."""
import argparse
import hashlib
import json
import struct
from pathlib import Path

BASE, ENTRY, END = 0x02000000, 0x02000120, 0x02100000

def flatten(blob):
    if len(blob) < 52 or blob[:7] != b'\x7fELF\x01\x01\x01':
        raise ValueError('expected little-endian ELF32')
    kind, machine, version, entry, phoff, _, _, ehsize, entsize, count = struct.unpack_from('<HHIIIIIHHH', blob, 16)
    if (kind,machine,version,entry,ehsize,entsize)!=(2,241,1,ENTRY,52,32):
        raise ValueError('unexpected executable identity/entry/header sizes')
    if not 1<=count<=64 or phoff<52 or phoff+32*count>len(blob):
        raise ValueError('invalid program table')
    segments=[]
    for i in range(count):
        typ, off, va, pa, size, mem, flags, align=struct.unpack_from('<8I',blob,phoff+32*i)
        if typ!=1 or not size: continue
        if size>mem or off+size>len(blob) or not BASE<=pa<pa+size<=END:
            raise ValueError('invalid initialized load segment')
        if any(pa<q+n and q<pa+size for q,n,_,_,_ in segments):
            raise ValueError('overlapping initialized loads')
        segments.append((pa,size,off,va,flags))
    if not any(pa<=ENTRY<pa+size and va==pa and flags&1 for pa,size,off,va,flags in segments):
        raise ValueError('entry not covered by executable XIP segment')
    image=bytearray(b'\xff'*(max(pa+size for pa,size,_,_,_ in segments)-BASE))
    for pa,size,off,_,_ in segments: image[pa-BASE:pa-BASE+size]=blob[off:off+size]
    return bytes(image), segments

def main():
    p=argparse.ArgumentParser(); p.add_argument('elf',type=Path); p.add_argument('output',type=Path); a=p.parse_args()
    if not a.output.name.endswith('.xip.bin'): p.error('output must end in .xip.bin')
    b=a.elf.read_bytes(); raw,segs=flatten(b)
    with a.output.open('xb') as f: f.write(raw)
    print(json.dumps({'entry':hex(ENTRY),'elf_sha256':hashlib.sha256(b).hexdigest(),'xip_sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw),'segments':segs,'purpose':'emulator-only'}))

if __name__=='__main__': main()
