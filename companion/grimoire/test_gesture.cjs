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

function checkShapes(R){
  const assert=(c,m)=>{if(!c)throw Error(m);};
  let blocks=0;
  const signatures=new Set();
  for(const shape of ['ribbon','crown','pendulum']){
    for(const speed of [1,2,4]){
      const r=new R(), points=[];r.setShape(shape);r.setSpeed(speed);
      for(let b=0;b<512;b++){
        const [x,y]=r.block();blocks++;
        assert(x>=0&&x<=127&&y>=0&&y<=127,'shape bounds');
        if(shape==='crown')assert(y>=96&&y<=120,'crown register');
        if(shape==='pendulum')assert(y>=24&&y<=48,'pendulum register');
        assert(r.phase===Math.floor((b+1)*5/2)*speed%256,'shape clock');
        points.push([x,y]);
      }
      signatures.add(JSON.stringify(points));
    }
  }
  assert(signatures.size===9,'distinct shape and speed traces');
  const r=new R();r.setSpeed(2);for(let i=0;i<20;i++)r.block();
  const [x,y,phase,carry]=[r.x,r.y,r.phase,r.carry];r.setShape('crown');
  assert(r.blend===8&&r.x===x&&r.y===y&&r.phase===phase&&r.carry===carry,'shape transition preserves clock and starting point');
  for(let i=0;i<4;i++)r.block();assert(r.blend===0&&r.y>=96,'shape blend completion');
  r.take(127,0);r.setShape('pendulum');for(let i=0;i<4;i++)assert(r.block()===null&&r.x===127&&r.y===0,'manual owns XY during shape change');
  r.resume();for(let i=0;i<4;i++)r.block();assert(r.blend===0&&r.y>=24&&r.y<=48,'manual blend resumes selected shape');
  r.reset();assert(r.shape==='ribbon'&&r.speed===0&&r.phase===0&&r.block()===null,'panic reset shape');
  for(const invalid of ['unknown','__proto__','constructor',null,1]){
    let rejected=false;try{r.setShape(invalid)}catch{rejected=true}
    assert(rejected&&r.shape==='ribbon','invalid shape rejected atomically');
  }
  return blocks;
}
console.log('Orbit Ribbon shapes: '+checkShapes(GestureQueue.Ribbon)+' blocks, 9 distinct trajectories, bounded phase-preserving blend and reset PASS');

function checkSketch(R){
  const assert=(c,m)=>{if(!c)throw Error(m)};
  const points=[[8,72],[16,83],[28,91],[40,84],[48,72],[40,77],[28,86],[16,79]];
  const r=new R();r.setSpeed(2);for(let i=0;i<10;i++)r.block();
  const before=[r.phase,r.carry,r.x,r.y];r.setSketch(points);r.setShape('sketch');
  assert(r.blend===8&&before.join() === [r.phase,r.carry,r.x,r.y].join(),'sketch transition continuity');
  points[0][0]=127;assert(r.path[0][0]===8&&Object.isFrozen(r.path[0]),'sketch copies and freezes');
  for(let i=0;i<4;i++)r.block();
  const original=r.sketch;
  for(const bad of [null,[],Array(7).fill([0,0]),Array(9).fill([0,0]),Array(8).fill([0,128]),Array(8).fill([-.5,0]),Array(8).fill(['0',0]),Array(8).fill([0]),Array(8).fill([0,0,0]),Array(8)]){
    let rejected=false;try{r.setSketch(bad)}catch{rejected=true}
    assert(rejected&&r.sketch===original&&r.shape==='sketch','atomic invalid sketch');
  }
  let blocks=0;
  for(const speed of [1,2,4]){
    r.setSpeed(speed);
    for(let i=0;i<512;i++){const [x,y]=r.block();blocks++;assert(x>=8&&x<=48&&y>=72&&y<=91,'sketch path bounds')}
  }
  r.take(127,0);r.setSketch(Array(8).fill([33,66]));assert(r.block()===null&&r.x===127&&r.y===0,'manual priority on edit');
  r.resume();for(let i=0;i<4;i++)r.block();assert(r.x===33&&r.y===66,'resume new sketch');
  r.setSketch(Array(8).fill([0,127]));assert(r.blend===8,'active sketch edit blends');
  for(let i=0;i<4;i++)r.block();assert(r.x===0&&r.y===127,'active edit endpoint');
  r.reset();assert(r.shape==='ribbon'&&r.speed===0&&r.block()===null&&r.sketch[0][1]===127,'panic stops automation, saved sketch is inert');
  const empty=new R();let rejected=false;try{empty.setShape('sketch')}catch{rejected=true}assert(rejected&&empty.shape==='ribbon','unavailable sketch rejected');
  return blocks;
}
console.log('Orbit Ribbon sketches: '+checkSketch(GestureQueue.Ribbon)+' bounded blocks; atomic validation, editing, manual takeover and panic PASS');

// Local JSON exchange is inert until explicitly applied by the performance UI.
function checkExchange(R){
  const assert=(c,m)=>{if(!c)throw Error(m)};
  let cases=0;
  for(let i=0;i<128;i++){
    const points=Array.from({length:8},(_,j)=>[(i+j*19)%128,(127-i+j*11)%128]);
    const doc=R.encodeSketch(points),copy=R.decodeSketch(doc);
    assert(doc.length<=512&&JSON.stringify(copy)===JSON.stringify(points),'round trip');
    assert(Object.isFrozen(copy)&&copy.every(Object.isFrozen),'immutable decoded path');
    const a=new R(),b=new R();a.setSketch(points);b.setSketch(copy);
    a.setShape('sketch');b.setShape('sketch');a.setSpeed(4);b.setSpeed(4);
    for(let k=0;k<128;k++)assert(a.block().join()===b.block().join(),'same performance');
    cases++;
  }
  const good={format:'grimoire.orbit-sketch',version:1,points:Array(8).fill([20,80])};
  for(const bad of [null,{},'','x'.repeat(513),'null','[]','{',JSON.stringify({...good,version:2}),JSON.stringify({...good,format:'other'}),JSON.stringify({...good,gate:1}),JSON.stringify({...good,speed:4}),JSON.stringify({...good,points:Array(8).fill([128,0])}),JSON.stringify({...good,points:Array(9).fill([0,0])}),JSON.stringify({...good,points:Array(8).fill([0,0.5])}),JSON.stringify({...good,points:Array(8).fill(['0',0])})]){
    let rejected=false;try{R.decodeSketch(bad)}catch{rejected=true}assert(rejected,'invalid exchange accepted');cases++;
  }
  return cases;
}
console.log('Orbit Sketch JSON exchange: '+checkExchange(GestureQueue.Ribbon)+' documents, 16384 matching trajectory blocks PASS');

function checkDirection(R){
  const assert=(b,m)=>{if(!b)throw Error(m)};
  let blocks=0;
  for(const shape of ['ribbon','crown','pendulum','sketch'])for(const speed of [1,2,4]){
    const r=new R(),control=new R();
    for(const obj of [r,control]){
      obj.setSketch([[2,12],[9,23],[34,56],[71,94],[126,10],[91,84],[32,7],[14,72]]);
      obj.setShape(shape);obj.setSpeed(speed);
    }
    let divergent=0;
    for(let k=0;k<1024;k++){
      if(k===37||k===702){
        const before=[r.phase,r.carry,r.x,r.y,r.blend,r.manual];
        r.setDirection(k===37?-1:1);
        assert(before.join() === [r.phase,r.carry,r.x,r.y,r.blend,r.manual].join(),'direction must preserve clock and state');
      }
      if(k===200){r.take(127,0);control.take(127,0)}
      if(k===220){r.resume();control.resume()}
      const phase=r.phase,carry=r.carry,direction=r.direction;
      const xy=r.block(),other=control.block();
      const ticks=Math.floor((carry+5)/2);
      assert(r.phase===(phase+direction*speed*ticks+256)%256&&r.carry===(carry+5)%2,'signed clock/carry');
      if(k>=200&&k<220)assert(xy===null&&r.x===127&&r.y===0,'reverse manual priority');
      else {assert(xy.every(v=>Number.isInteger(v)&&v>=0&&v<=127),'reverse bounded XY');if(xy.join()!==other.join())divergent++}
      if(k<37)assert(xy.join()===other.join(),'pre-reversal trajectory');
      blocks++;
    }
    assert(divergent>128,'direction materially changes trajectory');
    for(const bad of [0,2,-2,1.5,'-1',NaN,null]){
      let refused=false;try{r.setDirection(bad)}catch{refused=true}
      assert(refused&&r.direction===1,'invalid direction atomic');
    }
    r.setDirection(-1);r.reset();assert(r.direction===1&&r.phase===0&&r.speed===0&&r.block()===null,'panic restores forward and stops');
  }
  return blocks;
}
console.log('Orbit direction: '+checkDirection(GestureQueue.Ribbon)+' blocks, signed wrap/carry, held-state continuity, manual ownership and reset PASS');
