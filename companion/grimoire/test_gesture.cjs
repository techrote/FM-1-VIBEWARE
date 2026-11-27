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
