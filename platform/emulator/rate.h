#ifndef VW_RATE_H
#define VW_RATE_H
#include <stdint.h>
/* 24 kHz mono -> 44.1 kHz stereo Q15; causal sample hold. No lookahead. */
typedef struct { uint32_t phase; int16_t sample; uint8_t valid; } VwRate;
typedef int16_t (*VwNext)(void *);
static inline void vw_rate_clear(VwRate *r) {
    r->phase=0; r->sample=0; r->valid=0;
}
static inline int16_t vw_rate_step(VwRate *r, VwNext next, void *ctx) {
    if (!r->valid) { r->sample=next(ctx); r->valid=1; }
    int16_t out=r->sample;
    r->phase+=80u;
    if(r->phase>=147u) { r->phase-=147u; r->valid=0; }
    return out;
}
#endif
