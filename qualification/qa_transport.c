/* Independent transition-table oracle for the Chronomorph v1 semantic seam.
 * The caller's queue, authentication and cache invalidation implementation
 * are outside this test: FLUSH is checked as an obligation, not proof. */
#include "performance.h"
#include <assert.h>
#include <stdio.h>

enum action { REJECT, IGNORE, STOP, PANEL, REMOTE };
/* Rows: stopped, panel playing, companion playing. Columns: each origin's
 * start/stop/panic/invalid command. Last group is invalid origin. */
static const enum action table[3][16] = {
    {PANEL,STOP,STOP,REJECT, REMOTE,STOP,STOP,REJECT, REJECT,IGNORE,REJECT,REJECT, REJECT,REJECT,REJECT,REJECT},
    {PANEL,STOP,STOP,REJECT, IGNORE,IGNORE,STOP,REJECT, REJECT,IGNORE,REJECT,REJECT, REJECT,REJECT,REJECT,REJECT},
    {PANEL,STOP,STOP,REJECT, REMOTE,STOP,STOP,REJECT, REJECT,STOP,REJECT,REJECT, REJECT,REJECT,REJECT,REJECT}
};
static const unsigned receipt[]={0,5,3,1,1};
static unsigned counts[5], blocks, sounding, silent;
static uint32_t trace=UINT32_C(2166136261);
static void step(cm_state *a,cm_state *b,uint8_t *owner,unsigned *model,unsigned cmd,unsigned split){
    enum action expected=table[*model][cmd];
    unsigned result=cm_perf_transport(a,owner,cmd/4,cmd%4);
    assert(result==receipt[expected]);
    ++counts[expected];
    switch(expected){
    case PANEL: cm_start(b);*model=1;break;
    case REMOTE: cm_start(b);*model=2;break;
    case STOP: cm_stop(b);*model=0;break;
    default: break;
    }
    assert(*owner==*model && !memcmp(a,b,sizeof *a));
    int16_t x[1200],y[1200];
    cm_render(a,x,1200);cm_render(b,y,split);cm_render(b,y+split,1200-split);
    assert(!memcmp(x,y,sizeof x) && !memcmp(a,b,sizeof *a));
    cm_perf_state v;cm_perf_snapshot(&v,a,*owner);
    assert(v.owner==*model && v.playing==(*model!=0) && v.master==b->master && v.beat==b->beat);
    assert(v.bpm==b->bpm && v.warp==b->warp && v.variation==b->variation && v.preset==b->preset);
    for(unsigned i=0;i<CM_LANES;i++){
        const cm_lane *l=&b->lane[i];const cm_perf_lane *d=&v.lane[i];
        assert(d->clock==l->clock && d->ticks==l->ticks && d->hits==l->hits && d->mask==l->mask && d->length==l->length && d->step==l->step && d->cycle==l->cycle);
    }
    unsigned nz=0;
    for(unsigned i=0;i<1200;i++){nz+=(x[i]!=0);trace=(trace^(uint16_t)x[i])*UINT32_C(16777619);}
    if(!*model)assert(!nz);
    ++blocks;if(nz)++sounding;else ++silent;
}
int main(void){
    const uint32_t seeds[]={0,17,UINT32_MAX};
    const unsigned splits[]={1,17,1199};
    for(unsigned p=0;p<3;p++)for(unsigned j=0;j<3;j++)for(unsigned initial=0;initial<3;initial++)
    for(unsigned first=0;first<16;first++)for(unsigned second=0;second<16;second++){
        cm_state a,b;int16_t warm[1200];uint8_t owner=(uint8_t)initial;unsigned model=initial;
        cm_reset(&a,seeds[j],p);cm_start(&a);cm_render(&a,warm,1200);
        if(!initial)cm_stop(&a);
        memcpy(&b,&a,sizeof b);
        step(&a,&b,&owner,&model,first,splits[j]);
        step(&a,&b,&owner,&model,second,splits[(j+1)%3]);
    }
    assert(blocks==13824 && sounding>0 && silent>0);
    for(unsigned i=0;i<5;i++)assert(counts[i]>0);
    printf("QA transport: %u blocks, %u sounding, %u silent; reject/ignore/stop/panel/remote %u/%u/%u/%u/%u; trace %08lx\n",blocks,sounding,silent,counts[0],counts[1],counts[2],counts[3],counts[4],(unsigned long)trace);
    return 0;
}
