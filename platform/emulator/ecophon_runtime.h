#ifndef VW_ECOPHON_RUNTIME_H
#define VW_ECOPHON_RUNTIME_H
#include "ecophon.h"
#include "rate.h"
/* Local aligned snapshot, not a wire protocol. Main owns panel state, ISR owns core. */
typedef struct { unsigned fertility, pressure, preset, playing, epoch; } EcoPanel;
typedef struct { Eco eco; VwRate rate; uint32_t identity; unsigned initialized; } EcoRuntime;
static inline void eco_panel_preset(EcoPanel *p,unsigned preset) {
    static const uint8_t f[]={180,100,230,180}, q[]={40,150,85,40};
    p->preset=preset&3u; p->fertility=f[p->preset]; p->pressure=q[p->preset];
    p->epoch=(p->epoch+1u)&8191u;
}
static inline unsigned eco_panel_adjust(unsigned value,int32_t delta) {
    if(delta>255) delta=255;
    if(delta< -255) delta= -255;
    int32_t v=(int32_t)value+delta;
    return v<0?0u:v>255?255u:(unsigned)v;
}
static inline uint32_t eco_panel_cmd(const EcoPanel *p) {
    return p->fertility|(p->pressure<<8)|(p->preset<<16)|(p->playing<<18)|(p->epoch<<19);
}
static inline int16_t eco_next_sample(void *ctx) {
    int16_t sample; eco_render((Eco *)ctx,&sample,1); return sample;
}
static inline void eco_runtime_render(EcoRuntime *r,uint32_t c,int32_t *out,uint32_t n) {
    static const uint8_t sharing[]={200,20,90,200};
    unsigned p=(c>>16)&3u;
    uint32_t identity=c&0xfffb0000u;
    if(!r->initialized || r->identity!=identity) {
        eco_reset(&r->eco,42,p==3?0:p);
        vw_rate_clear(&r->rate);
        r->identity=identity; r->initialized=1;
    }
    eco_controls(&r->eco,c&255u,(unsigned)sharing[p],(c>>8)&255u,p==3);
    if(!(c&(1u<<18))) {
        eco_mute(&r->eco,1); vw_rate_clear(&r->rate); return;
    }
    eco_mute(&r->eco,0);
    for(uint32_t i=0;i<n;++i) {
        int32_t v=vw_rate_step(&r->rate,eco_next_sample,&r->eco);
        out[2u*i]+=v; out[2u*i+1u]+=v;
    }
}
#endif
