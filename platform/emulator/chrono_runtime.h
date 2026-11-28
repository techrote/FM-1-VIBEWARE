#ifndef VW_CHRONO_RUNTIME_H
#define VW_CHRONO_RUNTIME_H
#include "performance.h"
#include "rate.h"
/* Local audio-owner API. All mutations and snapshots are serialized at audio
 * boundaries. A future USB producer must validate sessions and queue commands;
 * it must not call these functions from the main loop or serialize cm_perf_state.
 * The legacy packed-panel adapter below is standalone-only. */
typedef struct { unsigned bpm, variation, preset, playing, epoch; int warp; } CmPanel;
typedef struct { cm_state core; VwRate rate; uint32_t identity; unsigned initialized; uint8_t owner; } CmRuntime;
static inline int cm_panel_adjust(int v,int32_t d,int lo,int hi) {
    if(d>220)d=220;
    if(d< -220)d= -220;
    v+=(int)d;
    return v<lo?lo:v>hi?hi:v;
}
static inline void cm_panel_preset(CmPanel *p,unsigned preset) {
    static const unsigned bpm[]={112,142,84};
    static const int warp[]={24,-32,48};
    p->preset=preset%3u; p->bpm=bpm[p->preset]; p->warp=warp[p->preset];
    p->variation=12; p->epoch=(p->epoch+1u)&127u;
}
static inline uint32_t cm_panel_cmd(const CmPanel *p) {
    return p->bpm|((uint32_t)(p->warp+60)<<8)|(p->variation<<15)|
           (p->preset<<22)|(p->playing<<24)|(p->epoch<<25);
}
static inline unsigned cm_runtime_reset(CmRuntime *r,unsigned preset,uint32_t seed) {
    unsigned flags=cm_perf_reset(&r->core,&r->owner,preset,seed);
    if(flags&CM_PERF_FLUSH) { vw_rate_clear(&r->rate); r->initialized=1; }
    return flags;
}
static inline unsigned cm_runtime_transport(CmRuntime *r,unsigned origin,unsigned op) {
    if(!r->initialized)return CM_PERF_REJECT;
    unsigned flags=cm_perf_transport(&r->core,&r->owner,origin,op);
    if(flags&CM_PERF_FLUSH)vw_rate_clear(&r->rate);
    return flags;
}
static inline int cm_runtime_scene(CmRuntime *r,const cm_scene *scene) {
    return r->initialized && cm_perf_scene(&r->core,scene);
}
static inline int cm_runtime_snapshot(const CmRuntime *r,cm_perf_state *state) {
    if(!r->initialized)return 0;
    cm_perf_snapshot(state,&r->core,r->owner);return 1;
}
static inline int16_t cm_next_sample(void *ctx) {
    int16_t v; cm_render((cm_state *)ctx,&v,1); return v;
}
static inline void cm_runtime_audio(CmRuntime *r,int32_t *out,uint32_t n) {
    if(!r->initialized||!r->core.playing)return;
    for(uint32_t i=0;i<n;i++) {
        int32_t v=vw_rate_step(&r->rate,cm_next_sample,&r->core);
        out[2u*i]+=v; out[2u*i+1u]+=v;
    }
}
/* Standalone panel publishes one aligned word; ISR exclusively owns DSP.
 * Do not mix this level-triggered path with origin-aware remote commands.
 * Preset changes retain panel play state, unlike explicit remote reset. */
static inline void cm_runtime_render(CmRuntime *r,uint32_t c,int32_t *out,uint32_t n) {
    uint32_t identity=c&0xfec00000u;
    unsigned p=(c>>22)&3u;
    if(p>=3u) { (void)cm_runtime_transport(r,CM_ORIGIN_PANEL,CM_TRANSPORT_PANIC); return; }
    if(!r->initialized||r->identity!=identity) {
        (void)cm_runtime_reset(r,p,42); r->identity=identity;
    }
    if(!cm_controls(&r->core,c&255u,(int)((c>>8)&127u)-60,(c>>15)&127u)||!(c&(1u<<24))) {
        (void)cm_runtime_transport(r,CM_ORIGIN_PANEL,CM_TRANSPORT_STOP); return;
    }
    (void)cm_runtime_transport(r,CM_ORIGIN_PANEL,CM_TRANSPORT_START);
    cm_runtime_audio(r,out,n);
}
#endif
