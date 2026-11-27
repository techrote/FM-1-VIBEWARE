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
            assert not errors,errors
            print("Chromium actual native PCM scheduling, visual clocks, live controls, pause/resume, panic and reconnect PASS",page.evaluate("window.witness"))
            browser.close()
    finally:
        s.shutdown();t.join()
