#ifndef VW_RATE_LINEAR_H
#define VW_RATE_LINEAR_H
#include "rate.h"
/* Experimental causal first-order hold, delayed by one 24 kHz sample.
 * Identical source call schedule to VwRate; no lookahead or allocation.
 * Not selected by any qualified target. Clear on panic/reset, as with VwRate. */
typedef struct { uint32_t phase; int16_t previous, current; uint8_t valid; } VwRateLinear;
static inline void vw_linear_clear(VwRateLinear *r) {
    r->phase=0; r->previous=0; r->current=0; r->valid=0;
}
static inline int16_t vw_linear_step(VwRateLinear *r, VwNext next, void *ctx) {
    if (!r->valid) { r->previous=r->current; r->current=next(ctx); r->valid=1; }
    /* Difference times phase bounded by 65535*146, safely inside int32_t. */
    int32_t delta=(int32_t)r->current-r->previous;
    int16_t out=(int16_t)(r->previous+delta*(int32_t)r->phase/147);
    r->phase+=80u;
    if(r->phase>=147u) { r->phase-=147u; r->valid=0; }
    return out;
}
#endif
