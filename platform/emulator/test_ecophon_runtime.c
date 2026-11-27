#include "ecophon_runtime.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <limits.h>
#define N 44100u
static int32_t a[N*2],b[N*2];
int main(void) {
    EcoPanel p={0}; eco_panel_preset(&p,0);
    EcoRuntime x={0},y={0};
    eco_runtime_render(&x,eco_panel_cmd(&p),a,N);
    assert(x.eco.ticks==0 && x.eco.muted && !x.rate.valid);
    for(unsigned i=0;i<N*2;++i) assert(a[i]==0);
    p.playing=1;
    eco_runtime_render(&x,eco_panel_cmd(&p),a,N);
    for(unsigned off=0;off<N;) {
        unsigned n=N-off<113?N-off:113;
        eco_runtime_render(&y,eco_panel_cmd(&p),b+off*2,n); off+=n;
    }
    assert(!memcmp(a,b,sizeof a));
    unsigned nonzero=0; for(unsigned i=0;i<N;++i) {
        assert(a[i*2]==a[i*2+1]); nonzero+=(a[i*2]!=0);
    }
    assert(nonzero>40000 && x.eco.ticks==100);
    p.playing=0; memset(b,0,sizeof b);
    eco_runtime_render(&x,eco_panel_cmd(&p),b,N);
    assert(x.eco.ticks==100 && !x.rate.valid);
    for(unsigned i=0;i<N*2;++i) assert(b[i]==0);
    p.playing=1; p.pressure=255; p.fertility=0;
    memset(a,0,sizeof a); memset(b,0,sizeof b);
    eco_runtime_render(&x,eco_panel_cmd(&p),a,N);
    p.pressure=40; p.fertility=180;
    eco_runtime_render(&y,eco_panel_cmd(&p),b,N);
    assert(memcmp(a,b,sizeof a)!=0 && x.eco.ticks>=199);
    eco_panel_preset(&p,3); memset(a,0,sizeof a);
    eco_runtime_render(&x,eco_panel_cmd(&p),a,N);
    assert(x.eco.ablation && x.eco.ticks==100 && !x.eco.births && !x.eco.gifts);
    eco_panel_preset(&p,0); memset(a,0,sizeof a); memset(b,0,sizeof b);
    eco_runtime_render(&x,eco_panel_cmd(&p),a,N);
    EcoRuntime fresh={0}; eco_runtime_render(&fresh,eco_panel_cmd(&p),b,N);
    assert(!memcmp(a,b,sizeof a));
    assert(eco_panel_adjust(1,INT32_MIN)==0 && eco_panel_adjust(254,INT32_MAX)==255);
    printf("Ecophon adapter PASS: %u nonzero frames, 100 Hz tick, partition, mute/freeze, intervention, reset and frozen comparator\n",nonzero);
}
