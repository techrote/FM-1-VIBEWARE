#include "xeno.h"
#include <string.h>
/* 24 kHz, Q15 complex rotations. Linear interpolation on quarter-wave LUT.
 * Each mode is a damped 2-D rotation; paired body coupling is a convex mix.
 * State is explicitly bounded; all products fit signed 64-bit. */
static const int16_t sine[65] = {
    0,804,1608,2410,3212,4011,4808,5602,6393,7180,7962,8740,9512,10279,11039,11793,
    12539,13279,14010,14732,15446,16151,16846,17530,18204,18868,19519,20159,20787,21403,22005,22594,
    23170,23731,24279,24811,25329,25832,26319,26790,27245,27683,28105,28510,28898,29268,29621,29956,
    30273,30571,30852,31113,31356,31580,31785,31971,32137,32285,32412,32521,32609,32678,32728,32757,32767
};
/* Q16 cycles/sample at MIDI 36..47, octave shifted for higher notes. */
static const uint16_t base[12]={179,189,200,212,225,238,252,267,283,300,318,337};
/* Q8 ratios of the six resonances: body A then body B. */
static const uint16_t ratios[4][6]={{256,512,768,263,538,801},{256,381,689,271,403,731},{256,707,1114,294,769,1241},{256,333,467,251,347,489}};
static const uint16_t loss[4][6]={{30,51,83,36,62,97},{14,26,54,19,32,62},{8,14,29,11,18,35},{66,98,137,77,110,160}};
static unsigned clip7(unsigned v){return v>127u?127u:v;}
static int32_t bounded(int64_t x){return x>65535?65535:x< -65535?-65535:(int32_t)x;}
static int16_t sinq(uint32_t phase){
    unsigned p=phase&65535u, q=p>>14, t=p&16383u;
    if(q&1u)t=16384u-t;
    unsigned i=t>>8, f=t&255u;
    int32_t v=sine[i];
    if(i<64u)v+=(int32_t)(sine[i+1]-v)*(int32_t)f/256;
    return (int16_t)(q>=2u?-v:v);
}
static void tune(Xeno *s){
    unsigned n=s->note-36u, oct=n/12u;
    uint32_t f=(uint32_t)base[n%12u]<<oct;
    for(unsigned m=0;m<XENO_MODES;m++){
        uint32_t p=f*ratios[s->material][m]/256u;
        if(p>29491u)p=29491u; /* keep every resonance below 0.45 Fs */
        s->sn[m]=sinq(p);s->cs[m]=sinq(p+16384u);
    }
}
void xeno_reset(Xeno *s,uint32_t seed,unsigned material){
    memset(s,0,sizeof *s);s->rng=seed?seed:1u;s->note=48;s->material=(uint8_t)(material%XENO_PRESETS);
    xeno_controls(s,76,38,48);tune(s);
}
void xeno_controls(Xeno *s,unsigned e,unsigned d,unsigned c){s->excitation=(uint8_t)clip7(e);s->damping=(uint8_t)clip7(d);s->coupling=(uint8_t)clip7(c);}
void xeno_material(Xeno *s,unsigned m){if(m<XENO_PRESETS){s->material=(uint8_t)m;tune(s);}}
void xeno_strike(Xeno *s,unsigned note,unsigned velocity){
    if(!velocity){xeno_release(s);return;}
    s->note=(uint8_t)(note<36u?36u:note>84u?84u:note);s->velocity=(uint8_t)clip7(velocity);
    tune(s);s->burst=(uint16_t)(32u+2u*s->excitation);s->held=1;
    /* Deterministic impulse launches body A; body B receives energy via coupling only. */
    for(unsigned m=0;m<3;m++)s->re[m]=bounded((int64_t)s->re[m]+(int32_t)s->velocity*(90-(int)m*18));
}
void xeno_release(Xeno *s){s->held=0;s->burst=0;}
void xeno_panic(Xeno *s){memset(s->re,0,sizeof s->re);memset(s->im,0,sizeof s->im);s->burst=0;s->held=0;}
uint32_t xeno_mode_level(const Xeno *s,unsigned m){if(m>=XENO_MODES)return 0;int32_t a=s->re[m],b=s->im[m];return (uint32_t)(a<0?-a:a)+(uint32_t)(b<0?-b:b);}
void xeno_render(Xeno *s,int16_t *out,size_t frames){
    for(size_t i=0;i<frames;i++){
        int32_t ex=0;
        if(s->burst){
            s->rng^=s->rng<<13;s->rng^=s->rng>>17;s->rng^=s->rng<<5;
            int32_t n=(int32_t)(s->rng&65535u)-32768;
            /* bounded nonlinear contact: harder impacts increase roughness and duration */
            int32_t shape=n*(int32_t)(n<0?-n:n)/32768;
            n=(n*(127-(int32_t)s->excitation)+shape*s->excitation)/127;
            ex=n*(int32_t)s->velocity*(int32_t)s->burst/ (32768*128);
            --s->burst;
        }
        for(unsigned m=0;m<XENO_MODES;m++){
            int32_t a=s->re[m],b=s->im[m];
            int32_t damp=32767-(int32_t)loss[s->material][m]-4*(int32_t)s->damping-(s->held?0:210);
            int64_t r=(int64_t)a*s->cs[m]-(int64_t)b*s->sn[m];
            int64_t j=(int64_t)a*s->sn[m]+(int64_t)b*s->cs[m];
            s->re[m]=bounded((r/32768)*damp/32768+(m<3u?ex/(int32_t)(m+1u):0));
            s->im[m]=bounded((j/32768)*damp/32768);
        }
        /* Symmetric energy-sharing mix (Q15), zero is uncoupled ablation. */
        int32_t k=(int32_t)s->coupling*6;
        for(unsigned m=0;m<3;m++){
            unsigned b=m+3;int32_t dr=(s->re[b]-s->re[m])*k/32768,di=(s->im[b]-s->im[m])*k/32768;
            s->re[m]+=dr;s->re[b]-=dr;s->im[m]+=di;s->im[b]-=di;
        }
        int32_t sum=0;for(unsigned m=0;m<XENO_MODES;m++)sum+=s->re[m];
        sum/=3; /* soft saturation with hard bound; signed operations stay in range */
        out[i]=(int16_t)((int64_t)sum*24000/(24000+(sum<0?-sum:sum)));
    }
}
