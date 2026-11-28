const assert=require('node:assert/strict');
const fs=require('node:fs');
const R=require('./gesture.js').Ribbon;
const rows=[];
const sketch=[[0,127],[127,0],[30,40],[50,60],[10,20],[70,90],[100,110],[127,127]];
for(let preset=0;preset<3;preset++){
  const r=new R();r.setSketch(sketch);r.setSpeed(2);
  for(let k=0;k<320;k++){
    if(k===40)r.setDirection(-1);
    if(k===60)r.setShape('crown');
    if(k===80)r.take(60,40);
    if(k===90)r.resume();
    if(k===110)r.setDirection(1);
    if(k===120){r.setShape('pendulum');r.setSpeed(4);}
    if(k===160)r.setShape('sketch');
    if(k===180){r.setSketch(sketch);r.setSpeed(1);}
    if(k===300)r.reset();
    r.block();
    rows.push([preset,k,r.phase,r.carry,r.x,r.y,+r.manual,r.blend,['ribbon','crown','pendulum','sketch'].indexOf(r.shape),r.direction].join(','));
  }
}
assert.equal(fs.readFileSync(process.argv[2],'utf8').replace(/\r\n/g,'\n'),rows.join('\n')+'\n');
console.log(`PASS: ${rows.length} native/browser clock-state rows exactly equal`);
