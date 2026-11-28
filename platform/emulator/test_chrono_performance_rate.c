#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "chrono_runtime.h"
/* Independent 80/147 hold oracle: count output frames from last flush and
 * generate the input sample at floor(output_frame*80/147). */
typedef struct { cm_state core; uint32_t frame,input; int16_t held; } Oracle;
static unsigned blocks,sounding,silent;
static uint32_t trace=2166136261u;
static void flush(Oracle *o){o->frame=0;o->input=0;o->held=0;}
static void compare(CmRuntime *r,Oracle *o,unsigned n){
    int32_t pcm[2*257]={0};assert(n<=257);
    cm_runtime_audio(r,pcm,n);
    unsigned nz=0;
    for(unsigned i=0;i<n;i++){
        int16_t v=0;
        if(o->core.playing){
            uint32_t wanted=o->frame++*80u/147u;
            while(o->input<=wanted){cm_render(&o->core,&o->held,1);o->input++;}
            v=o->held;
        }
        assert(pcm[2*i]==v&&pcm[2*i+1]==v);nz+=v!=0;
        trace=(trace^(uint16_t)v)*16777619u;
    }
    assert(!memcmp(&r->core,&o->core,sizeof o->core));
    cm_perf_state snapshot;assert(cm_runtime_snapshot(r,&snapshot));
    assert(snapshot.owner==r->owner&&snapshot.playing==o->core.playing&&snapshot.master==o->core.master);
    for(unsigned i=0;i<CM_LANES;i++)assert(snapshot.lane[i].ticks==o->core.lane[i].ticks&&snapshot.lane[i].mask==o->core.lane[i].mask);
    blocks++;if(nz)sounding++;else silent++;
}
static void stop(CmRuntime *r,Oracle *o,unsigned origin,unsigned op){
    assert(cm_runtime_transport(r,origin,op)==(CM_PERF_ACCEPT|CM_PERF_FLUSH));
    assert(!r->rate.valid&&!r->rate.phase&&!r->rate.sample&&r->owner==CM_OWNER_NONE);
    cm_stop(&o->core);flush(o);
}
int main(void){
    CmRuntime r={0};cm_perf_state state;
    assert(!cm_runtime_snapshot(&r,&state));assert(!cm_runtime_transport(&r,CM_ORIGIN_PANEL,CM_TRANSPORT_START));
    for(unsigned p=0;p<3;p++)for(unsigned seed=1;seed<=9;seed++){
        Oracle o={0};assert(cm_runtime_reset(&r,p,seed)==(CM_PERF_ACCEPT|CM_PERF_FLUSH));cm_reset(&o.core,seed,p);
        assert(cm_runtime_transport(&r,CM_ORIGIN_PANEL,CM_TRANSPORT_START)==CM_PERF_ACCEPT);cm_start(&o.core);
        compare(&r,&o,1);assert(r.rate.valid&&r.rate.sample);
        VwRate cached=r.rate;
        assert(cm_runtime_transport(&r,CM_ORIGIN_COMPANION,CM_TRANSPORT_START)==(CM_PERF_ACCEPT|CM_PERF_IGNORED));
        assert(cm_runtime_transport(&r,CM_ORIGIN_COMPANION,CM_TRANSPORT_STOP)==(CM_PERF_ACCEPT|CM_PERF_IGNORED));
        assert(cm_runtime_transport(&r,CM_ORIGIN_SESSION_LOST,CM_TRANSPORT_STOP)==(CM_PERF_ACCEPT|CM_PERF_IGNORED));
        assert(r.owner==CM_OWNER_PANEL&&r.rate.valid==cached.valid&&r.rate.sample==cached.sample&&r.rate.phase==cached.phase);
        for(unsigned i=0;i<60;i++)compare(&r,&o,1+i%257);
        cm_scene scene;cm_scene_capture(&scene,&o.core);scene.bpm=220;scene.warp=-60;scene.variation=100;scene.length[1]=16;scene.mask[1]=0x8001;
        assert(cm_runtime_scene(&r,&scene));assert(cm_controls(&o.core,220,-60,100));assert(cm_pattern(&o.core,1,16,0x8001));
        scene.length[2]=0;assert(!cm_runtime_scene(&r,&scene));assert(!cm_runtime_reset(&r,3,seed));
        for(unsigned i=0;i<60;i++)compare(&r,&o,257-i);
        /* Stop+start between callbacks must flush held PCM, even without an
         * intervening silent render. No stale held sample may be repeated. */
        stop(&r,&o,CM_ORIGIN_PANEL,CM_TRANSPORT_STOP);
        assert(cm_runtime_transport(&r,CM_ORIGIN_COMPANION,CM_TRANSPORT_START)==CM_PERF_ACCEPT);cm_start(&o.core);
        for(unsigned i=0;i<60;i++)compare(&r,&o,1+i%31);
        stop(&r,&o,CM_ORIGIN_SESSION_LOST,CM_TRANSPORT_STOP);compare(&r,&o,257);
        assert(cm_runtime_transport(&r,CM_ORIGIN_PANEL,CM_TRANSPORT_START)==CM_PERF_ACCEPT);cm_start(&o.core);
        for(unsigned i=0;i<60;i++)compare(&r,&o,257);
        stop(&r,&o,CM_ORIGIN_COMPANION,CM_TRANSPORT_PANIC);compare(&r,&o,257);
        assert(cm_runtime_reset(&r,(p+1)%3,seed)==(CM_PERF_ACCEPT|CM_PERF_FLUSH));cm_reset(&o.core,seed,(p+1)%3);flush(&o);compare(&r,&o,257);
    }
    assert(sounding&&silent);
    printf("Chronomorph performance/rate PASS: %u exact PCM/state blocks, %u sounding, %u silent; trace %08x\n",blocks,sounding,silent,trace);
    return 0;
}
