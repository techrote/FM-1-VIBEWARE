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
if(typeof module!=='undefined')module.exports=GestureQueue;
