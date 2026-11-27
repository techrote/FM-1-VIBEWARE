// Deterministic execution of the actual page's visual timeline and panic functions.
const assert=require('node:assert/strict'), fs=require('node:fs'), vm=require('node:vm');
const page=fs.readFileSync(__dirname+'/index.html','utf8');
const match=page.match(/<script>\r?\n([\s\S]*?)<\/script>/);
assert.ok(match,'inline performance script missing');
const script=match[1];
const drawLog=[], frames=[];
const ctx=new Proxy({}, {get:()=>()=>{},set:()=>true});
const node={getContext:()=>ctx,addEventListener(){},setAttribute(){},textContent:''};
const sandbox={document:{querySelector:()=>node,querySelectorAll:()=>[],addEventListener(){}},window:{addEventListener(){}},requestAnimationFrame:f=>frames.push(f),GestureQueue:require('./gesture.js'),drawLog};
vm.createContext(sandbox);vm.runInContext(script,sandbox);
vm.runInContext('draw=d=>drawLog.push(d);audio={currentTime:1};visuals.push({at:1.05,state:1},{at:1.10,state:2})',sandbox);
frames.shift()();assert.deepEqual(drawLog,[]);
vm.runInContext('audio.currentTime=1.07',sandbox);frames.shift()();assert.deepEqual(drawLog,[1]);
vm.runInContext('audio.currentTime=1.2',sandbox);frames.shift()();assert.deepEqual(drawLog,[1,2]);
vm.runInContext('visuals.push({at:1.25,state:3});sources.add({stop(){drawLog.push("stop")}});cancelAudio();audio.currentTime=2',sandbox);
frames.shift()();assert.deepEqual(drawLog,[1,2,'stop']);
assert.equal(vm.runInContext('visuals.length+sources.size',sandbox),0);
console.log('Actual page JS: audio-clock snapshot ordering and panic invalidation PASS (DOM stub, not browser)');
