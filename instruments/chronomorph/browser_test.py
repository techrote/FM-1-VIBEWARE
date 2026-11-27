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
