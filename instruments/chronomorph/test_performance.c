#include "performance.h"
#include <assert.h>
#include <stdio.h>

#define N 1200u
static unsigned blocks, sounding, silent;
static uint32_t trace=UINT32_C(2166136261);
static void compare(cm_state *a, cm_state *b, uint8_t owner, int must_silent) {
    int16_t x[N], y[N];
    cm_render(a,x,N); cm_render(b,y,N);
    assert(!memcmp(x,y,sizeof x) && !memcmp(a,b,sizeof *a));
    cm_perf_state v;
    cm_perf_snapshot(&v,a,owner);
    assert(v.master==b->master && v.bpm==b->bpm && v.warp==b->warp &&
           v.variation==b->variation && v.preset==b->preset && v.beat==b->beat &&
           v.playing==b->playing && v.owner==owner);
    for(unsigned i=0;i<CM_LANES;i++){
        const cm_lane *l=&b->lane[i]; const cm_perf_lane *d=&v.lane[i];
        assert(d->clock==l->clock && d->ticks==l->ticks && d->hits==l->hits &&
               d->mask==l->mask && d->length==l->length && d->step==l->step &&
               d->cycle==l->cycle && d->step<d->length && d->clock<CM_CYCLE);
    }
    unsigned nz=0;
    for(unsigned i=0;i<N;i++){
        nz+=(x[i]!=0);
        trace=(trace^(uint16_t)x[i])*UINT32_C(16777619);
    }
    if(must_silent)assert(!nz);
    ++blocks; if(nz)++sounding; else ++silent;
}
int main(void) {
    const uint32_t seeds[]={0,17,UINT32_MAX};
    for(unsigned p=0;p<3;p++)for(unsigned j=0;j<3;j++){
        cm_state a,b; uint8_t owner=CM_OWNER_NONE;
        assert(cm_perf_reset(&a,&owner,p,seeds[j])==3);
        cm_reset(&b,seeds[j],p);
        assert(cm_perf_transport(&a,&owner,CM_ORIGIN_PANEL,CM_TRANSPORT_START)==1);
        cm_start(&b); assert(owner==CM_OWNER_PANEL);
        for(unsigned k=0;k<160;k++){
            cm_scene v; cm_scene_capture(&v,&a);
            v.bpm=(uint16_t)(40u+(k*19u)%181u);
            v.warp=(int8_t)((int)((k*13u)%121u)-60);
            v.variation=(uint8_t)((k*11u)%101u);
            for(unsigned i=0;i<3;i++){
                v.length[i]=(uint8_t)(1u+(k+i*5u)%16u);
                v.mask[i]=(uint16_t)((k*137u+i*23u)&((1u<<v.length[i])-1u));
            }
            assert(cm_perf_scene(&a,&v));
            assert(cm_controls(&b,v.bpm,v.warp,v.variation));
            for(unsigned i=0;i<3;i++)assert(cm_pattern(&b,i,v.length[i],v.mask[i]));
            cm_state prior; memcpy(&prior,&a,sizeof a);
            v.length[2]=0;
            assert(!cm_perf_scene(&a,&v) && !memcmp(&a,&prior,sizeof a));
            assert(!cm_perf_reset(&a,&owner,3,0) && owner==CM_OWNER_PANEL);
            assert(!cm_perf_transport(&a,&owner,99,CM_TRANSPORT_START));
            assert(!cm_perf_transport(&a,&owner,CM_ORIGIN_SESSION_LOST,CM_TRANSPORT_PANIC));
            assert(!cm_perf_transport(&a,&owner,CM_ORIGIN_PANEL,99));
            assert(cm_perf_transport(&a,&owner,CM_ORIGIN_COMPANION,CM_TRANSPORT_START)==5);
            assert(cm_perf_transport(&a,&owner,CM_ORIGIN_COMPANION,CM_TRANSPORT_STOP)==5);
            assert(cm_perf_transport(&a,&owner,CM_ORIGIN_SESSION_LOST,CM_TRANSPORT_STOP)==5);
            assert(owner==CM_OWNER_PANEL && !memcmp(&a,&prior,sizeof a));
            compare(&a,&b,owner,0);
        }
        assert(cm_perf_transport(&a,&owner,CM_ORIGIN_COMPANION,CM_TRANSPORT_PANIC)==3);
        cm_stop(&b); assert(owner==CM_OWNER_NONE); compare(&a,&b,owner,1);
        assert(cm_perf_transport(&a,&owner,CM_ORIGIN_COMPANION,CM_TRANSPORT_START)==1);
        cm_start(&b); assert(owner==CM_OWNER_COMPANION); compare(&a,&b,owner,0);
        assert(cm_perf_transport(&a,&owner,CM_ORIGIN_SESSION_LOST,CM_TRANSPORT_STOP)==3);
        cm_stop(&b); assert(owner==CM_OWNER_NONE); compare(&a,&b,owner,1);
        assert(cm_perf_transport(&a,&owner,CM_ORIGIN_COMPANION,CM_TRANSPORT_START)==1);
        cm_start(&b);
        assert(cm_perf_transport(&a,&owner,CM_ORIGIN_PANEL,CM_TRANSPORT_START)==1);
        assert(owner==CM_OWNER_PANEL);
        assert(cm_perf_transport(&a,&owner,CM_ORIGIN_SESSION_LOST,CM_TRANSPORT_STOP)==5);
        compare(&a,&b,owner,0);
        assert(cm_perf_transport(&a,&owner,CM_ORIGIN_PANEL,CM_TRANSPORT_STOP)==3);
        cm_stop(&b); assert(owner==CM_OWNER_NONE); compare(&a,&b,owner,1);
        assert(cm_perf_transport(&a,&owner,CM_ORIGIN_COMPANION,CM_TRANSPORT_START)==1);
        cm_start(&b); assert(owner==CM_OWNER_COMPANION);
        assert(cm_perf_reset(&a,&owner,(p+1u)%3u,17)==3);
        assert(owner==CM_OWNER_NONE);
        cm_reset(&b,17,(p+1u)%3u); compare(&a,&b,owner,1);
    }
    assert(blocks==1494u && sounding>0 && silent>=36u);
    printf("performance seam: %u exact PCM/state blocks, %u sounding, %u silent; trace %08lx; snapshot %lu bytes\n",
           blocks,sounding,silent,(unsigned long)trace,(unsigned long)sizeof(cm_perf_state));
    return 0;
}
