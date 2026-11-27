#include "rate.h"
#include <assert.h>
#include <stdio.h>
static int16_t next(void *p) { uint32_t *n=p; return (int16_t)((*n)++%30001u); }
int main(void) {
    VwRate r; uint32_t n=0;
    vw_rate_clear(&r);
    for(uint32_t i=0;i<441000u;i++) {
        assert(vw_rate_step(&r,next,&n)==(int16_t)(((uint64_t)i*80u/147u)%30001u));
        assert(r.phase<147u);
    }
    assert(n==240000u && r.phase==0 && !r.valid);
    for(unsigned k=0;k<147u;k++) {
        n=0; vw_rate_clear(&r);
        for(unsigned i=0;i<k;i++) (void)vw_rate_step(&r,next,&n);
        vw_rate_clear(&r); n=0;
        assert(vw_rate_step(&r,next,&n)==0 && n==1);
    }
    puts("rate: exact 240000 source samples in 441000 frames; reset at 147 offsets PASS");
}
