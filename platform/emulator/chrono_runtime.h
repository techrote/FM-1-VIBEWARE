#ifndef VW_CHRONO_RUNTIME_H
#define VW_CHRONO_RUNTIME_H
#include "performance.h"
#include "sample_score.h"
#include "rate.h"
/* Local audio-owner API. All mutations and snapshots are serialized at audio
 * boundaries. A future USB producer must validate sessions and queue commands;
 * it must not call these functions from the main loop or serialize cm_perf_state.
 * The legacy packed-panel adapter below is standalone-only. */
typedef struct { unsigned bpm, variation, preset, playing, epoch; int warp; } CmPanel;
typedef struct { cm_state core; VwRate rate; uint32_t identity; unsigned initialized; uint8_t owner, retiring; cm_sample_score score; } CmRuntime;
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
static inline void cm_runtime_flush(CmRuntime *r) {
    cm_sample_score_cancel(&r->score); vw_rate_clear(&r->rate); r->retiring=0;
}
static inline unsigned cm_runtime_reset(CmRuntime *r,unsigned preset,uint32_t seed) {
    unsigned flags=cm_perf_reset(&r->core,&r->owner,preset,seed);
    if(flags&CM_PERF_FLUSH) { cm_runtime_flush(r); r->initialized=1; }
    return flags;
}
static inline unsigned cm_runtime_transport(CmRuntime *r,unsigned origin,unsigned op) {
    if(!r->initialized)return CM_PERF_REJECT;
    unsigned before=r->owner;
    unsigned flags=cm_perf_transport(&r->core,&r->owner,origin,op);
    if(flags&CM_PERF_FLUSH) cm_runtime_flush(r);
    else if(flags==CM_PERF_ACCEPT && op==CM_TRANSPORT_START) {
        if(r->retiring) cm_runtime_flush(r);
        if(before!=r->owner) cm_sample_score_cancel(&r->score);
    }
    return flags;
}
static inline int cm_runtime_scene(CmRuntime *r,const cm_scene *scene) {
    if(!r->initialized || !cm_perf_scene(&r->core,scene)) return 0;
    cm_sample_score_cancel(&r->score); return 1;
}
static inline int cm_runtime_score_begin(CmRuntime *r,const cm_scene_bank *bank,unsigned seconds) {
    return r->initialized && cm_sample_score_begin(&r->score,&r->core,bank,seconds);
}
static inline int cm_runtime_snapshot(const CmRuntime *r,cm_perf_state *state) {
    if(!r->initialized)return 0;
    cm_perf_snapshot(state,&r->core,r->owner);return 1;
}
static inline int16_t cm_next_sample(void *ctx) {
    CmRuntime *r=(CmRuntime *)ctx;
    int16_t v;
    if(cm_score_peek(&r->score.cursor)) {
        if(cm_sample_score_render(&r->score,&r->core,&v,1)) {
            r->retiring=1;
        }
    } else cm_render(&r->core,&v,1);
    return v;
}
static inline void cm_runtime_audio(CmRuntime *r,int32_t *out,uint32_t n) {
    if(!r->initialized)return;
    for(uint32_t i=0;i<n && (r->core.playing||r->retiring);i++) {
        int32_t v=vw_rate_step(&r->rate,cm_next_sample,r);
        out[2u*i]+=v; out[2u*i+1u]+=v;
        /* Retain the final core sample for its full rational hold interval.
         * Explicit stop/panic/reset still flush immediately. */
        if(r->retiring && !r->rate.valid) {
            r->owner=CM_OWNER_NONE; cm_runtime_flush(r);
        }
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
    cm_sample_score_cancel(&r->score);
    (void)cm_runtime_transport(r,CM_ORIGIN_PANEL,CM_TRANSPORT_START);
    cm_runtime_audio(r,out,n);
}
/* Standalone panel sequence trigger: three authored scenes, each four seconds.
 * Only changed manual snapshots take over. Unchanged snapshots never restart
 * a completed score. The producer must publish cmd+epoch in one IRQ section. */
typedef struct { uint32_t cmd, epoch; unsigned seen; } CmScorePanel;
static inline void cm_runtime_score_panel(CmRuntime *r,CmScorePanel *p,uint32_t cmd,uint32_t epoch,int32_t *out,uint32_t n) {
    static const cm_scene_bank bank={.slots={
        {.bpm=112,.mask={0x49,0x15,0x529},.warp=24,.variation=12,.length={7,5,11}},
        {.bpm=142,.mask={0x15,0x129,0x55},.warp=-32,.variation=27,.length={5,9,7}},
        {.bpm=84,.mask={0x125,0x49,0x1255},.warp=48,.variation=4,.length={9,7,13}}
    },.occupied=7};
    unsigned new_score=epoch!=p->epoch;
    if(!p->seen || cmd!=p->cmd || new_score) {
        cm_runtime_render(r,cmd,out,0);
        p->cmd=cmd; p->epoch=epoch; p->seen=1;
        if(new_score) (void)cm_runtime_score_begin(r,&bank,4);
    }
    cm_runtime_audio(r,out,n);
}
#endif
