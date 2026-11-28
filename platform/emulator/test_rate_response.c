/* Host-only witness: exact rational model plus coherent-tone measurement.
 * No target or physical timing inference. */
#include "rate_linear.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <stdint.h>

#define IN 24000u
#define OUT 44100u
#define TAU 6.283185307179586476925286766559
static int16_t src[2*IN];
typedef struct { unsigned pos; } Cursor;
static int16_t next(void *p) {
    Cursor *c=p;
    assert(c->pos<2*IN);
    return src[c->pos++];
}
static void exact(void) {
    uint32_t rng=42;
    for(unsigned i=0;i<2*IN;i++) {
        rng=rng*1664525u+1013904223u;
        src[i]=(int16_t)((int32_t)(rng>>16)-32768);
    }
    src[0]=INT16_MAX; src[1]=INT16_MIN;
    /* Every fractional phase is visited in the 147-frame period; clear
     * after each possible phase and verify a new independent source starts. */
    for(unsigned cut=1;cut<=147;cut++) {
        VwRate h; VwRateLinear l; Cursor a={0},b={0};
        vw_rate_clear(&h); vw_linear_clear(&l);
        for(unsigned j=0;j<cut;j++) {
            (void)vw_rate_step(&h,next,&a); (void)vw_linear_step(&l,next,&b);
        }
        vw_rate_clear(&h); vw_linear_clear(&l); a.pos=b.pos=0;
        for(unsigned j=0;j<294;j++) {
            unsigned k=j*80u/147u, phase=j*80u%147u;
            int32_t prev=k?src[k-1]:0, cur=src[k];
            assert(vw_rate_step(&h,next,&a)==cur);
            assert(vw_linear_step(&l,next,&b)==prev+(cur-prev)*(int32_t)phase/147);
            assert(a.pos==k+1&&b.pos==k+1);
        }
        assert(a.pos==160&&b.pos==160);
    }
    /* Exact positive/negative full-scale DC including the first causal sample. */
    for(unsigned sign=0;sign<2;sign++) {
        int16_t x=sign?INT16_MIN:INT16_MAX;
        for(unsigned i=0;i<2*IN;i++) src[i]=x;
        VwRateLinear l; Cursor b={0}; vw_linear_clear(&l);
        for(unsigned j=0;j<OUT;j++) {
            int16_t y=vw_linear_step(&l,next,&b);
            if(j>=2) assert(y==x);
        }
        assert(b.pos==IN);
    }
}
/* Coherent 1-second projection after 1-second warmup. Report fundamental
 * gain and RMS residual relative to the fundamental, not just >=12kHz power.
 * Residual includes images and quantization; no subjective quality claim. */
static void tone(unsigned hz) {
    for(unsigned i=0;i<2*IN;i++) src[i]=(int16_t)lround(12000*sin(TAU*hz*i/IN));
    double si[2]={0},co[2]={0},power[2]={0};
    VwRate h; VwRateLinear l; Cursor a={0},b={0};
    vw_rate_clear(&h); vw_linear_clear(&l);
    for(unsigned j=0;j<2*OUT;j++) {
        int16_t x[2]={vw_rate_step(&h,next,&a),vw_linear_step(&l,next,&b)};
        if(j<OUT) continue;
        double ang=TAU*hz*(j-OUT)/OUT, s=sin(ang),c=cos(ang);
        for(unsigned m=0;m<2;m++) { si[m]+=x[m]*s; co[m]+=x[m]*c; power[m]+=(double)x[m]*x[m]; }
    }
    assert(a.pos==2*IN&&b.pos==2*IN);
    double gain[2],res[2];
    for(unsigned m=0;m<2;m++) {
        double fundamental=2*hypot(si[m],co[m])/OUT;
        double fp=fundamental*fundamental/2, rp=power[m]/OUT-fp;
        assert(fundamental>0&&rp>0);
        gain[m]=20*log10(fundamental/12000); res[m]=10*log10(rp/fp);
    }
    /* Expected sinc/sinc^2 response; loose enough for finite phase grid and
     * Q15 rounding, strict enough to reject wrong rate or altered gain. */
    double w=TAU*hz/(2*IN), ideal=20*log10(sin(w)/w);
    assert(fabs(gain[0]-ideal)<0.08&&fabs(gain[1]-2*ideal)<0.08);
    assert(res[1]<res[0]);
    printf("%u,%.6f,%.6f,%.6f,%.6f\n",hz,gain[0],gain[1],res[0],res[1]);
}
int main(void) {
    exact();
    puts("hz,hold_gain_db,linear_gain_db,hold_residual_dbc,linear_residual_dbc");
    const unsigned tones[]={100,1000,3000,6000,9000,11000};
    for(unsigned i=0;i<sizeof tones/sizeof tones[0];i++) tone(tones[i]);
    puts("PASS: 147 reset phases, 43218 exact frames per mode, 88200 DC frames, six coherent tones");
    return 0;
}
