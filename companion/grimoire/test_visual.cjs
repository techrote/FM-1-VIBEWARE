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
const sandbox={document:{querySelector:getNode,querySelectorAll:()=>[],addEventListener(){}},window:{addEventListener(){}},requestAnimationFrame:f=>frames.push(f),GestureQueue:require('./gesture.js'),drawLog};
vm.createContext(sandbox);vm.runInContext(script,sandbox);
vm.runInContext('draw=d=>drawLog.push(d);audio={currentTime:1};visuals.push({at:1.05,state:1},{at:1.10,state:2})',sandbox);
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
