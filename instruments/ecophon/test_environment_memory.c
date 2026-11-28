/* Compare local memory semantics against an independent schedule and real core. */
#include "environment_memory.h"
#include "ecophon.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#define N 2400u
static int equal(EcoEnvironment a,EcoEnvironment b) { return a.f==b.f&&a.s==b.s&&a.p==b.p; }
static EcoEnvironment reference(EcoEnvironment a,EcoEnvironment b,unsigned n) {
    /* Integer floor of a+(b-a)*n/40, including descending transitions. */
    int x[3]={a.f,a.s,a.p}, y[3]={b.f,b.s,b.p};
    for(unsigned i=0;i<3;++i){int d=(y[i]-x[i])*(int)n; x[i]+=d>=0?d/40:-((-d+39)/40);}
    return (EcoEnvironment){(uint8_t)x[0],(uint8_t)x[1],(uint8_t)x[2]};
}
static void bounds(void) {
    EcoMemory m; eco_memory_init(&m); assert(!eco_memory_recall(&m,0));
    for(unsigned a=0;a<256;++a) for(unsigned b=0;b<256;++b){
        EcoEnvironment from={(uint8_t)a,(uint8_t)b,127},to={(uint8_t)b,(uint8_t)a,0};
        eco_memory_reset(&m,to); assert(eco_memory_capture(&m,0));
        eco_memory_reset(&m,from); assert(eco_memory_recall(&m,0));
        for(unsigned n=1;n<=40;++n) assert(equal(eco_memory_next(&m),reference(from,to,n)));
        assert(!m.active&&equal(eco_memory_next(&m),to));
    }
    assert(eco_memory_recall(&m,0)); EcoMemory before=m;
    assert(!eco_memory_manual(&m,256,0,0)&&!eco_memory_capture(&m,2)&&!eco_memory_recall(&m,2));
    assert(!memcmp(&m,&before,sizeof m));
    eco_memory_freeze(&m,1); assert(!m.active&&!eco_memory_recall(&m,0));
    eco_memory_freeze(&m,0); assert(eco_memory_recall(&m,0)); eco_memory_stop(&m);
    assert(!m.active&&!eco_memory_recall(&m,0));
    eco_memory_reset(&m,(EcoEnvironment){1,2,3}); assert(eco_memory_recall(&m,0));
    assert(eco_memory_manual(&m,9,8,7)); assert(!m.active&&equal(eco_memory_next(&m),(EcoEnvironment){9,8,7}));
}
static void score(unsigned preset,unsigned takeover) {
    const EcoEnvironment A={0,0,255},B={255,220,0},manual={150,240,70};
    Eco e,r; EcoMemory m; eco_reset(&e,42,preset); eco_reset(&r,42,preset); eco_memory_init(&m);
    EcoEnvironment initial={e.fertility,e.sharing,e.pressure};
    eco_memory_reset(&m,A); assert(eco_memory_capture(&m,0));
    eco_memory_reset(&m,B); assert(eco_memory_capture(&m,1)); eco_memory_reset(&m,initial);
    EcoEnvironment captured=reference(initial,A,20), expected=initial;
    int16_t pcm[N], control[N]; unsigned heard=0;
    for(unsigned block=1;block<=190;++block){
        int n=(int)block-30;
        if(n==1) assert(eco_memory_recall(&m,0));
        if(n==21) {assert(eco_memory_capture(&m,0)); assert(equal(m.slots[0],captured));}
        if(n==51) assert(eco_memory_recall(&m,1));
        if(n==71&&takeover) assert(eco_memory_manual(&m,manual.f,manual.s,manual.p));
        if(n==101&&!takeover) assert(eco_memory_recall(&m,0));
        if(n>=1&&n<=40) expected=reference(initial,A,(unsigned)n);
        else if(n>=51&&n<=90) expected=reference(A,B,(unsigned)(n-50));
        else if(n>=101&&n<=140) expected=reference(B,captured,(unsigned)(n-100));
        if(takeover&&n>=71) expected=manual;
        if(n==151){eco_memory_stop(&m); eco_mute(&e,1); eco_mute(&r,1);}
        EcoEnvironment got=eco_memory_next(&m); assert(equal(got,expected));
        eco_controls(&e,got.f,got.s,got.p,0); eco_controls(&r,expected.f,expected.s,expected.p,0);
        eco_render(&e,pcm,N); eco_render(&r,control,N);
        assert(!memcmp(pcm,control,sizeof pcm)); assert(!memcmp(&e,&r,sizeof e)); assert(e.ticks==block*10u);
        for(unsigned i=0;i<N;++i){assert(pcm[i]>=-24000&&pcm[i]<=24000); if(n>150) assert(!pcm[i]); else if(pcm[i]) ++heard;}
    }
    assert(heard);
}
int main(void) {
    bounds(); for(unsigned p=0;p<3;++p){score(p,0);score(p,1);}
    printf("PASS 2621440 interpolation positions; 1140 actual-core PCM/state blocks; memory bytes=%zu\n",sizeof(EcoMemory));
    return 0;
}
