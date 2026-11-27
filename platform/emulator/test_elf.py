import struct
import unittest
from elf_xip import flatten, BASE, ENTRY, END

def fixture(segments):
    h=bytearray(256)
    h[:7]=b'\x7fELF\x01\x01\x01'
    struct.pack_into('<HHIIIIIHHH',h,16,2,241,1,ENTRY,52,0,0,52,32,len(segments))
    for i,s in enumerate(segments): struct.pack_into('<8I',h,52+i*32,*s)
    h[200:204]=b'ABCD'; h[204:208]=b'EFGH'
    return h

A=(1,200,ENTRY,ENTRY,4,4,5,4)
B=(1,204,0x01c08000,ENTRY+16,4,8,6,4)
class GuardTests(unittest.TestCase):
    def test_good(self):
        out,_=flatten(fixture([A,B])); self.assertEqual(out[ENTRY-BASE:],b'ABCD'+b'\xff'*12+b'EFGH')
    def test_bad(self):
        for bad in [(1,200,ENTRY,ENTRY,4,2,5,4),(1,254,ENTRY,ENTRY,4,4,5,4),(1,200,ENTRY,ENTRY,4,4,4,4),(1,200,ENTRY,END-2,4,4,5,4)]:
            with self.subTest(bad=bad), self.assertRaises(ValueError): flatten(fixture([bad]))
        with self.assertRaises(ValueError): flatten(fixture([A,A]))
        for idx in (0,18,24,28,42,44):
            b=fixture([A]); b[idx]^=0xff
            with self.subTest(idx=idx), self.assertRaises(ValueError): flatten(b)
if __name__=='__main__': unittest.main()
