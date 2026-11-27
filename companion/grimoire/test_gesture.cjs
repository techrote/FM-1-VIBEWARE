const GestureQueue=require('./gesture.js');
function checkQueue(Q){
  const assert=(c,msg)=>{if(!c)throw Error(msg);};let q=new Q();
  for(let i=0;i<100000;i++)q.push(1,i%128,127-i%128);
  assert(q.length===1,"XY coalescing");assert(q.shift()[1]===31,"latest XY");
  q.push(1,4,5);q.push(2,1);q.push(1,9,10);q.push(2,0);
  assert(JSON.stringify([q.shift(),q.shift(),q.shift(),q.shift()])==="[[1,4,5],[2,1,0],[1,9,10],[2,0,0]]","edge ordering");
  for(let i=0;i<16;i++)assert(q.push(2,i%2),"within bound");
  assert(!q.push(2,1),"overflow must report failure");
  assert(q.length===1&&q.shift()[0]===4&&q.overflows===1&&q.highWater===16,"overflow panic");
  q.push(2,1);q.push(3,1);q.panic();assert(q.length===1&&q.shift()[0]===4,"panic supersedes queued work");
}
checkQueue(GestureQueue);console.log('Gesture fixture: 100000 updates / order / overflow panic PASS');

function checkRibbon(R){
 const check=(b,m)=>{if(!b)throw Error(m);};
 let count=0;
 for(const speed of [1,2,4]){
  const r=new R();r.setSpeed(speed);
  for(let b=0;b<512;b++){const xy=r.block();count++;check(xy.every(v=>Number.isInteger(v)&&v>=0&&v<=127),'bounds');check(r.phase===Math.floor((b+1)*5/2)*speed%256,'sample clock');}
  r.take(127,0);for(let b=0;b<20;b++){check(r.block()===null&&r.x===127&&r.y===0,'manual');}
  r.resume();for(let b=0;b<4;b++)r.block();check(r.blend===0,'blend completed');r.reset();check(r.block()===null&&!r.manual&&r.phase===0,'reset');
 }
 for(const invalid of [0,3,5,NaN]){let rejected=false;try{new R().setSpeed(invalid)}catch{rejected=true}check(rejected,'invalid speed');}
 for(const xy of [[128,0],[0,-1],[1.2,3]]){let rejected=false;try{new R().take(...xy)}catch{rejected=true}check(rejected,'invalid XY');}
 return count;
}
console.log('Orbit Ribbon: '+checkRibbon(GestureQueue.Ribbon)+' sample-clock blocks, manual takeover, blend, reset and input rejection PASS');
