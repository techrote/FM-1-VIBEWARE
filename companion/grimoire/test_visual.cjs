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
const sandbox={document:{querySelector:getNode,querySelectorAll:()=>[],addEventListener(){}},window:{addEventListener(){}},requestAnimationFrame:f=>frames.push(f),GestureQueue:require('./gesture.js'),atob:()=>'',drawLog};
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
vm.runInContext('addSketchPoint(10,10);sketchClear.onclick();clearRibbon()',sandbox);
assert.equal(vm.runInContext('draft.length===0&&ribbon.shape==="ribbon"&&ribbon.speed===0&&!held&&ribbon.sketch[7][0]===70',sandbox),true);
console.log('Actual page JS: bounded sketch draft, incomplete rejection, undo, apply and inert saved sketch after panic PASS (DOM stub)');

vm.runInContext('g=9;ribbon.setSpeed(2);held=true;ribbon.setShape("sketch");sketchExport.onclick();globalThis.savedText=sketchExchange.value;globalThis.oldSketch=ribbon.sketch;globalThis.oldPhase=ribbon.phase;addSketchPoint(12,13);sketchExchange.value="{bad";sketchImport.onclick()',sandbox);
assert.equal(vm.runInContext('draft.length===1&&ribbon.sketch===oldSketch&&held&&ribbon.phase===oldPhase',sandbox),true);
vm.runInContext('sketchExchange.value=GestureQueue.Ribbon.encodeSketch(Array(8).fill([33,77]));sketchImport.onclick()',sandbox);
assert.equal(vm.runInContext('draft.length===8&&draft[0][0]===33&&ribbon.sketch===oldSketch&&held&&ribbon.phase===oldPhase&&queue.length===0',sandbox),true);
vm.runInContext('sketchApply.onclick()',sandbox);
assert.equal(vm.runInContext('ribbon.sketch[0][0]===33&&ribbon.blend===8&&ribbon.phase===oldPhase&&held&&queue.length===0',sandbox),true);
vm.runInContext('clearRibbon();sketchExchange.value=savedText;sketchImport.onclick()',sandbox);
assert.equal(vm.runInContext('!held&&ribbon.speed===0&&ribbon.shape==="ribbon"&&draft.length===8&&queue.length===0',sandbox),true);
console.log('Actual page JS: import is draft-only, malformed import atomic, explicit apply and inert post-panic import PASS (DOM stub)');

// Exercise the actual asynchronous pump with a deferred event response. The
// audio stub proves timeline metadata, not sound or browser qualification.
async function checkOrbitTimeline(){
  const run=s=>vm.runInContext(s,sandbox);
  run(`g=9;queue.clear();clearRibbon();ribbon.setSpeed(2);held=true;next=0;
    audio={currentTime:0,createBuffer(){return {duration:.05,getChannelData(){return new Float32Array(0)}}},createBufferSource(){return {connect(){},start(){},stop(){}}}};
    globalThis.nativeFixture={pcm:"",rate:24000,phase:[1,2,3],energy:1,env:100,gate:1,preset:0,x:42,y:60};
    request=(kind)=>kind==="event"?new Promise(resolve=>{globalThis.releaseEvent=resolve}):Promise.resolve(nativeFixture);
    pump();globalThis.firstPending=inFlight;globalThis.submittedPhase=ribbon.phase;
    ribbon.setShape("crown");ribbon.setDirection(-1);releaseEvent({})`);
  await run('firstPending');
  assert.equal(run('visuals.length'),1);
  assert.equal(run('visuals[0].state.localOrbit.shape'),'ribbon');
  assert.equal(run('visuals[0].state.localOrbit.direction'),1);
  assert.equal(run('visuals[0].state.localOrbit.phase===submittedPhase'),true);
  assert.equal(run('visuals[0].state.localOrbit.path[0][1]'),18);
  assert.equal(run('visuals[0].state.localOrbit.path!==GestureQueue.Ribbon.path'),true);
  assert.equal(run('visuals[0].state.localOrbit.path[0]!==GestureQueue.Ribbon.path[0]'),true);
  run('originalDraw(visuals[0].state)');
  assert.equal(run('orbitPlayed.textContent.startsWith("Played local orbit: ribbon")'),true);
  run('audio.currentTime=.07;pump();globalThis.secondPending=inFlight;releaseEvent({})');
  await run('secondPending');
  assert.equal(run('visuals.length'),2);
  assert.equal(run('visuals[1].state.localOrbit.shape'),'crown');
  assert.equal(run('visuals[1].state.localOrbit.direction'),-1);
  assert.equal(run('visuals[1].state.localOrbit.path[0][1]'),96);
  run('originalDraw(visuals[1].state)');
  assert.equal(run('orbitPlayed.textContent.startsWith("Played local orbit: crown")'),true);
  assert.equal(run('orbitPlayed.textContent.includes("reverse")'),true);
  run('ribbon.setSketch(Array(8).fill([10,80]));ribbon.setShape("sketch");globalThis.captured=captureOrbit();ribbon.setSketch(Array(8).fill([100,20]))');
  assert.equal(run('captured.path[0][0]'),10);
  assert.equal(run('captured.path[0][1]'),80);
  run('audio.currentTime=.2;pump();globalThis.thirdPending=inFlight;cancelAudio();releaseEvent({})');
  await run('thirdPending');
  assert.equal(run('visuals.length+sources.size'),0);
  assert.equal(run('captureOrbit()'),null);
  assert.equal(run('ribbon.direction'),1);
  assert.equal(run('orbitPlayed.textContent'),'Played local orbit: off');
  console.log('Actual asynchronous page pump: 20 assertions, detached played paths and directions, delayed response, edit and panic invalidation PASS (DOM/audio stub)');
}
checkOrbitTimeline().catch(err=>{console.error(err);process.exitCode=1});
