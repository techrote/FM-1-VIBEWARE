"""Actual native local endpoint against independent direct-event controls."""
import base64
import ctypes as C
import hashlib
import json
import sys
from host import Engine, Session

PATHS = (
    ((24,18),(48,48),(84,110),(108,76),(72,26),(36,98),(12,120),(36,46)),
    ((24,96),(44,104),(66,112),(88,120),(104,112),(88,104),(66,96),(44,104)),
    ((32,24),(48,30),(80,42),(96,48),(80,42),(48,30),(32,24),(24,30)),
    ((0,127),(127,0),(30,40),(50,60),(10,20),(70,90),(100,110),(127,127)),
)

def reject(fn):
    try:fn()
    except ValueError:return
    raise AssertionError('invalid request accepted')

def run(path):
    clock=[0.0];e=Engine(path,clock=lambda:clock[0]);l=e.lib
    direct=Session();p=C.byref(direct);l.os_init(p);h=l.os_connect(p,1)
    total=sounding=0;digest=hashlib.sha256()
    for preset in range(3):
        g=e.handle(dict(kind='connect',version=1))['generation']
        def call(kind,**kw):return e.handle(dict(kind=kind,generation=g,**kw))
        def cmd(action,**kw):return call('ribbon',action=action,**kw)['ribbon']
        def event(op,a=0,b=0):
            call('event',op=op,a=a,b=b);assert l.os_event(p,h,op,a,b)
        def state():return cmd('state')
        def compare():
            nonlocal total,sounding
            out=call('audio');buf=(C.c_int16*1200)();l.os_render(p,buf,1200)
            pcm=base64.b64decode(out['pcm']);assert pcm==bytes(buf)
            assert bytes(e.s.core)==bytes(direct.core)
            assert out['ribbon']==state()
            total+=1;sounding+=any(pcm);digest.update(pcm)
            return out
        event(3,preset);event(2,1)
        reject(lambda:cmd('shape',value=3))
        cmd('sketch',points=[list(x) for x in PATHS[3]])
        cmd('speed',value=2)
        shape=0;speed=2;direction=1;phase=carry=0;manual=False;blend=0
        xy=(48,70);origin=xy
        for k in range(320):
            if k==40:cmd('direction',value=-1);direction=-1
            if k==60:cmd('shape',value=1);shape=1;blend=8;origin=xy
            if k==80:event(1,60,40);xy=(60,40);manual=True;blend=0
            if k==90:cmd('resume');manual=False;blend=8;origin=xy
            if k==110:cmd('direction',value=1);direction=1
            if k==120:cmd('shape',value=2);cmd('speed',value=4);shape=2;speed=4;blend=8;origin=xy
            if k==160:cmd('shape',value=3);shape=3;blend=8;origin=xy
            if k==180:cmd('sketch',points=[list(x) for x in PATHS[3]]);cmd('speed',value=1);speed=1;blend=8;origin=xy
            if k==240:cmd('stop');speed=0;manual=False;blend=0
            if k==250:cmd('speed',value=2);speed=2
            if k==300:event(4);shape=0;speed=phase=carry=blend=0;manual=False;direction=1
            before=state();lease=e.deadline
            for action,kw in [('speed',{'value':3}),('shape',{'value':4}),('direction',{'value':True}),('resume',{'value':0}),('sketch',{'points':[[0,128]]*8})]:
                reject(lambda:cmd(action,**kw))
            assert state()==before and e.deadline==lease
            if speed:
                ticks,carry=divmod(carry+5,2)
                for _ in range(ticks):
                    i,n=divmod(phase,32);a,b=PATHS[shape][i],PATHS[shape][(i+1)%8]
                    target=tuple((v*(32-n)+w*n+16)//32 for v,w in zip(a,b))
                    if not manual:
                        if blend:
                            progress=9-blend
                            target=tuple((v*(8-progress)+w*progress+4)//8 for v,w in zip(origin,target));blend-=1
                        xy=target
                    phase=(phase+direction*speed)%256
                if not manual:assert l.os_event(p,h,1,*xy)
            out=compare();r=out['ribbon']
            assert (r['shape'],r['speed'],r['direction'],r['phase'],r['carry'],r['manual'],r['blend'])==(shape,speed,direction,phase,carry,manual,blend)
            assert (r['x'],r['y'])==xy==(out['x'],out['y'])
            if k>=300:assert not any(base64.b64decode(out['pcm']))
        event(2,1);cmd('speed',value=1);assert any(base64.b64decode(call('audio')['pcm']))
        clock[0]+=1.4;lease=e.deadline;cmd('state');assert e.deadline==lease
        clock[0]+=.11;assert e.expire();reject(lambda:call('audio'))
        assert not e.s.core.gate and not e.s.core.env
        new=e.handle(dict(kind='connect',version=1))['generation'];assert new!=g
        reject(lambda:call('ribbon',action='speed',value=4))
        fresh=e.handle(dict(kind='audio',generation=new));assert not any(base64.b64decode(fresh['pcm']))
        assert fresh['ribbon']['speed']==fresh['ribbon']['has_sketch']==0
        e.handle(dict(kind='disconnect',generation=new))
        l.os_disconnect(p);h=l.os_connect(p,1)
    assert total==960 and sounding==900
    print(f'PASS: {total} exact PCM/state blocks; {sounding} sounding; {total-sounding} silent; PCM SHA256 {digest.hexdigest()}')

if __name__=='__main__':run(sys.argv[1])
