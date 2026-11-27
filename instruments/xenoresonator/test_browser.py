"""Actual Chromium Web Audio graph, rendered modal state and gesture ownership."""
import base64
import pathlib
import subprocess
import sys
from playwright.sync_api import sync_playwright

ROOT = pathlib.Path(__file__).resolve().parent
TAP = """(() => {
  const original=AudioBufferSourceNode.prototype.connect;
  const taps=new WeakMap();
  const probe=window.xenoProbe={peak:0,bodyA:0,bodyB:0,rms:0};
  AudioBufferSourceNode.prototype.connect=function(dest,...args){
    if(dest!==this.context.destination)return original.call(this,dest,...args);
    let a=taps.get(this.context);
    if(!a){a=this.context.createAnalyser();a.fftSize=2048;a.connect(dest);
      taps.set(this.context,a);}
    probe.analyser=a;
    original.call(this,a,...args);
    return dest;
  };
  const data=new Float32Array(2048);
  function sample(){
    if(probe.analyser){
      probe.analyser.getFloatTimeDomainData(data);
      probe.rms=Math.sqrt(data.reduce((s,x)=>s+x*x,0)/data.length);
      probe.peak=Math.max(probe.peak,probe.rms);
    }
    const bars=[...document.querySelectorAll('#modes div')].map(
      b=>parseFloat(b.style.height)||0);
    if(bars.length===6){
      probe.bodyA=Math.max(probe.bodyA,...bars.slice(0,3));
      probe.bodyB=Math.max(probe.bodyB,...bars.slice(3));
    }
    requestAnimationFrame(sample);
  }
  requestAnimationFrame(sample);
})()"""

proc = subprocess.Popen(
    [sys.executable, str(ROOT/'live.py'), str(pathlib.Path(sys.argv[1]).resolve()), '--port','0'],
    stdout=subprocess.PIPE, text=True)
try:
    url=proc.stdout.readline().strip()
    assert url.startswith('http://127.0.0.1:'), url
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,args=['--autoplay-policy=no-user-gesture-required'])
        page=browser.new_page()
        page.set_default_timeout(10000)
        errors=[]
        requests=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.on('request',lambda req:requests.append(req.post_data_json)
                if req.url==url+'/block' and req.method=='POST' else None)
        page.add_init_script(TAP)
        page.goto(url)
        def wait(js):
            page.wait_for_function(js,timeout=10000)
        def fresh(coupling):
            page.select_option('#p',value='2')
            page.locator('#c').fill(str(coupling))
            page.locator('#d').fill('0')
            page.evaluate("Object.assign(window.xenoProbe,{peak:0,bodyA:0,bodyB:0})")
            page.click('#start')
            wait("active && seq>=2")
        def gesture(action, event):
            with page.expect_request(lambda req:req.url==url+'/block' and
                    req.method=='POST' and req.post_data_json['event']==event):
                action()
        def silent():
            wait("!active && sources.size===0 && visuals.length===0 && events.length===0 && window.xenoProbe.rms<0.000001")
            assert page.evaluate("[...document.querySelectorAll('#modes div')].every(b=>parseFloat(b.style.height)===0)")
        fresh(90)
        page.locator('#strike').hover()
        gesture(page.mouse.down,1)
        wait("window.xenoProbe.peak>0.0001 && window.xenoProbe.bodyA>0 && window.xenoProbe.bodyB>0")
        coupled=page.evaluate("({rms:window.xenoProbe.peak,a:window.xenoProbe.bodyA,b:window.xenoProbe.bodyB})")
        gesture(page.mouse.up,2)
        xy=page.locator('#xy').bounding_box()
        page.mouse.move(xy['x']+xy['width']*.2,xy['y']+xy['height']*.25)
        page.mouse.down()
        page.mouse.move(xy['x']+xy['width']*.7,xy['y']+xy['height']*.6)
        page.mouse.up()
        assert 85<=int(page.input_value('#e'))<=94
        assert 45<=int(page.input_value('#d'))<=57
        e,d=map(int,(page.input_value('#e'),page.input_value('#d')))
        wait(f"active && seq>=3")
        with page.expect_request(lambda req:req.url==url+'/block' and req.method=='POST'
                and req.post_data_json['e']==e and req.post_data_json['d']==d):
            pass
        page.click('#stop')
        silent()

        fresh(0)
        page.locator('#strike').focus()
        start=len(requests)
        gesture(lambda:page.keyboard.down('Space'),1)
        # The second key cannot retrigger or release the first key's held note.
        page.keyboard.down('Enter')
        page.keyboard.up('Enter')
        page.locator('#strike').hover()
        page.mouse.down()
        page.mouse.up()
        assert page.evaluate("heldKey===' ' && pointer===null")
        wait("window.xenoProbe.peak>0.0001 && window.xenoProbe.bodyA>0")
        assert page.evaluate("window.xenoProbe.bodyB===0")
        assert [q['event'] for q in requests[start:] if q['event']] == [1]
        gesture(lambda:page.keyboard.up('Space'),2)
        # Changing focus releases a keyboard-held note exactly once.
        gesture(lambda:page.keyboard.down('Enter'),1)
        gesture(lambda:page.locator('#p').focus(),2)
        page.keyboard.up('Enter')
        assert page.evaluate("heldKey===null && pointer===null")
        assert [q['event'] for q in requests[start:] if q['event']] == [1,2,1,2]
        assert page.evaluate("visuals.length<=8 && events.length<=8")

        # Chromatic keyboard: actual PCM for all 13 notes plus octave bounds.
        # Keyboard remains monophonic and shares pointer ownership and panic.
        def pitched(key, note):
            with page.expect_response(lambda r:r.url==url+'/block' and
                    r.request.method=='POST' and r.request.post_data_json['event']==1) as witness:
                page.keyboard.down(key)
            r=witness.value
            assert r.ok and r.request.post_data_json['n']==note
            pcm=base64.b64decode(r.json()['pcm'],validate=True)
            assert len(pcm)==2400 and any(pcm)
            assert int(page.input_value('#n'))==note
            return pcm
        page.select_option('#octave',value='48')
        page.locator('#strike').focus()
        start=len(requests)
        tones=[]
        for i,key in enumerate('zsxdcvgbhnjm,'):
            tones.append(pitched(key,48+i))
            if i==0:
                page.keyboard.down('z')  # repeat
                page.keyboard.down('s')  # competing note
                page.keyboard.up('s')
                assert page.evaluate("heldKey==='KeyZ' && pointer===null")
            gesture(lambda:page.keyboard.up(key),2)
        assert len(set(tones))==13
        assert [q['event'] for q in requests[start:] if q['event']]==[1,2]*13
        for octave,key,note in [('36','z',36),('72',',',84)]:
            page.select_option('#octave',value=octave)
            page.locator('#strike').focus()
            pitched(key,note)
            gesture(lambda:page.locator('#p').focus(),2)
            page.keyboard.up(key)
            assert page.evaluate("heldKey===null && pointer===null")
        print('PASS chromatic keyboard: 15 pitch/PCM witnesses, bounds, repeat, competing key and focus release')

        # Fail a real request while the engine is active, then reconnect.
        page.route('**/block',lambda route:route.abort())
        wait("document.querySelector('#status').textContent.startsWith('Connection lost')")
        silent()
        page.unroute('**/block')
        fresh(90)
        page.locator('#strike').hover()
        gesture(page.mouse.down,1)
        wait("window.xenoProbe.peak>0.0001 && window.xenoProbe.bodyB>0")
        gesture(page.mouse.up,2)
        page.click('#stop')
        silent()
        assert not errors,errors
        print('PASS Chromium actual audio, modal coupling, XY, input ownership, panic, fault and reconnect',coupled)
        browser.close()
finally:
    proc.terminate()
    proc.wait(timeout=5)
