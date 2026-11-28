#ifndef GRIMOIRE_SAMPLE_RIBBON_H
#define GRIMOIRE_SAMPLE_RIBBON_H
#include "orbit.h"
/* Standalone audio-owner gesture player. Original 8-point Orbit Ribbon
 * geometry and 50 Hz motion, now at exact core-sample boundaries. Not the
 * legacy 1200-frame browser receipt schedule; no session or wire dependency.
 * Caller serializes commands/render, owns gate and output-rate cache. */
enum { GR_SAMPLE_QUANTUM = ORBIT_RATE / 50u, GR_SAMPLE_POINTS = 8 };
typedef struct {
    uint8_t path[GR_SAMPLE_POINTS][2];
    uint16_t remaining;
    uint8_t phase, speed, manual, blend, from_x, from_y;
    int8_t direction;
} GrSampleRibbon;
static inline void grs_cancel(GrSampleRibbon *r) {
    r->remaining=0;r->phase=0;r->speed=0;r->manual=0;r->blend=0;
}
static inline int grs_arm(GrSampleRibbon *r,const uint8_t points[8][2],unsigned speed,int direction) {
    if(!points||(speed!=1&&speed!=2&&speed!=4)||(direction!=1&&direction!=-1))return 0;
    for(unsigned i=0;i<8;i++)if(points[i][0]>127||points[i][1]>127)return 0;
    for(unsigned i=0;i<8;i++)for(unsigned j=0;j<2;j++)r->path[i][j]=points[i][j];
    grs_cancel(r);r->speed=(uint8_t)speed;r->direction=(int8_t)direction;return 1;
}
static inline int grs_motion(GrSampleRibbon *r,unsigned speed,int direction) {
    if(!r->speed||(speed!=1&&speed!=2&&speed!=4)||(direction!=1&&direction!=-1))return 0;
    r->speed=(uint8_t)speed;r->direction=(int8_t)direction;return 1;
}
static inline int grs_take(GrSampleRibbon *r,Orbit *s,unsigned x,unsigned y) {
    if(x>127||y>127)return 0;
    if(r->speed){r->manual=1;r->blend=0;}
    orbit_xy(s,x,y);return 1;
}
static inline void grs_resume(GrSampleRibbon *r,const Orbit *s) {
    if(r->speed&&r->manual){r->manual=0;r->blend=8;r->from_x=s->x;r->from_y=s->y;}
}
static inline void grs_panic(GrSampleRibbon *r,Orbit *s) {grs_cancel(r);orbit_panic(s);}
static inline unsigned grs_lerp(unsigned a,unsigned b,unsigned n,unsigned d) {
    return (a*(d-n)+b*n+d/2u)/d;
}
static inline void grs_tick(GrSampleRibbon *r,Orbit *s) {
    unsigned i=r->phase>>5,k=r->phase&31u,j=(i+1u)&7u;
    if(!r->manual){
        unsigned x=grs_lerp(r->path[i][0],r->path[j][0],k,32),y=grs_lerp(r->path[i][1],r->path[j][1],k,32);
        if(r->blend){unsigned n=9u-r->blend;x=grs_lerp(r->from_x,x,n,8);y=grs_lerp(r->from_y,y,n,8);r->blend--;}
        orbit_xy(s,x,y);
    }
    r->phase=(uint8_t)((int)r->phase+r->direction*(int)r->speed+256);
}
static inline void grs_render(GrSampleRibbon *r,Orbit *s,int16_t *out,size_t n) {
    if(!r->speed){orbit_render(s,out,n);return;}
    while(n){
        if(!r->remaining){grs_tick(r,s);r->remaining=GR_SAMPLE_QUANTUM;}
        size_t chunk=n<r->remaining?n:r->remaining;
        orbit_render(s,out,chunk);out+=chunk;n-=chunk;r->remaining=(uint16_t)(r->remaining-chunk);
    }
}
#endif
