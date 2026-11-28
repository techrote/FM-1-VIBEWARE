#include "sample_morph.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

/* Independent direct-core oracle: integer nearest interpolation with a
 * signed delta, including the asymmetric rounding at half ties. */
static unsigned mix(unsigned a, unsigned b, unsigned k, unsigned d) {
    int v = (int)a * (int)d + ((int)b - (int)a) * (int)k;
    return (unsigned)((v + (int)d / 2) / (int)d);
}
static void direct(Xeno *s, XenoMaterialMemory m, unsigned pos) {
    XenoMaterialPatch a = m.slot[0], b = m.slot[1];
    xeno_controls(s, mix(a.excitation,b.excitation,pos,127),
        mix(a.damping,b.damping,pos,127), mix(a.coupling,b.coupling,pos,127));
    unsigned p = pos < 64 ? a.material : b.material;
    if (s->material != p) xeno_material(s,p);
}
static int16_t expected[XENO_MORPH_QUANTUM * XENO_MORPH_MAX_STEPS + 137];
static int16_t actual[sizeof expected / sizeof *expected];
static uint32_t trace = 2166136261u;
static unsigned contrasts;
static void compare(unsigned p, unsigned q, unsigned from, unsigned to,
                    unsigned steps, unsigned seed) {
    Xeno a,b,fixed;
    XenoMaterialMemory memory;
    XenoSampleMorph m;
    xeno_memory_init(&memory);
    assert(xeno_memory_store(&memory,0,p,110,0,1));
    assert(xeno_memory_store(&memory,1,q,38,16,127));
    xeno_reset(&a,seed,p);
    xeno_strike(&a,43+seed,110);
    b = a;
    xeno_sample_morph_cancel(&m);
    assert(xeno_sample_morph_arm(&m,&a,&memory,from,to,steps));
    direct(&b,memory,from);
    fixed = b;
    for (unsigned k=0;k<steps;++k) {
        xeno_render(&b,expected+k*XENO_MORPH_QUANTUM,XENO_MORPH_QUANTUM);
        direct(&b,memory,mix(from,to,k+1,steps));
    }
    size_t duration=steps*XENO_MORPH_QUANTUM, total=duration+137;
    xeno_render(&b,expected+duration,137);
    /* Mutating caller memory after arm must not alter the detached score. */
    xeno_memory_init(&memory);
    const size_t sizes[]={1,127,4097,23,120,8191};
    for (size_t off=0,i=0;off<total;++i) {
        size_t n=sizes[i%6]; if(n>total-off)n=total-off;
        xeno_sample_morph_render(&m,&a,actual+off,n); off+=n;
    }
    assert(!m.active && m.elapsed==steps && m.position==to);
    assert(!memcmp(actual,expected,total*sizeof *actual));
    assert(!memcmp(&a,&b,sizeof a));
    assert(a.note==43+seed && a.held && a.velocity==110);
    for(size_t i=0;i<total;++i) {
        trace=(trace^(uint16_t)actual[i])*16777619u;
        assert(actual[i]>-24000 && actual[i]<24000);
    }
    xeno_render(&fixed,actual,total);
    if(memcmp(actual,expected,total*sizeof *actual)) ++contrasts;
}
static void lifecycle(void) {
    Xeno s,b;
    XenoMaterialMemory bank;
    XenoSampleMorph m;
    xeno_memory_init(&bank);
    xeno_sample_morph_cancel(&m);
    xeno_reset(&s,1,0);
    assert(!xeno_sample_morph_arm(&m,&s,&bank,0,127,1));
    assert(xeno_memory_store(&bank,0,0,100,0,12));
    assert(xeno_memory_store(&bank,1,3,60,0,120));
    assert(xeno_sample_morph_arm(&m,&s,&bank,0,127,10));
    xeno_strike(&s,48,127);
    xeno_sample_morph_render(&m,&s,actual,121);
    b=s; XenoSampleMorph saved=m;
    assert(!xeno_sample_morph_arm(&m,&s,&bank,0,128,10));
    assert(!xeno_sample_morph_arm(&m,&s,&bank,0,127,0));
    assert(!xeno_sample_morph_arm(&m,&s,&bank,0,127,1201));
    bank.slot[1].material=4;
    assert(!xeno_sample_morph_arm(&m,&s,&bank,0,127,10));
    xeno_sample_morph_render(&m,&s,NULL,0);
    assert(!memcmp(&b,&s,sizeof s) && !memcmp(&m,&saved,sizeof m));
    xeno_release(&s);
    xeno_sample_morph_render(&m,&s,actual,120);
    assert(!s.held && !s.burst && m.active);
    xeno_sample_morph_cancel(&m);
    xeno_controls(&s,30,40,50); b=s;
    xeno_sample_morph_render(&m,&s,actual,2000);
    xeno_render(&b,expected,2000);
    assert(!memcmp(actual,expected,4000) && !memcmp(&b,&s,sizeof s));
    bank.slot[1].material=3;
    assert(xeno_sample_morph_arm(&m,&s,&bank,127,0,100));
    xeno_strike(&s,60,100);
    xeno_sample_morph_cancel(&m); xeno_panic(&s);
    xeno_sample_morph_render(&m,&s,actual,2000);
    for(unsigned i=0;i<2000;++i)assert(actual[i]==0);
    assert(!m.active && !s.held);
}
int main(void) {
    const unsigned durations[]={1,17,400};
    unsigned cases=0;
    for(unsigned p=0;p<4;++p)for(unsigned q=0;q<4;++q)
        for(unsigned r=0;r<2;++r)for(unsigned d=0;d<3;++d)
            for(unsigned seed=1;seed<=2;++seed) {
                compare(p,q,r?127:0,r?0:127,durations[d],seed); ++cases;
            }
    compare(2,1,113,19,1200,3); ++cases;
    compare(0,3,64,64,17,1); ++cases;
    lifecycle();
    assert(contrasts>100);
    printf("sample morph %u PCM/state cases, %u contrasts, state %zu B, trace %08lx\n",
        cases,contrasts,sizeof(XenoSampleMorph),(unsigned long)trace);
    return 0;
}
