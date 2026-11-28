"""Native local material-memory consumer; no device or transport claims."""
import ctypes as C
import pathlib
import sys


def load(path):
    lib = C.CDLL(str(pathlib.Path(path).resolve()))
    pcm = C.c_int16 * 1200
    levels = C.c_uint32 * 6
    u = C.c_uint
    ptrs = [C.POINTER(C.c_int16), C.POINTER(C.c_uint32)]
    lib.live_block.argtypes = [u] * 7 + ptrs
    lib.live_block.restype = None
    for name in ('live_reset', 'live_panic'):
        fn = getattr(lib, name)
        fn.argtypes = []
        fn.restype = None
    return lib, pcm, levels


def main():
    lib, pcm, levels = load(sys.argv[1])
    old = load(sys.argv[2])[0] if len(sys.argv) > 2 else lib
    u = C.c_uint
    ptrs = [C.POINTER(C.c_int16), C.POINTER(C.c_uint32)]
    for name, args in [('clear', []), ('store', [u]*5), ('capture', [u]),
                       ('block', [u, u] + ptrs)]:
        fn = getattr(lib, 'live_memory_' + name)
        fn.argtypes = args
        fn.restype = None if name == 'clear' else C.c_int

    def direct(dll, patch, event=0):
        p, l = pcm(), levels()
        dll.live_block(*patch, 48, 113, event, p, l)
        return bytes(p), tuple(l)

    def memory(op, value):
        p, l = pcm(), levels()
        assert lib.live_memory_block(op, value, p, l) == 1
        return bytes(p), tuple(l)

    def reject(op, value):
        p, l = pcm(*([1234]*1200)), levels(*([987]*6))
        assert lib.live_memory_block(op, value, p, l) == 0
        assert all(x == 1234 for x in p) and all(x == 987 for x in l)

    def interp(a, b, q):
        # Independent integer rounding oracle using quotient/remainder.
        def mix(x, y):
            k, r = divmod(x*(127-q) + y*q, 127)
            return k + (r >= 64)
        return (a[0] if q < 64 else b[0], *(mix(x, y) for x,y in zip(a[1:],b[1:])))

    checks = sounding = silences = 0
    for i in range(4):
        for j in range(4):
            a, b = (i, 104, 0, 127), (j, 19, 7, 13)
            positions = [0, 1, 31, 63, 64, 95, 126, 127, 95, 64, 63, 0]
            old.live_reset()
            expected = [direct(old, a, 1)]
            last = a
            for q in positions:
                expected.append(direct(old, last, 1))
                expected.append(direct(old, interp(a,b,q)))
                last = interp(a,b,q)
            expected += [direct(old, b), direct(old, a), direct(old, a, 2)]
            old.live_panic()
            expected.append(direct(old, b))
            old.live_reset()
            expected.append(direct(old, a))

            lib.live_memory_clear()
            lib.live_reset()
            reject(0,0)
            reject(1,64)
            got = [direct(lib, a, 1)]
            assert lib.live_memory_capture(0) == 1
            assert lib.live_memory_store(1,*b) == 1
            assert lib.live_memory_store(1,4,0,0,0) == 0
            assert lib.live_memory_store(1,*b[:3],128) == 0
            assert lib.live_memory_capture(2) == 0
            last = a
            for q in positions:
                got.append(direct(lib, last, 1))
                reject(1,128)
                reject(2,q)
                assert lib.live_memory_block(1,q,None,None) == 0
                got.append(memory(1,q))
                last = interp(a,b,q)
            got += [memory(0,1), memory(0,0), direct(lib,a,2)]
            lib.live_panic()
            got.append(memory(0,1))
            assert got[-1] == (bytes(2400), (0,)*6)
            silences += 1
            lib.live_reset()
            got.append(memory(0,0))
            lib.live_memory_clear()
            reject(0,0)
            reject(1,0)
            assert got == expected, (i,j)
            checks += len(got)
            sounding += sum(any(p) for p,_ in got)
    assert sounding > 0
    print(f'{checks} PCM/modal blocks; {sounding} sounding; {silences} panic silences; 16 ordered material pairs PASS')


if __name__ == '__main__':
    main()
