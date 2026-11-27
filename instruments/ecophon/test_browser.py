"""Actual Chromium Web Audio graph and local native HTTP integration."""
import sys
import threading
from pathlib import Path
from playwright.sync_api import sync_playwright
from live import make_server

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
            page.click("#stop")
            assert not errors,errors
            browser.close()
            print("PASS Chromium native audio graph, XY gesture, regime reset, panic, fault and reconnect")
    finally:
        server.shutdown()
        worker.join()
