// Deterministic execution of the actual page's visual timeline and panic functions.
const assert=require('node:assert/strict'), fs=require('node:fs'), vm=require('node:vm');
const page=fs.readFileSync(__dirname+'/index.html','utf8');
const match=page.match(/<script>\r?\n([\s\S]*?)<\/script>/);
assert.ok(match,'inline performance script missing');
const script=match[1];
const drawLog=[], frames=[];
const ctx=new Proxy({}, {get:()=>()=>{},set:()=>true});
const nodes=new Map();
function getNode(selector){if(!nodes.has(selector))nodes.set(selector,{getContext:()=>ctx,addEventListener(){},setAttribute(){},textContent:''});return nodes.get(selector)}
const sandbox={document:{querySelector:getNode,querySelectorAll:()=>[],addEventListener(){}},window:{addEventListener(){}},requestAnimationFrame:f=>frames.push(f),GestureQueue:require('./gesture.js'),atob:()=>String.fromCharCode(...new Uint8Array(2400)),clearInterval:()=>{},drawLog};
vm.createContext(sandbox);vm.runInContext(script,sandbox);
vm.runInContext('globalThis.originalDraw=draw;draw=d=>drawLog.push(d);audio={currentTime:1};visuals.push({at:1.05,state:1},{at:1.10,state:2})',sandbox);
frames.shift()();assert.deepEqual(drawLog,[]);
vm.runInContext('audio.currentTime=1.07',sandbox);frames.shift()();assert.deepEqual(drawLog,[1]);
vm.runInContext('audio.currentTime=1.2',sandbox);frames.shift()();assert.deepEqual(drawLog,[1,2]);
vm.runInContext('visuals.push({at:1.25,state:3});sources.add({stop(){drawLog.push("stop")}});cancelAudio();audio.currentTime=2',sandbox);
frames.shift()();assert.deepEqual(drawLog,[1,2,'stop']);
assert.equal(vm.runInContext('visuals.length+sources.size',sandbox),0);
console.log('Actual page JS: audio-clock snapshot ordering and panic invalidation PASS (DOM stub, not browser)');

vm.runInContext('g=9;ribbon.setSpeed(2);held=true;for(let i=0;i<7;i++)addSketchPoint(i*10,80);sketchApply.onclick()',sandbox);
assert.equal(vm.runInContext('draft.length',sandbox),7);
assert.equal(vm.runInContext('ribbon.sketch',sandbox),null);
vm.runInContext('sketchUndo.onclick();addSketchPoint(60,80);addSketchPoint(70,80);addSketchPoint(99,99);sketchApply.onclick()',sandbox);
assert.equal(vm.runInContext('draft.length',sandbox),0);
assert.equal(vm.runInContext('ribbon.shape',sandbox),'sketch');
assert.equal(vm.runInContext('held&&ribbon.speed===2&&ribbon.path[7][0]===70',sandbox),true);
vm.runInContext('addSketchPoint(10,10);sketchClear.onclick();clearRibbon();queue.clear()',sandbox);
assert.equal(vm.runInContext('draft.length===0&&ribbon.shape==="ribbon"&&ribbon.speed===0&&!held&&ribbon.sketch[7][0]===70',sandbox),true);
console.log('Actual page JS: bounded sketch draft, incomplete rejection, undo, apply and inert saved sketch after panic PASS (DOM stub)');

vm.runInContext('g=9;ribbon.setSpeed(2);held=true;ribbon.setShape("sketch");sketchExport.onclick();globalThis.savedText=sketchExchange.value;globalThis.oldSketch=ribbon.sketch;globalThis.oldPhase=ribbon.phase;addSketchPoint(12,13);sketchExchange.value="{bad";sketchImport.onclick()',sandbox);
assert.equal(vm.runInContext('draft.length===1&&ribbon.sketch===oldSketch&&held&&ribbon.phase===oldPhase',sandbox),true);
vm.runInContext('sketchExchange.value=GestureQueue.Ribbon.encodeSketch(Array(8).fill([33,77]));sketchImport.onclick()',sandbox);
assert.equal(vm.runInContext('draft.length===8&&draft[0][0]===33&&ribbon.sketch===oldSketch&&held&&ribbon.phase===oldPhase&&queue.length===0',sandbox),true);
vm.runInContext('sketchApply.onclick()',sandbox);
assert.equal(vm.runInContext('ribbon.sketch[0][0]===33&&ribbon.blend===8&&ribbon.phase===oldPhase&&held&&queue.length===2',sandbox),true);
vm.runInContext('clearRibbon();queue.clear();sketchExchange.value=savedText;sketchImport.onclick()',sandbox);
assert.equal(vm.runInContext('!held&&ribbon.speed===0&&ribbon.shape==="ribbon"&&draft.length===8&&queue.length===0',sandbox),true);
console.log('Actual page JS: import is draft-only, malformed import atomic, explicit apply and inert post-panic import PASS (DOM stub)');

// Execute the actual page's native pump in a fresh stubbed DOM/audio context.
const nativeSandbox={...sandbox,document:{querySelector:getNode,querySelectorAll:()=>[],addEventListener(){}},window:{addEventListener(){}},requestAnimationFrame:()=>{},assert};
vm.createContext(nativeSandbox);
vm.runInContext(script+"\nasync function nativeCheck(assert){\n  g=9;queue.clear();clearRibbon();nativeSketch=null;held=true;next=0;\n  audio={currentTime:0,createBuffer(){return {duration:.05,getChannelData(){return new Float32Array(1200)}}},createBufferSource(){return {connect(){},start(){},stop(){}}}};\n  const calls=[],fixture={pcm:\"fixture\",rate:24000,state_source:\"local native core\",phase:[1,2,3],energy:1,env:100,gate:1,preset:0,x:42,y:60,\n      ribbon:{shape:0,speed:2,direction:1,phase:17,carry:1,manual:0,blend:0,x:42,y:60,has_sketch:0}};\n  let releaseAudio;\n  ribbon.block=()=>{throw Error(\"browser clock advanced\")};\n  request=(kind,data)=>{calls.push({kind,data});return kind===\"audio\"?new Promise(resolve=>{releaseAudio=resolve}):Promise.resolve({ok:true})};\n  pump();const firstPending=inFlight;\n  assert.equal(typeof releaseAudio,\"function\");\n  ribbon.setShape(\"crown\");selectNativeShape(\"crown\");ribbon.setDirection(-1);ribbonCommand(\"direction\",{value:-1});\n  releaseAudio(fixture);await firstPending;\n  assert.equal(visuals.length,1);assert.equal(visuals[0].state.localOrbit.shape,\"ribbon\");\n  assert.equal(visuals[0].state.localOrbit.phase,17);assert.equal(visuals[0].state.localOrbit.direction,1);\n  assert.equal(ribbon.shape===\"crown\"&&ribbon.direction===-1,true);\n  for(let i=0;i<4&&inFlight;i++)await inFlight;\n  assert.equal(calls[0].kind===\"audio\"&&calls[1].kind===\"ribbon\"&&calls[1].data.action===\"shape\"&&calls[2].data.action===\"direction\",true);\n  audio.currentTime=.07;pump();const secondPending=inFlight;\n  releaseAudio({...fixture,ribbon:{...fixture.ribbon,shape:1,direction:-1,phase:3}});await secondPending;\n  assert.equal(visuals[1].state.localOrbit.shape,\"crown\");assert.equal(visuals[1].state.localOrbit.direction,-1);assert.equal(ribbon.phase,3);\n  nativeSketch=Array.from({length:8},()=>[10,80]);const captured=captureOrbit({...fixture,ribbon:{...fixture.ribbon,shape:3,has_sketch:1}});nativeSketch[0][0]=99;\n  assert.equal(captured.path[0][0],10);\n  audio.currentTime=.2;pump();const thirdPending=inFlight;cancelAudio();releaseAudio(fixture);await thirdPending;\n  assert.equal(visuals.length+sources.size,0);\n  g=9;audio.currentTime=.3;pump();const badPending=inFlight;releaseAudio({...fixture,ribbon:{...fixture.ribbon,phase:256}});await badPending;\n  assert.equal(g,0);assert.equal(visuals.length+sources.size,0);\n}\n",nativeSandbox);
vm.runInContext('nativeCheck(assert)',nativeSandbox).then(()=>console.log('Native trajectory: serialized controls, actual receipt metadata, delayed panic and malformed receipt PASS (DOM/audio/HTTP stubs)')).catch(err=>{console.error(err);process.exitCode=1});
