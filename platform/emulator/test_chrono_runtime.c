#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <limits.h>
#include "chrono_runtime.h"
#define N 44100u
static int32_t a[2*N],b[2*N];
int main(void) {
    CmRuntime r={0},s={0}; CmPanel p={0}; cm_panel_preset(&p,0); p.playing=1;
    uint32_t cmd=cm_panel_cmd(&p);
    cm_runtime_render(&r,cmd,a,N);
    for(unsigned i=0;i<N;) {
        unsigned n=N-i<113u?N-i:113u;
        cm_runtime_render(&s,cmd,b+2*i,n); i+=n;
    }
    assert(!memcmp(a,b,sizeof a));
    unsigned nonzero=0;
    for(unsigned i=0;i<N;i++) { assert(a[2*i]==a[2*i+1]); assert(a[2*i]>=-32768&&a[2*i]<=32767); nonzero+=a[2*i]!=0; }
    assert(nonzero>N/2);
    assert(r.core.lane[0].ticks==8);
    uint32_t phase=r.core.lane[0].clock,ticks=r.core.lane[0].ticks;
    p.playing=0; memset(b,0,sizeof b); cm_runtime_render(&r,cm_panel_cmd(&p),b,N);
    for(unsigned i=0;i<2*N;i++)assert(!b[i]);
    assert(r.core.lane[0].clock==phase&&r.core.lane[0].ticks==ticks&&!r.rate.valid);
    p.playing=1; p.bpm=220; p.warp=-60; p.variation=100;
    cm_runtime_render(&r,cm_panel_cmd(&p),b,N);
    assert(r.core.lane[0].ticks>ticks+10&&r.core.bpm==220&&r.core.warp==-60&&r.core.variation==100);
    cm_panel_preset(&p,0); memset(b,0,sizeof b); cm_runtime_render(&r,cm_panel_cmd(&p),b,N);
    assert(!memcmp(a,b,sizeof a));
    cm_panel_preset(&p,1); memset(b,0,sizeof b); cm_runtime_render(&r,cm_panel_cmd(&p),b,N);
    assert(memcmp(a,b,sizeof a)&&r.core.preset==1);
    memset(b,0,sizeof b); cm_runtime_render(&r,cm_panel_cmd(&p)&~255u,b,N);
    for(unsigned i=0;i<2*N;i++)assert(!b[i]);
    assert(cm_panel_adjust(100,INT_MAX,0,100)==100&&cm_panel_adjust(40,INT_MIN,40,220)==40);
    printf("Chronomorph runtime PASS: %u/%u nonzero frames; 8 master ticks; partition, reset, preset, tempo/warp, pause and malformed mute\n",nonzero,N);
    return 0;
}
