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

        # Factory patches are single control-frame changes, never note events.
        patches = page.evaluate("JSON.parse(document.querySelector('#patch-data').textContent)")
        assert len(patches)==6
        note,velocity=map(int,(page.input_value('#n'),page.input_value('#v')))
        start=len(requests)
        for patch in patches:
            with page.expect_request(lambda req:req.url==url+'/block' and
                    req.method=='POST' and req.post_data_json['event']==0 and
                    all(req.post_data_json[k]==patch[k] for k in ('p','e','d','c'))):
                page.select_option('#patch',value=patch['id'])
            assert all(int(page.input_value('#'+k))==patch[k] for k in ('p','e','d','c'))
            assert (int(page.input_value('#n')),int(page.input_value('#v')))==(note,velocity)
        assert not any(q['event'] for q in requests[start:])
        page.locator('#e').fill('55')
        assert page.input_value('#patch')==''
        page.select_option('#patch',value='ceramic-chime')
        page.locator('#xy').scroll_into_view_if_needed()
        page.locator('#xy').click(position={'x':20,'y':20})
        assert page.input_value('#patch')==''
        # Real performance keys must not release a held note or steal focus.
        # Ordinary user focus changes still follow the existing blur-release rule.
        page.select_option('#patch',value='ceramic-chime')
        page.select_option('#octave',value='72')
        page.locator('#strike').focus()
        start=len(requests)
        pitched('z',72)
        with page.expect_request(lambda req:req.url==url+'/block' and
                req.method=='POST' and req.post_data_json['event']==0 and
                req.post_data_json['d']==92 and req.post_data_json['c']==12):
            page.evaluate("patchPicker.value='ceramic-click';patchPicker.dispatchEvent(new Event('change'))")
        assert page.evaluate("heldKey==='KeyZ'")
        for i,patch in enumerate(patches,1):
            with page.expect_response(lambda r:r.url==url+'/block' and r.ok and
                    r.request.post_data_json['event']==0 and
                    all(r.request.post_data_json[k]==patch[k] for k in ('p','e','d','c'))) as witness:
                page.keyboard.press(str(i))
            assert len(base64.b64decode(witness.value.json()['pcm'],validate=True))==2400
            assert page.input_value('#patch')==patch['id']
            assert page.evaluate("heldKey==='KeyZ' && document.activeElement===strike")
        # Membrane patch is p=3/e=118/d=9/c=80; make a continuous macro edit.
        for key,k,value in [('ArrowRight','e',122),('ArrowUp','d',13),(']','c',84)]:
            with page.expect_request(lambda req:req.url==url+'/block' and
                    req.method=='POST' and req.post_data_json['event']==0 and
                    req.post_data_json[k]==value):
                page.keyboard.press(key)
            assert int(page.input_value('#'+k))==value
            assert page.input_value('#patch')==''
        # Repeated patch key must not overwrite a subsequent manual adjustment.
        page.keyboard.down('1')
        page.keyboard.press('ArrowRight')
        assert int(page.input_value('#e'))==58
        page.keyboard.down('1')
        page.keyboard.up('1')
        assert int(page.input_value('#e'))==58 and page.input_value('#patch')==''
        # Coalesced macro updates clamp at both bounds, with no queued strikes.
        for key,k,value in [('ArrowRight','e',127),('ArrowDown','d',0),('ArrowLeft','e',0),('ArrowUp','d',127),('[','c',0),(']','c',127)]:
            for _ in range(34):
                page.keyboard.press(key)
            assert int(page.input_value('#'+k))==value
        assert page.evaluate("heldKey==='KeyZ' && pointer===null && events.length<=8")
        gesture(lambda:page.keyboard.up('z'),2)
        assert [q['event'] for q in requests[start:] if q['event']]==[1,2]
        print('PASS factory patches, actual keyboard recall, macro bounds/repeat and no synthetic strike/release')

        # User material exchange never acts as a note event. Import is slot-only.
        def memory_response(action,op,**fields):
            with page.expect_response(lambda r:r.url==url+'/memory-block' and r.ok and
                    r.request.post_data_json.get('op')==op and
                    all(r.request.post_data_json.get(k)==v for k,v in fields.items())) as witness:
                action()
            data=witness.value.json()
            assert len(base64.b64decode(data['pcm'],validate=True))==2400
            return data
        page.locator('summary').click()
        page.click('#user-capture')
        captured=page.input_value('#user-doc')
        assert '"schema":"xenoresonator.material/1"' in captured
        before=page.evaluate("Object.fromEntries(userKeys.map(k=>[k,Number($(k).value)]))")
        doc='{"schema":"xenoresonator.material/1","p":2,"e":93,"d":17,"c":110}'
        page.fill('#user-doc',doc)
        page.click('#user-import')
        assert page.evaluate("Object.fromEntries(userKeys.map(k=>[k,Number($(k).value)]))")==before
        page.fill('#user-doc',doc.replace('"c":110','"c":128'))
        page.click('#user-import')
        assert page.locator('#user-status').inner_text().startswith('Rejected')
        assert page.evaluate("userPatch.c===110")
        page.select_option('#patch',value='ceramic-chime')
        page.locator('#strike').focus()
        start=len(requests)
        pitched('z',72)
        data=memory_response(lambda:page.keyboard.press('7'),'recall',slot=0)
        assert data['patch']==dict(p=2,e=93,d=17,c=110)
        assert any(base64.b64decode(data['pcm'],validate=True))
        wait("$('user-status').textContent==='User material recalled'")
        assert page.evaluate("heldKey==='KeyZ' && document.activeElement===strike")
        assert page.input_value('#patch')==''
        memory_response(lambda:page.keyboard.down('7'),'recall',slot=0)
        wait("$('user-status').textContent==='User material recalled'")
        page.keyboard.press('ArrowRight')
        page.keyboard.down('7')
        page.keyboard.up('7')
        assert page.input_value('#e')=='97'
        gesture(lambda:page.keyboard.up('z'),2)
        assert [q['event'] for q in requests[start:] if q['event']]==[1,2]
        print('PASS user material slot import isolation, invalid rejection, held recall/PCM and repeat')

        # A/B endpoints are local documents; import does not alter controls.
        # A material changes discretely at 64, while macros interpolate.
        page.select_option('#patch',value='ceramic-chime')
        before=page.evaluate("Object.fromEntries(userKeys.map(k=>[k,Number($(k).value)]))")
        page.fill('#user-doc','{"schema":"xenoresonator.material/1","p":0,"e":0,"d":127,"c":0}')
        page.click('#user-import')
        page.fill('#morph-b-doc','{"schema":"xenoresonator.material/1","p":3,"e":127,"d":0,"c":127}')
        page.click('#morph-b-import')
        assert page.evaluate("Object.fromEntries(userKeys.map(k=>[k,Number($(k).value)]))")==before
        assert not page.locator('#morph').is_disabled()
        page.fill('#morph-b-doc','{"schema":"xenoresonator.material/1","p":4,"e":127,"d":0,"c":127}')
        page.click('#morph-b-import')
        assert page.locator('#morph-b-status').inner_text().startswith('Rejected')
        assert page.evaluate("morphB.p===3 && userPatch.p===0")
        data=memory_response(lambda:page.locator('#morph').fill('56'),'morph',position=56)
        assert data['patch']==dict(p=0,e=56,d=71,c=56)
        wait("Number($('p').value)===0 && Number($('e').value)===56")
        page.locator('#strike').focus()
        start=len(requests)
        pitched('z',72)
        def morph_key(key,position,material):
            expected=dict(p=material,e=position,d=127-position,c=position)
            data=memory_response(lambda:page.keyboard.press(key),'morph',position=position)
            assert data['patch']==expected
            wait(f"$('morph-status').textContent.startsWith('Native morph {position}/127')")
            assert page.evaluate("heldKey==='KeyZ' && document.activeElement===strike")
            assert int(page.input_value('#morph'))==position
            assert page.input_value('#patch')==''
        morph_key('9',64,3)
        morph_key('8',56,0)
        morph_key('9',64,3)
        gesture(lambda:page.keyboard.up('z'),2)
        assert [q['event'] for q in requests[start:] if q['event']]==[1,2]
        print('PASS material A/B import isolation, midpoint switch, held keyboard morph and native block response')

        # Delay delivery of an actual native response, then supersede it manually.
        page.evaluate('''() => {
          const orig=window.fetch;
          window.fetch=async (...args)=>{
            const result=await orig(...args);
            if(args[0]==='/memory-block' && !window.delaySeen){
              window.delaySeen=true;
              await new Promise(resolve=>window.releaseMemory=resolve);
            }
            return result;
          };
        }''')
        page.locator('#strike').focus()
        page.keyboard.press('8')
        wait('window.delaySeen && typeof window.releaseMemory==="function"')
        page.keyboard.press('ArrowRight')
        edited=int(page.input_value('#e'))
        assert edited==68
        page.evaluate('window.releaseMemory()')
        with page.expect_request(lambda req:req.url==url+'/block' and req.method=='POST'
                and req.post_data_json['e']==edited):
            pass
        assert int(page.input_value('#e'))==edited
        # Reload retains server-owned slots, without applying them to new controls.
        page.click('#stop')
        silent()
        page.reload()
        page.click('#start')
        wait('active && seq>=2')
        assert page.evaluate('userPatch.p===0 && morphB.p===3')
        assert page.evaluate("Number($('p').value)===0 && Number($('e').value)===76")
        print('PASS native response supersession and server-owned slot reload without recall')

        # Fail a real request while the engine is active, then reconnect.
        page.route('**/block',lambda route:route.abort())
        wait("document.querySelector('#status').textContent.startsWith('Connection lost')")
        silent()
        page.unroute('**/block')
        fresh(90)
        page.locator('#strike').hover()
        gesture(page.mouse.down,1)
        wait("window.xenoProbe.peak>0.0001 && window.xenoProbe.bodyB>0")
        # A native response may be received but never delivered to the pump.
        # This deliberately withholds the real response even after fetch aborts.
        # The request deadline must mute the held note and quarantine the late
        # response, including across a new session.
        old_token=page.evaluate('token')
        page.evaluate('''() => {
          const original=window.fetch;
          window.fetch=async (...args)=>{
            const response=await original(...args);
            if(args[0]==='/block' && !window.releaseStalled){
              await new Promise(resolve=>window.releaseStalled=resolve);
            }
            return response;
          };
        }''')
        wait('typeof window.releaseStalled==="function"')
        with page.expect_response(lambda r:r.url==url+'/panic' and
                r.request.method=='POST' and r.request.post_data_json['token']==old_token) as panic:
            wait("$('status').textContent.includes('Request deadline exceeded')")
        assert (panic.value.status==200 and panic.value.json()['muted'] is True) or (
            panic.value.status==409 and panic.value.json()['error']=='stale session')
        silent()
        assert page.evaluate('pointer===null && heldKey===null && memoryJobs.length===0')
        page.mouse.up()
        stale=page.request.post(url+'/block',data={'token':old_token,'seq':0})
        assert stale.status==409 and stale.json()['error']=='stale session'
        fresh(90)
        assert page.evaluate('token')!=old_token
        current_seq=page.evaluate('seq')
        page.evaluate('window.releaseStalled()')
        wait(f'active && seq>={current_seq+4}')
        wait('window.xenoProbe.rms<0.000001')
        assert page.evaluate('window.xenoProbe.peak<0.000001 && pointer===null && heldKey===null')
        page.locator('#strike').hover()
        gesture(page.mouse.down,1)
        wait("window.xenoProbe.peak>0.0001 && window.xenoProbe.bodyB>0")
        gesture(page.mouse.up,2)
        page.click('#stop')
        silent()
        print('PASS held-note deadline, native panic/stale session, late response quarantine and actual audio recovery')
        assert not errors,errors
        print('PASS Chromium actual audio, modal coupling, XY, input ownership, panic, fault and reconnect',coupled)
        browser.close()
finally:
    proc.terminate()
    proc.wait(timeout=5)
