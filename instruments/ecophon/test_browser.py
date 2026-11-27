"""Actual Chromium Web Audio graph and local native HTTP integration."""
import sys
import threading
from pathlib import Path
from playwright.sync_api import sync_playwright
from live import make_server
from feedback import regulate

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
            box=page.locator("#xy").bounding_box()
            page.mouse.move(box["x"]+box["width"]*0.1,box["y"]+box["height"]*0.9)
            page.mouse.down()
            page.mouse.move(box["x"]+box["width"]*0.2,box["y"]+box["height"]*0.8)
            page.mouse.up()
            assert 40<=int(page.input_value("#fertility"))<=65
            assert 190<=int(page.input_value("#pressure"))<=215
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
                const original=post;
                post=async(path,data)=>{
                    const result=await original(path,data);
                    if(path==='/step'){
                        window.ecoWitness.push({controls:[data.fertility,data.sharing,data.pressure,data.frozen],
                            living:result.agents.reduce((n,a)=>n+(a.alive?1:0),0),ticks:result.ticks});
                        if(window.ecoWitness.length>32)window.ecoWitness.shift();
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
            page.locator("#fertility").focus()
            page.keyboard.press("Home")
            assert not page.is_checked("#feedback")
            page.wait_for_function("window.ecoWitness.slice(-2).every(r=>r.controls[0]===0)")
            page.check("#feedback")
            page.check("#frozen")
            assert not page.is_checked("#feedback") and page.is_disabled("#feedback")
            page.wait_for_function("window.ecoWitness.slice(-2).every(r=>r.controls[3]===1)")
            page.uncheck("#frozen")
            assert not page.is_disabled("#feedback")
            page.check("#feedback")
            page.click("#stop")
            assert not page.is_checked("#feedback") and page.is_disabled("#feedback")
            page.wait_for_function("window.ecoRms()<0.000001")
            page.click("#start")
            page.wait_for_function("window.ecoRms()>0.001")
            assert not page.is_checked("#feedback")
            page.click("#stop")
            assert not errors,errors
            browser.close()
            print("PASS Chromium native audio graph, XY gesture, regime reset, panic, fault, reconnect and actual-state population feedback/manual override")
    finally:
        server.shutdown()
        worker.join()
