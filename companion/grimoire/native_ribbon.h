#ifndef GRIMOIRE_NATIVE_RIBBON_H
#define GRIMOIRE_NATIVE_RIBBON_H
#include "session.h"
#include <string.h>
/* Local controller, not device telemetry or a wire ABI. One owner, one
 * generation, fixed 1200-frame render blocks at the existing 24 kHz rate. */
enum { GR_RIBBON, GR_CROWN, GR_PENDULUM, GR_SKETCH };
enum { GR_BLOCK = 1200 };
typedef struct {
    uint32_t generation;
    uint8_t sketch[8][2];
    uint8_t has_sketch, shape, speed, phase, carry, manual, blend;
    uint8_t x,y,from_x,from_y;
    int8_t direction;
} GrRibbon;
static inline void gr_reset(GrRibbon *r) {
    r->shape=GR_RIBBON;r->speed=0;r->phase=0;r->carry=0;
    r->manual=0;r->blend=0;r->x=r->from_x=24;r->y=r->from_y=18;r->direction=1;
}
static inline void gr_init(GrRibbon *r,uint32_t generation) {
    memset(r,0,sizeof(*r));r->generation=generation;gr_reset(r);
}
static inline int gr_valid(const GrRibbon *r,const OrbitSession *s) {
    return s->connected && r->generation && s->generation==r->generation;
}
static inline void gr_blend(GrRibbon *r) {
    r->blend=8;r->from_x=r->x;r->from_y=r->y;
}
static inline int gr_sketch(GrRibbon *r,const uint8_t points[8][2]) {
    if(!points)return 0;
    for(unsigned i=0;i<8;i++)if(points[i][0]>127||points[i][1]>127)return 0;
    memmove(r->sketch,points,sizeof(r->sketch));r->has_sketch=1;
    if(r->shape==GR_SKETCH&&r->speed&&!r->manual)gr_blend(r);
    return 1;
}
static inline int gr_shape(GrRibbon *r,unsigned shape) {
    if(shape>GR_SKETCH||(shape==GR_SKETCH&&!r->has_sketch))return 0;
    if(shape!=r->shape){r->shape=(uint8_t)shape;if(r->speed&&!r->manual)gr_blend(r);}
    return 1;
}
static inline int gr_speed(GrRibbon *r,unsigned speed) {
    if(speed!=1&&speed!=2&&speed!=4)return 0;
    r->speed=(uint8_t)speed;return 1;
}
static inline int gr_direction(GrRibbon *r,int direction) {
    if(direction!=1&&direction!=-1)return 0;
    r->direction=(int8_t)direction;return 1;
}
static inline int gr_take(GrRibbon *r,OrbitSession *s,unsigned x,unsigned y) {
    if(!gr_valid(r,s)||!os_event(s,r->generation,ORBIT_XY,x,y))return 0;
    r->manual=1;r->blend=0;r->x=(uint8_t)x;r->y=(uint8_t)y;return 1;
}
static inline void gr_resume(GrRibbon *r) {
    if(r->manual){r->manual=0;gr_blend(r);}
}
static inline unsigned gr_lerp(unsigned a,unsigned b,unsigned n,unsigned d) {
    return (a*(d-n)+b*n+d/2)/d;
}
static inline void gr_tick(GrRibbon *r) {
    static const uint8_t shapes[3][8][2]={
        {{24,18},{48,48},{84,110},{108,76},{72,26},{36,98},{12,120},{36,46}},
        {{24,96},{44,104},{66,112},{88,120},{104,112},{88,104},{66,96},{44,104}},
        {{32,24},{48,30},{80,42},{96,48},{80,42},{48,30},{32,24},{24,30}}
    };
    const uint8_t (*path)[2]=r->shape==GR_SKETCH?(const uint8_t (*)[2])r->sketch:shapes[r->shape];
    unsigned i=r->phase>>5,k=r->phase%32,q=(i+1)%8;
    unsigned x=gr_lerp(path[i][0],path[q][0],k,32),y=gr_lerp(path[i][1],path[q][1],k,32);
    if(!r->manual){
        if(r->blend){unsigned n=9-r->blend;x=gr_lerp(r->from_x,x,n,8);y=gr_lerp(r->from_y,y,n,8);r->blend--;}
        r->x=(uint8_t)x;r->y=(uint8_t)y;
    }
    r->phase=(uint8_t)((r->phase+r->direction*(int)r->speed+256)%256);
}
static inline int gr_render(GrRibbon *r,OrbitSession *s,int16_t *out,size_t n) {
    if(!out||n!=GR_BLOCK||!gr_valid(r,s))return 0;
    if(r->speed){
        r->carry+=5;while(r->carry>=2){gr_tick(r);r->carry-=2;}
        if(!r->manual)os_event(s,r->generation,ORBIT_XY,r->x,r->y);
    }
    os_render(s,out,n);return 1;
}
static inline int gr_panic(GrRibbon *r,OrbitSession *s) {
    if(!gr_valid(r,s)||!os_event(s,r->generation,ORBIT_PANIC,0,0))return 0;
    gr_reset(r);return 1;
}
#endif
