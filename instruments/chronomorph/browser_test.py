"""Headless browser exercise of the real local native audio fixture."""
import pathlib
import sys
import threading
from playwright.sync_api import sync_playwright
from live import Engine,Server,Handler

with Server(("127.0.0.1",0),Handler) as s:
    s.engine=Engine(sys.argv[1])
    t=threading.Thread(target=s.serve_forever,kwargs={"poll_interval":.05},daemon=True)
    t.start()
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True,args=["--autoplay-policy=no-user-gesture-required"])
            page=browser.new_page()
            errors=[]
            page.on("pageerror",lambda e:errors.append(str(e)))
            page.add_init_script("""
                window.witness={starts:0,nonzero:0,stops:0,rate:0};
                const start=AudioBufferSourceNode.prototype.start, stop=AudioBufferSourceNode.prototype.stop;
                AudioBufferSourceNode.prototype.start=function(...args){
                    const w=window.witness;w.starts++;w.rate=this.buffer.sampleRate;
                    if(this.buffer.getChannelData(0).some(x=>x!==0))w.nonzero++;
                    return start.apply(this,args);
                };
                AudioBufferSourceNode.prototype.stop=function(...args){
                    window.witness.stops++;return stop.apply(this,args);
                };
            """)
            page.goto(f"http://127.0.0.1:{s.server_port}/")
            page.get_by_role("button",name="Start / resume",exact=True).click()
            page.wait_for_function("window.witness.nonzero>=4 && document.querySelectorAll('.current').length===3")
            assert page.evaluate("window.witness.rate")==24000
            # Exhaustive native browser JS invariants, including all 16-step masks.
            result=page.evaluate("""() => {
                let rotations=0, spreads=0;
                for(let n=1;n<=16;n++){
                    const limit=(1<<n)-1;
                    for(let m=0;m<=limit;m++){
                        const r=rotatePattern(m,n,1);
                        if(r<0||r>limit||rotatePattern(r,n,-1)!==m)throw Error('rotation');
                        rotations++;
                    }
                    for(let k=0;k<=n;k++){
                        const m=spreadPattern(n,k),p=[];
                        for(let j=0;j<n;j++)if((m>>j)&1)p.push(j);
                        if(m<0||m>limit||p.length!==k)throw Error('density');
                        if(k){const g=p.map((v,i)=>(p[(i+1)%k]-v+n)%n||n);
                            if(Math.max(...g)-Math.min(...g)>1)throw Error('spacing')}
                        spreads++;
                    }
                }
                return [rotations,spreads];
            }""")
            assert result==[131070,152],result
            # Observe real native HTTP responses for mid-performance pattern edits.
            def pattern_response(mask):
                return lambda r: r.url.endswith("/block") and r.status==200 and r.request.post_data_json["patterns"][0]==[7,mask]
            with page.expect_response(pattern_response(19)):
                page.get_by_role("button",name="Bass / master Rotate right",exact=True).click()
            assert page.locator("#lane0 button.on").count()==3
            page.get_by_role("spinbutton",name="Bass / master hits",exact=True).fill("3")
            with page.expect_response(pattern_response(41)):
                page.get_by_role("button",name="Bass / master Spread hits",exact=True).click()
            assert page.locator("#lane0 button.on").count()==3
            # Capture/recall applies a complete control frame to the existing session.
            assert page.get_by_role("button",name="Recall Scene 1",exact=True).is_disabled()
            page.get_by_role("button",name="Save Scene 1",exact=True).click()
            page.locator("#bpm").fill("180")
            page.locator("#warp").fill("-48")
            page.locator("#variation").fill("64")
            with page.expect_response(pattern_response(82)):
                page.get_by_role("button",name="Bass / master Rotate right",exact=True).click()
            page.get_by_role("button",name="Save Scene 2",exact=True).click()
            def scene_response(bpm,warp,variation,mask):
                return lambda r: r.url.endswith("/block") and r.status==200 and all(
                    r.request.post_data_json[k]==v for k,v in dict(
                        bpm=bpm,warp=warp,variation=variation,playing=1,
                        patterns=[[7,mask],[5,21],[11,1321]]).items())
            with page.expect_response(scene_response(112,24,12,41)) as first_scene:
                page.get_by_role("button",name="Recall Scene 1",exact=True).click()
            with page.expect_response(scene_response(180,-48,64,82)) as second_scene:
                page.get_by_role("button",name="Recall Scene 2",exact=True).click()
            a,b=first_scene.value,second_scene.value
            assert a.request.post_data_json["token"]==b.request.post_data_json["token"]
            assert b.json()["seq"]>a.json()["seq"]
            assert all(y[1]>=x[1] for x,y in zip(a.json()["lanes"],b.json()["lanes"]))
            assert page.locator("#sceneStatus").inner_text().startswith("Scene 2 recalled")
            assert page.locator("#lane0 button.on").count()==3
            # Export, alter and restore a scene bank while the real engine runs.
            page.get_by_role("button",name="Export scenes",exact=True).click()
            bank=page.locator("#sceneExchange").input_value()
            import json
            decoded=json.loads(bank)
            assert decoded["version"]==1 and len(decoded["slots"])==4
            assert decoded["slots"][2:]==[None,None]
            page.get_by_role("button",name="Save Scene 1",exact=True).click()
            page.locator("#sceneExchange").fill(bank.replace('"version": 1','"version": 2'))
            page.get_by_role("button",name="Import scenes",exact=True).click()
            assert page.locator("#sceneStatus").inner_text().startswith("Import rejected")
            page.get_by_role("button",name="Export scenes",exact=True).click()
            altered=json.loads(page.locator("#sceneExchange").input_value())
            assert altered["slots"][0]==altered["slots"][1]
            page.locator("#sceneExchange").fill(bank)
            with page.expect_response(scene_response(180,-48,64,82)) as imported:
                page.get_by_role("button",name="Import scenes",exact=True).click()
            assert page.locator("#sceneStatus").inner_text().startswith("Scene bank imported")
            assert page.get_by_role("button",name="Recall Scene 3",exact=True).is_disabled()
            with page.expect_response(scene_response(112,24,12,41)) as restored:
                page.get_by_role("button",name="Recall Scene 1",exact=True).click()
            c,d=imported.value,restored.value
            assert c.request.post_data_json["token"]==d.request.post_data_json["token"]==a.request.post_data_json["token"]
            assert d.json()["seq"]>c.json()["seq"]
            assert all(y[1]>=x[1] for x,y in zip(c.json()["lanes"],d.json()["lanes"]))
            # Factory cues fill only empty slots and do not apply controls.
            page.get_by_role("button",name="Fill empty slots: Lattice Variations",exact=True).click()
            assert "filled 2" in page.locator("#sceneStatus").inner_text()
            page.get_by_role("button",name="Export scenes",exact=True).click()
            filled=json.loads(page.locator("#sceneExchange").input_value())
            assert filled["slots"][:2]==decoded["slots"][:2]
            assert filled["slots"][2]==dict(bpm=84,warp=48,variation=38,patterns=[[9,293],[7,73],[13,4693]])
            assert filled["slots"][3]==dict(bpm=72,warp=-12,variation=4,patterns=[[7,9],[5,4],[11,129]])
            page.get_by_role("button",name="Fill empty slots: Lattice Variations",exact=True).click()
            assert "no scenes changed" in page.locator("#sceneStatus").inner_text()
            # Digits typed in the JSON field are not performance events.
            page.locator("#sceneExchange").focus()
            with page.expect_response(scene_response(112,24,12,41)):
                page.keyboard.press("3")
            # A shortcut outside editing recalls the full scene in the existing session.
            page.locator("h1").click()
            def cue_response(r):
                return r.url.endswith("/block") and r.status==200 and all(
                    r.request.post_data_json[k]==v for k,v in dict(playing=1,**filled["slots"][2]).items())
            with page.expect_response(cue_response) as cue:
                page.keyboard.press("3")
            e=cue.value
            assert e.request.post_data_json["token"]==d.request.post_data_json["token"]
            assert e.json()["seq"]>d.json()["seq"]
            assert all(y[1]>=x[1] for x,y in zip(d.json()["lanes"],e.json()["lanes"]))
            assert page.locator("#sceneStatus").inner_text().startswith("Scene 3 recalled")
            page.get_by_role("button",name="Pause",exact=True).click()
            with page.expect_response(lambda r:r.url.endswith("/block") and r.status==200 and
                    r.request.post_data_json["playing"]==0 and r.request.post_data_json["bpm"]==112):
                page.get_by_role("button",name="Recall Scene 1",exact=True).click()
            page.get_by_role("button",name="Start / resume",exact=True).click()
            page.locator("#warp").fill("-60")
            page.locator("#bpm").fill("220")
            page.locator("#lane0 button").first.click()
            page.wait_for_function("document.querySelector('#status').textContent.includes('Playing')")
            page.get_by_role("button",name="Pause",exact=True).click()
            page.wait_for_function("document.querySelector('#status').textContent.startsWith('Paused')")
            page.wait_for_timeout(180)
            n=page.evaluate("window.witness.nonzero")
            page.wait_for_timeout(200)
            assert page.evaluate("window.witness.nonzero")==n
            page.get_by_role("button",name="Start / resume",exact=True).click()
            page.wait_for_function("n=>window.witness.nonzero>n",arg=n)
            page.get_by_role("button",name="Panic / disconnect",exact=True).click()
            n=page.evaluate("window.witness.starts")
            page.wait_for_timeout(250)
            assert page.evaluate("window.witness.starts")==n
            assert page.locator(".current").count()==0
            page.get_by_role("button",name="Start / resume",exact=True).click()
            page.wait_for_function("n=>window.witness.starts>n",arg=n)
            # Escape is a safety shortcut even when editing the scene JSON.
            page.locator("#sceneExchange").focus()
            page.keyboard.press("Escape")
            n=page.evaluate("window.witness.starts")
            page.wait_for_timeout(250)
            assert page.evaluate("window.witness.starts")==n
            assert page.locator(".current").count()==0
            assert page.locator("#status").inner_text()=="Stopped / disconnected"
            # Manual takeover and full native score playback; no reset of the active session.
            page.get_by_role("button",name="Start / resume",exact=True).click()
            page.wait_for_function("token!==null && playing===1 && seq>2")
            page.get_by_role("button",name="Perform Lattice Variations",exact=True).click()
            page.wait_for_function("score!==null && score.count>=2")
            page.locator("#bpm").fill("156")
            assert "cancelled" in page.locator("#scoreStatus").inner_text()
            page.wait_for_function("score===null")
            requests=[]
            def observe_score(req):
                if req.url.endswith("/block"):
                    requests.append(req.post_data_json)
            page.on("request",observe_score)
            first,active_token=page.evaluate("""() => {
                document.querySelector('#performScore').click();return [seq+1,token]
            }""")
            before=page.evaluate("window.witness.nonzero")
            page.wait_for_function("document.querySelector('#scoreStatus').textContent.startsWith('Score complete')",timeout=45000)
            page.wait_for_function("document.querySelector('#status').textContent.startsWith('Paused')")
            frames=[q for q in requests if q["token"]==active_token and first<=q["seq"]<first+400]
            assert len(frames)==400
            assert [q["seq"] for q in frames]==list(range(first,first+400))
            expected=[
                (112,24,12,[[7,73],[5,21],[11,1321]]),
                (124,-36,25,[[7,19],[5,11],[11,585]]),
                (84,48,38,[[9,293],[7,73],[13,4693]]),
                (72,-12,4,[[7,9],[5,4],[11,129]])]
            for i,q in enumerate(frames):
                assert q["playing"]==1
                assert (q["bpm"],q["warp"],q["variation"],q["patterns"])==expected[i//100]
            assert page.evaluate("token")==active_token
            assert page.evaluate("window.witness.nonzero")>before
            page.wait_for_timeout(250)
            n=page.evaluate("window.witness.nonzero")
            page.wait_for_timeout(200)
            assert page.evaluate("window.witness.nonzero")==n
            # Exhaust every occupancy mask and duration in actual page JS.
            checked=page.evaluate("""() => {
                let frames=0;
                for(let mask=1;mask<16;mask++)for(let seconds=1;seconds<=10;seconds++){
                    const bank=makeSceneBank(),cues=factoryCues(),slots=[];
                    for(let i=0;i<4;i++)if(mask&(1<<i)){bank.save(i,cues[i]);slots.push(i)}
                    const p=makeBankPerformance(bank,seconds);
                    bank.importText(JSON.stringify({format:'chronomorph-scenes',version:1,slots:[null,null,null,null]}));
                    if(p.total!==slots.length*seconds*20)throw Error('duration');
                    for(let i=0;i<p.total;i++){
                        const frame=p.frame(),slot=slots[Math.floor(i/(seconds*20))];
                        if(frame.slot!==slot||frame.first!==(i%(seconds*20)===0)||
                            JSON.stringify(frame.controls)!==JSON.stringify(cues[slot]))throw Error('cue');
                        frame.controls.patterns[0][1]=0;
                        if(p.frame().controls.patterns[0][1]!==cues[slot].patterns[0][1])throw Error('mutable snapshot');
                        if(p.accept()!==i+1)throw Error('cursor');
                        frames++;
                    }
                    if(p.frame()!==null)throw Error('completion');
                }
                return frames;
            }""")
            assert checked==35200
            # Performer-authored score: sparse slots, exact accepted duration,
            # immutable cue snapshot despite edits/import while performing.
            page.get_by_role("button",name="Start / resume",exact=True).click()
            page.wait_for_function("playing===1")
            custom=[dict(bpm=96,warp=15,variation=9,patterns=[[3,5],[8,129],[5,11]]),
                    None,dict(bpm=173,warp=-47,variation=31,patterns=[[16,32769],[7,25],[4,9]]),None]
            def import_bank(slots):
                page.locator("#sceneExchange").fill(json.dumps(dict(format="chronomorph-scenes",version=1,slots=slots)))
                page.get_by_role("button",name="Import scenes",exact=True).click()
                assert page.locator("#sceneStatus").inner_text().startswith("Scene bank imported")
            import_bank([None]*4)
            page.locator("#cueSeconds").fill("1")
            page.locator("#performBank").click()
            assert "rejected" in page.locator("#scoreStatus").inner_text()
            assert page.evaluate("score===null && playing===1")
            import_bank(custom)
            page.locator("#cueSeconds").fill("1.5")
            page.locator("#performBank").click()
            assert "rejected" in page.locator("#scoreStatus").inner_text()
            page.locator("#cueSeconds").fill("2")
            requests.clear()
            first,active_token=page.evaluate("""() => {
                document.querySelector('#performBank').click();return [seq+1,token]
            }""")
            page.wait_for_function("score!==null && score.count>=2")
            before_custom=page.evaluate("window.witness.nonzero")
            import_bank([None]*4)
            page.locator("#cueSeconds").fill("10")
            assert page.evaluate("score!==null && score.total===80")
            page.wait_for_function("document.querySelector('#scoreStatus').textContent.startsWith('Score complete')",timeout=15000)
            page.wait_for_function("document.querySelector('#status').textContent.startsWith('Paused')")
            frames=[q for q in requests if q["token"]==active_token and first<=q["seq"]<first+80]
            assert len(frames)==80
            assert [q["seq"] for q in frames]==list(range(first,first+80))
            for i,q in enumerate(frames):
                assert q["playing"]==1
                assert all(q[k]==v for k,v in custom[0 if i<40 else 2].items())
            assert page.evaluate("window.witness.nonzero")>before_custom
            assert page.evaluate("token")==active_token
            assert page.evaluate("score===null && playing===0")
            page.get_by_role("button",name="Export scenes",exact=True).click()
            assert json.loads(page.locator("#sceneExchange").input_value())["slots"]==[None]*4
            page.get_by_role("button",name="Panic / disconnect",exact=True).click()
            assert not errors,errors
            print("Chromium actual native PCM scheduling, visual clocks, live controls, pause/resume, panic and reconnect PASS",page.evaluate("window.witness"))
            browser.close()
    finally:
        s.shutdown();t.join()
