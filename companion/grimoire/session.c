#include "session.h"
#include <string.h>
void os_init(OrbitSession *s){memset(s,0,sizeof(*s));orbit_reset(&s->core,0);}
void os_disconnect(OrbitSession *s){s->connected=0;orbit_panic(&s->core);}
uint32_t os_connect(OrbitSession *s,unsigned version){
    if(version!=ORBIT_VERSION || s->generation==UINT32_MAX)return 0;
    os_disconnect(s);
    s->generation++;s->connected=1;return s->generation;
}
int os_event(OrbitSession *s,uint32_t generation,unsigned op,unsigned a,unsigned b){
    if(!s->connected||generation!=s->generation)return 0;
    switch(op){
    case ORBIT_XY: if(a>127||b>127)return 0;orbit_xy(&s->core,a,b);break;
    case ORBIT_GATE: if(a>1||b)return 0;orbit_gate(&s->core,a);break;
    case ORBIT_PRESET: if(a>2||b)return 0;orbit_reset(&s->core,a);break;
    case ORBIT_PANIC: if(a||b)return 0;orbit_panic(&s->core);break;
    default:return 0;
    }
    return 1;
}
void os_render(OrbitSession *s,int16_t *out,size_t n){orbit_render(&s->core,out,n);}

/* Instrument-local host bridge; existing OrbitSession ABI remains intact. */
#include "native_ribbon.h"
size_t osr_size(void){return sizeof(GrRibbon);}
void osr_init(GrRibbon *r,const OrbitSession *s){
    gr_init(r,s->connected?s->generation:0);
    r->x=s->core.x;r->y=s->core.y;
}
int osr_command(GrRibbon *r,OrbitSession *s,unsigned op,int value){
    if(!gr_valid(r,s))return 0;
    switch(op){
    case 1:return value>=0&&gr_shape(r,(unsigned)value);
    case 2:return value>=0&&gr_speed(r,(unsigned)value);
    case 3:return gr_direction(r,value);
    case 4:if(value)return 0;gr_resume(r);return 1;
    case 5:if(value)return 0;r->speed=r->manual=r->blend=0;return 1;
    default:return 0;
    }
}
int osr_sketch(GrRibbon *r,OrbitSession *s,const uint8_t points[8][2]){
    return gr_valid(r,s)&&gr_sketch(r,points);
}
int osr_event(GrRibbon *r,OrbitSession *s,unsigned op,unsigned a,unsigned b){
    if(!gr_valid(r,s))return 0;
    if(op==ORBIT_XY&&r->speed)return gr_take(r,s,a,b);
    if(!os_event(s,r->generation,op,a,b))return 0;
    if(op==ORBIT_PANIC||op==ORBIT_PRESET)gr_reset(r);
    r->x=s->core.x;r->y=s->core.y;
    return 1;
}
int osr_render(GrRibbon *r,OrbitSession *s,int16_t *out,size_t n){
    return gr_render(r,s,out,n);
}
void osr_snapshot(const GrRibbon *r,int32_t out[10]){
    out[0]=r->shape;out[1]=r->speed;out[2]=r->direction;out[3]=r->phase;
    out[4]=r->carry;out[5]=r->manual;out[6]=r->blend;out[7]=r->x;
    out[8]=r->y;out[9]=r->has_sketch;
}
