"""Actual Chromium Web Audio graph and local native HTTP integration."""
import sys
import threading
from pathlib import Path
from playwright.sync_api import sync_playwright
from live import make_server
from feedback import regulate
from performance import BASE, ramp, controls

# Insert a measurement tap into the real output graph, without replacing audio.
TAP = """(() => {
 const original=AudioContext.prototype.createGain;
 AudioContext.prototype.createGain=function(){
   const node=original.call(this), analyser=this.createAnalyser();
   analyser.fftSize=2048;
   const connect=node.connect.bind(node);
   analyser.connect(this.destination);
   node.connect=function(dest,...args){
     if(dest===this.context.destination){connect(analyser,...args);return dest;}
     return connect(dest,...args);
   };
   window.ecoTap={context:this, analyser};
   return node;
 };
 window.ecoRms=()=>{
   if(!window.ecoTap)return 0;
   const a=new Float32Array(window.ecoTap.analyser.fftSize);
   window.ecoTap.analyser.getFloatTimeDomainData(a);
   return Math.sqrt(a.reduce((s,x)=>s+x*x,0)/a.length);
 };
})()"""

def drag_xy(page):
    surface=page.locator("#xy")
    surface.scroll_into_view_if_needed()
    box=surface.bounding_box()
    assert box is not None
    x0,y0=box["x"]+box["width"]*0.1,box["y"]+box["height"]*0.9
    x1,y1=box["x"]+box["width"]*0.2,box["y"]+box["height"]*0.8
    assert page.evaluate("([x,y])=>document.elementFromPoint(x,y)?.closest('#xy')!==null && !!document.elementFromPoint(x,y)?.closest('#xy')", [x0,y0]), (box,page.viewport_size)
    page.mouse.move(x0,y0)
    page.mouse.down()
    page.mouse.move(x1,y1)
    page.mouse.up()
    f,p=int(page.input_value("#fertility")),int(page.input_value("#pressure"))
    print("XY witness",page.viewport_size,box,f,p,flush=True)
    assert 40<=f<=65
    assert 190<=p<=215
    return f,p


with make_server(Path(sys.argv[1]),0) as server:
    worker=threading.Thread(target=server.serve_forever,daemon=True)
    worker.start()
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True,args=["--autoplay-policy=no-user-gesture-required"])
            page=browser.new_page()
            errors=[]
            page.on("pageerror",lambda error:errors.append(str(error)))
            page.add_init_script(TAP)
            page.goto(f"http://127.0.0.1:{server.server_address[1]}/")
            page.click("#start")
            page.wait_for_function("window.ecoRms()>0.001 && document.querySelector('#stats').textContent.includes('Ticks')",timeout=10000)
            before=page.locator("#stats").inner_text()
            drag_xy(page)
            page.wait_for_function("old=>document.querySelector('#stats').textContent!==old && +document.querySelector('#stats').dataset.pressure>=190 && +document.querySelector('#stats').dataset.fertility<=65",arg=before)
            assert page.evaluate("visuals.length<=MAX_VISUALS")
            page.select_option("#preset",index=2)
            assert "next reset" in page.locator("#status").inner_text()
            assert int(page.input_value("#fertility"))<65
            page.click("#start")
            page.wait_for_function("window.ecoRms()>0.001 && document.querySelector('#stats').textContent.includes('Ticks')")
            assert page.input_value("#fertility")=="230"
            assert page.locator("#stats").get_attribute("data-regime")=="2"
            page.click("#stop")
            page.wait_for_function("window.ecoRms()<0.000001")
            assert page.locator("#stats").inner_text()==""
            page.wait_for_timeout(400)
            assert page.locator("#stats").inner_text()==""
            page.click("#start")
            page.wait_for_function("window.ecoRms()>0.001")
            page.route("**/step",lambda route:route.abort())
            page.wait_for_function("document.querySelector('#status').textContent.startsWith('Stopped:')")
            page.wait_for_function("window.ecoRms()<0.000001")
            page.unroute("**/step")
            page.click("#start")
            page.wait_for_function("window.ecoRms()>0.001")
            # Record actual native step requests/responses without replacing the core.
            page.evaluate("""() => {
                window.ecoWitness=[];
                const original=post, originalControls=stepControls;
                let arcBlock=null;
                stepControls=()=>{
                    arcBlock=cue?.id==="cueArc"?cue.block+1:null;
                    return originalControls();
                };
                post=async(path,data)=>{
                    const block=path==='/step'?arcBlock:null;
                    const memory=path==='/memory/step'&&nativeRecall?.slot==="A"?nativeRecall.block+1:null;
                    const result=await original(path,data);
                    if(path==='/step'||path==='/memory/step'){
                        window.ecoWitness.push({path,controls:path==='/step'?[data.fertility,data.sharing,data.pressure,data.frozen]:[...result.controls,result.frozen],
                            living:result.agents.reduce((n,a)=>n+(a.alive?1:0),0),ticks:result.ticks,echo:[...result.controls,result.frozen],generation:result.generation,arcBlock:block,memoryBlock:memory});
                        if(window.ecoWitness.length>256)window.ecoWitness.shift();
                    }
                    return result;
                };
            }""")
            page.locator("#goal").focus()
            page.keyboard.press("Home")
            assert page.input_value("#goal")=="1"
            page.check("#feedback")
            page.wait_for_function("window.ecoWitness.length>=9")
            rows=page.evaluate("window.ecoWitness.slice()")
            for prev,row in zip(rows[-6:-1],rows[-5:]):
                assert row["ticks"]==prev["ticks"]+10
                assert row["controls"]==list(regulate(tuple(prev["controls"]),prev["living"],1)),(prev,row)
            assert any(r["controls"]!=rows[0]["controls"] for r in rows[2:])
            # A compact viewport must still admit a real pointer gesture. XY must
            # cancel the regulator and the actual native request must keep the
            # manual values for subsequent blocks, not just update the DOM.
            page.set_viewport_size({"width":390,"height":640})
            assert page.is_checked("#feedback")
            f,pressure=drag_xy(page)
            assert not page.is_checked("#feedback")
            page.wait_for_function("([f,p])=>window.ecoWitness.length>=2 && window.ecoWitness.slice(-2).every(r=>r.controls[0]===f && r.controls[2]===p)",arg=[f,pressure])
            page.set_viewport_size({"width":1280,"height":720})
            page.check("#feedback")
            page.locator("#fertility").focus()
            page.keyboard.press("Home")
            assert not page.is_checked("#feedback")
            page.wait_for_function("window.ecoWitness.length>=2 && window.ecoWitness.slice(-2).every(r=>r.controls[0]===0)")
            page.check("#feedback")
            page.check("#frozen")
            assert not page.is_checked("#feedback") and page.is_disabled("#feedback")
            page.wait_for_function("window.ecoWitness.length>=2 && window.ecoWitness.slice(-2).every(r=>r.controls[3]===1)")
            page.uncheck("#frozen")
            assert not page.is_disabled("#feedback")
            # Live score cues use the original Habitat Arc endpoints, not reset.
            page.click("#cueBase")
            page.wait_for_function("window.ecoWitness.slice(-2).length===2 && window.ecoWitness.slice(-2).every(r=>r.controls.join(',')==='180,200,40,0')")
            page.evaluate("window.ecoWitness=[]")
            page.click("#cueDrought")
            page.wait_for_function("window.ecoWitness.some(r=>r.controls[0]<180 && r.controls[2]>40)")
            first=page.evaluate("window.ecoWitness.filter(r=>r.controls[0]<180)[0]")
            assert first["controls"]==[175,195,45,0],first
            page.wait_for_function("window.ecoWitness.slice(-2).length===2 && window.ecoWitness.slice(-2).every(r=>r.controls.join(',')==='0,0,255,0')")
            rows=page.evaluate("window.ecoWitness.slice()")
            assert all(r["echo"]==r["controls"] and r["generation"]==first["generation"] for r in rows)
            assert all(b["ticks"]==a["ticks"]+10 for a,b in zip(rows,rows[1:]))
            assert rows[-1]["ticks"]>=first["ticks"]+390
            page.click("#cueRecovery")
            page.wait_for_function("window.ecoWitness.slice(-1)[0].controls[0]>0")
            page.locator("#sharing").focus()
            page.keyboard.press("End")
            assert "Manual" in page.locator("#cueStatus").inner_text()
            held=[int(page.input_value("#"+n)) for n in ("fertility","sharing","pressure")]+[0]
            page.wait_for_function("v=>window.ecoWitness.slice(-2).length===2 && window.ecoWitness.slice(-2).every(r=>r.controls.join(',')===v.join(','))",arg=held)
            page.click("#cueRecovery")
            page.check("#feedback")
            assert "Manual" in page.locator("#cueStatus").inner_text()
            page.locator("#seed").focus()
            page.keyboard.press("Escape")
            assert not page.is_checked("#feedback") and page.is_disabled("#feedback")
            assert page.is_disabled("#cueRecovery")
            page.wait_for_function("window.ecoRms()<0.000001")
            page.click("#start")
            page.wait_for_function("window.ecoRms()>0.001")
            assert not page.is_checked("#feedback")
            # Whole-score performance starts from the actual current controls,
            # matches the authored score after the entry ramp and never resets.
            origin=tuple(page.evaluate("names.map(n=>+$(n).value)"))
            page.evaluate("window.ecoWitness=[]")
            page.click("#cueArc")
            page.wait_for_function("window.ecoWitness.some(r=>r.arcBlock===240)",timeout=60000)
            rows=page.evaluate("window.ecoWitness.filter(r=>r.arcBlock!==null)")
            assert [r["arcBlock"] for r in rows]==list(range(1,241))
            for i,row in enumerate(rows,1):
                expected=(*ramp(origin,BASE,i,40),0) if i<=40 else controls(i-1,"habitat-arc")
                assert row["controls"]==row["echo"]==list(expected),(i,row,expected)
                assert row["generation"]==rows[0]["generation"]
                assert row["ticks"]==rows[0]["ticks"]+(i-1)*10
            assert "240/240 complete" in page.locator("#cueStatus").inner_text()
            page.evaluate("window.ecoWitness=[]")
            page.click("#cueArc")
            page.wait_for_function("window.ecoWitness.some(r=>r.arcBlock===3)")
            page.locator("#sharing").focus()
            page.keyboard.press("Home")
            assert "Manual" in page.locator("#cueStatus").inner_text()
            page.wait_for_function("window.ecoWitness.slice(-2).length===2 && window.ecoWitness.slice(-2).every(r=>r.arcBlock===null && r.controls[1]===0)")
            # User environment memory: two independent slots, exact native
            # ramp, snapshot isolation during capture, no habitat reset.
            def set_environment(keys):
                for name,key in zip(("fertility","sharing","pressure"),keys):
                    page.locator("#"+name).focus()
                    page.keyboard.press(key)
            set_environment(("Home","End","Home"))
            page.wait_for_function("window.ecoWitness.slice(-1)[0].echo.join(',')==='0,255,0,0'")
            page.click("#storeA")
            page.wait_for_function("document.querySelector('#memoryA').textContent==='F 0 / S 255 / P 0'")
            set_environment(("End","Home","End"))
            page.wait_for_function("window.ecoWitness.slice(-1)[0].echo.join(',')==='255,0,255,0'")
            page.click("#storeB")
            page.wait_for_function("document.querySelector('#memoryB').textContent==='F 255 / S 0 / P 255'")
            page.evaluate("window.ecoWitness=[]")
            page.click("#recallA")
            page.wait_for_function("window.ecoWitness.some(r=>r.memoryBlock===3)")
            page.click("#storeA") # must not change already-running recall target
            page.wait_for_function("window.ecoWitness.some(r=>r.memoryBlock===40)",timeout=15000)
            recalled=page.evaluate("window.ecoWitness.filter(r=>r.memoryBlock!==null)")
            assert [r["memoryBlock"] for r in recalled]==list(range(1,41))
            for i,row in enumerate(recalled,1):
                assert row["path"]=="/memory/step" and row["echo"]==[*ramp((255,0,255),(0,255,0),i,40),0],(i,row)
                assert row["generation"]==recalled[0]["generation"]
                assert row["ticks"]==recalled[0]["ticks"]+(i-1)*10
            assert "40/40 complete" in page.locator("#cueStatus").inner_text()
            assert "F 255 / S 0 / P 255" in page.locator("#memoryB").inner_text()
            assert page.locator("#memoryA").inner_text()!="F 0 / S 255 / P 0"
            page.click("#recallB")
            page.wait_for_function("nativeRecall?.slot==='B' && nativeRecall.block>=2")
            page.locator("#sharing").focus()
            page.keyboard.press("Home")
            page.wait_for_function("window.ecoWitness.slice(-2).length===2 && window.ecoWitness.slice(-2).every(r=>r.path==='/step' && r.echo[1]===0)")
            assert "Manual" in page.locator("#cueStatus").inner_text()
            page.click("#recallB")
            page.check("#frozen")
            assert page.is_disabled("#recallA") and page.is_disabled("#recallB")
            assert "Manual" in page.locator("#cueStatus").inner_text()
            page.uncheck("#frozen")
            page.wait_for_function("!document.querySelector('#recallA').disabled")
            page.click("#stop")
            page.wait_for_function("window.ecoRms()<0.000001")
            assert page.is_disabled("#recallA") and page.is_disabled("#recallB")
            assert page.is_disabled("#cueArc")
            remembered=page.locator("#memoryA").inner_text()
            page.reload()
            page.click("#start")
            page.wait_for_function("window.ecoRms()>0.001")
            assert page.locator("#memoryA").inner_text()==remembered
            assert page.locator("#memoryB").inner_text()=="F 255 / S 0 / P 255"
            page.click("#stop")
            page.wait_for_function("window.ecoRms()<0.000001")
            assert not errors,errors
            browser.close()
            print("PASS Chromium native audio graph, XY gesture, regime reset, panic, fault, reconnect and actual-state population feedback/manual override and whole Habitat Arc 240-block playback")
    finally:
        server.shutdown()
        worker.join()
