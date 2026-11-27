#ifndef VW_CHRONO_RUNTIME_H
#define VW_CHRONO_RUNTIME_H
#include "chrono.h"
#include "rate.h"
/* Main publishes one aligned word; the audio callback exclusively owns DSP. */
typedef struct { unsigned bpm, variation, preset, playing, epoch; int warp; } CmPanel;
typedef struct { cm_state core; VwRate rate; uint32_t identity; unsigned initialized; } CmRuntime;
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
static inline int16_t cm_next_sample(void *ctx) {
    int16_t v; cm_render((cm_state *)ctx,&v,1); return v;
}
static inline void cm_runtime_render(CmRuntime *r,uint32_t c,int32_t *out,uint32_t n) {
    uint32_t identity=c&0xfec00000u;
    unsigned p=(c>>22)&3u;
    if(!r->initialized||r->identity!=identity) {
        cm_reset(&r->core,42,p); vw_rate_clear(&r->rate);
        r->identity=identity; r->initialized=1;
    }
    if(!cm_controls(&r->core,c&255u,(int)((c>>8)&127u)-60,(c>>15)&127u)||!(c&(1u<<24))) {
        cm_stop(&r->core); vw_rate_clear(&r->rate); return;
    }
    cm_start(&r->core);
    for(uint32_t i=0;i<n;i++) {
        int32_t v=vw_rate_step(&r->rate,cm_next_sample,&r->core);
        out[2u*i]+=v; out[2u*i+1u]+=v;
    }
}
#endif
