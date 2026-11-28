#include "xeno.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
static int16_t a[24000],b[24000];
static unsigned long energy(const int16_t *p,size_t n){unsigned long e=0;for(size_t i=0;i<n;i++)e+=(unsigned)abs(p[i]);return e;}
int main(void){
    Xeno s,t;unsigned peaks=0;uint32_t seed=123;
    for(unsigned p=0;p<4;p++){
        xeno_reset(&s,123,p);xeno_reset(&t,123,p);xeno_strike(&s,48,110);xeno_strike(&t,48,110);
        xeno_render(&s,a,24000);for(unsigned i=0;i<24000;i+=100)xeno_render(&t,b+i,100);
        assert(!memcmp(a,b,sizeof a));assert(energy(a,24000)>1000);assert(!memcmp(&s,&t,sizeof s));
        xeno_panic(&s);xeno_render(&s,b,24000);assert(!energy(b,24000));
    }
    xeno_reset(&s,42,2);xeno_reset(&t,42,2);xeno_controls(&s,90,0,127);xeno_controls(&t,90,0,0);
    xeno_strike(&s,48,127);xeno_strike(&t,48,127);xeno_render(&s,a,1000);xeno_render(&t,b,1000);
    assert(memcmp(a,b,2000));assert(xeno_mode_level(&s,3)>0);assert(xeno_mode_level(&t,3)==0);
    xeno_release(&s);xeno_render(&s,a,24000);assert(energy(a,200)>0);assert(!energy(a+23000,1000));
    xeno_reset(&s,7,0);
    for(unsigned i=0;i<20000;i++){
        seed=seed*1664525u+1013904223u;
        xeno_material(&s,(seed>>8)%5u);xeno_controls(&s,seed&255u,(seed>>8)&255u,(seed>>16)&255u);
        xeno_strike(&s,(seed>>24),seed&127u);if(i%7u==0)xeno_release(&s);if(i%31u==0)xeno_panic(&s);
        xeno_render(&s,a,64);for(unsigned j=0;j<64;j++){unsigned v=(unsigned)abs(a[j]);if(v>peaks)peaks=v;assert(v<24000);}
        for(unsigned j=0;j<6;j++)assert(xeno_mode_level(&s,j)<=131070u);
    }
    printf("PASS 4 presets, block identity, coupling ablation, release/panic, 1,280,000 stress samples; peak=%u state=%zu\n",peaks,sizeof(Xeno));
}
