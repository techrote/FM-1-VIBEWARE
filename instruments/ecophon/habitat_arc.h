#ifndef ECOPHON_HABITAT_ARC_H
#define ECOPHON_HABITAT_ARC_H
/* Instrument-local score, not a wire format or shared runtime. The serialized
 * audio owner advances it in CORE samples (before any target rate bridge).
 * Cancel before manual intervention, preset/reset or another automation.
 * No allocation, no clock read, no rendering from the control/transport thread. */
#include "ecophon.h"
#define ECO_ARC_FRAMES (ECO_RATE / 10u)
#define ECO_ARC_BLOCKS 240u

typedef struct {
    uint16_t remaining, completed;
    uint8_t origin[3], active;
} EcoArc;

static inline void eco_arc_cancel(EcoArc *a) {
    a->active=0; a->remaining=0;
}
static inline int eco_arc_arm(EcoArc *a,const Eco *e) {
    if(e->muted||e->ablation) return 0;
    a->origin[0]=e->fertility; a->origin[1]=e->sharing; a->origin[2]=e->pressure;
    a->completed=0; a->remaining=0; a->active=1;
    return 1;
}
static inline unsigned eco_arc_mix(unsigned a,unsigned b,unsigned n) {
    return (a*(40u-n)+b*n)/40u;
}
static inline void eco_arc_controls(const EcoArc *a,Eco *e) {
    const unsigned n=(unsigned)a->completed+1u;
    const uint8_t base[3]={180,200,40}, drought[3]={0,0,255}, recovery[3]={255,220,0};
    const uint8_t *from,*to;
    unsigned step;
    if(n<=40u) { from=a->origin; to=base; step=n; }
    else if(n<=80u) { from=base; to=drought; step=n-40u; }
    else if(n<=120u) { from=drought; to=drought; step=40u; }
    else if(n<=160u) { from=drought; to=recovery; step=n-120u; }
    else { from=recovery; to=recovery; step=40u; }
    eco_controls(e,eco_arc_mix(from[0],to[0],step),eco_arc_mix(from[1],to[1],step),
                 eco_arc_mix(from[2],to[2],step),0);
}
/* Same 240 x 100 ms score as the native audition. Partition at cue boundaries
 * even when the caller requests arbitrary-sized chunks. After block 240 the
 * ecology continues in recovery, not a reset or loop. Initialize EcoArc to zero.
 * Caller owns buffer validity and manual/reset cancellation. */
static inline void eco_arc_render(EcoArc *a,Eco *e,int16_t *out,size_t frames) {
    if(!frames) return;
    if(e->muted||e->ablation) eco_arc_cancel(a);
    while(frames) {
        if(!a->active) { eco_render(e,out,frames); return; }
        if(!a->remaining) {
            eco_arc_controls(a,e);
            a->remaining=(uint16_t)ECO_ARC_FRAMES;
        }
        size_t count=frames<a->remaining?frames:a->remaining;
        eco_render(e,out,count);
        out+=count; frames-=count; a->remaining=(uint16_t)(a->remaining-count);
        if(!a->remaining && ++a->completed==ECO_ARC_BLOCKS) eco_arc_cancel(a);
    }
}
#endif
