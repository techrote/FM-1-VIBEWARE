class GestureQueue {
  constructor(limit=16){this.limit=limit;this.items=[];this.highWater=0;this.overflows=0;}
  clear(){this.items.length=0;}
  panic(){this.clear();this.items.push([4,0,0]);}
  push(op,a=0,b=0){
    if(op===4){this.panic();return true;}
    const last=this.items[this.items.length-1];
    if(op===1&&last&&last[0]===1){this.items[this.items.length-1]=[op,a,b];return true;}
    if(this.items.length>=this.limit){this.overflows++;this.panic();return false;}
    this.items.push([op,a,b]);this.highWater=Math.max(this.highWater,this.items.length);return true;
  }
  shift(){return this.items.shift();}
  get length(){return this.items.length;}
}
class OrbitRibbon {
  static path=[[24,18],[48,48],[84,110],[108,76],[72,26],[36,98],[12,120],[36,46]];
  // Local musical shapes, not a new device command. All share the 256-tick cycle.
  static shapes=Object.freeze({
    ribbon:OrbitRibbon.path,
    crown:[[24,96],[44,104],[66,112],[88,120],[104,112],[88,104],[66,96],[44,104]],
    pendulum:[[32,24],[48,30],[80,42],[96,48],[80,42],[48,30],[32,24],[24,30]]
  });
  get path(){return this.shape==='sketch'?this.sketch:OrbitRibbon.shapes[this.shape];}
  // Eight performer-authored points, copied and frozen. Edits are atomic.
  setSketch(points){
    if(!Array.isArray(points)||points.length!==8)throw RangeError('sketch points');
    const copy=[];
    for(const point of points){
      if(!Array.isArray(point)||point.length!==2||!Number.isInteger(point[0])||!Number.isInteger(point[1])||point[0]<0||point[0]>127||point[1]<0||point[1]>127)throw RangeError('sketch XY');
      copy.push(Object.freeze([point[0],point[1]]));
    }
    this.sketch=Object.freeze(copy);
    if(this.shape==='sketch'&&this.speed&&!this.manual)this.beginBlend();
  }
  setShape(shape){
    if(!(shape==='sketch'?this.sketch:Object.hasOwn(OrbitRibbon.shapes,shape)))throw RangeError('ribbon shape');
    if(this.shape===shape)return;
    this.shape=shape;
    if(this.speed&&!this.manual)this.beginBlend();
  }
  beginBlend(){this.blend=8;this.fromX=this.x;this.fromY=this.y;}
  constructor(){this.sketch=null;this.reset();}
  reset(){this.shape='ribbon';this.speed=0;this.phase=0;this.carry=0;this.manual=false;this.blend=0;this.x=24;this.y=18;this.fromX=24;this.fromY=18;}
  setSpeed(speed){if(![1,2,4].includes(speed))throw RangeError('ribbon speed');this.speed=speed;}
  take(x,y){if(![x,y].every(v=>Number.isInteger(v)&&v>=0&&v<=127))throw RangeError('ribbon XY');this.manual=true;this.blend=0;this.x=x;this.y=y;}
  resume(){if(this.manual){this.manual=false;this.beginBlend();}}
  tick(){const i=this.phase>>5,k=this.phase%32,p=this.path[i],q=this.path[(i+1)%8];
    const lerp=(a,b,n,d)=>Math.floor((a*(d-n)+b*n+d/2)/d);
    const x=lerp(p[0],q[0],k,32),y=lerp(p[1],q[1],k,32);
    if(!this.manual){if(this.blend){const n=9-this.blend;this.x=lerp(this.fromX,x,n,8);this.y=lerp(this.fromY,y,n,8);this.blend--;}else{this.x=x;this.y=y;}}
    this.phase=(this.phase+this.speed)%256;
  }
  // The existing native host renders 1200 frames at 24 kHz. Advance
  // exactly 2.5 of the reference 50 Hz ticks per block, alternating 2/3.
  block(){if(!this.speed)return null;this.carry+=5;while(this.carry>=2){this.tick();this.carry-=2;}return this.manual?null:[this.x,this.y];}
}
GestureQueue.Ribbon=OrbitRibbon;
if(typeof module!=='undefined')module.exports=GestureQueue;
