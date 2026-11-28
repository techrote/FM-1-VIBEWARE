#include "material_memory.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <limits.h>

/* Independent signed-delta formulation of rounded interpolation. */
static unsigned oracle(unsigned a,unsigned b,unsigned p) {
    int delta=((int)b-(int)a)*(int)p;
    return (unsigned)((int)a+(delta<0 ? -((-delta+63)/127) : (delta+63)/127));
}
static void unchanged(const Xeno *a,const Xeno *b) {
    assert(!memcmp(a,b,sizeof *a));
}
int main(void) {
    Xeno s, ref, before;
    XenoMaterialMemory m, saved;
    int16_t pcm[120], other[120];
    unsigned blocks=0, sounding=0;
    xeno_memory_init(&m);
    xeno_reset(&s,42,0); before=s;
    assert(!xeno_memory_morph(&m,0,&s));
    assert(!xeno_memory_recall(&m,0,&s)); unchanged(&s,&before);
    for(unsigned a=0;a<128;a++) for(unsigned b=0;b<128;b++)
        for(unsigned p=0;p<128;p++)
            assert(xeno_memory_mix(a,b,p)==oracle(a,b,p));
    for(unsigned a=0;a<XENO_PRESETS;a++) for(unsigned b=0;b<XENO_PRESETS;b++) {
        xeno_memory_init(&m);
        xeno_reset(&s,42,a); xeno_controls(&s,76,0,84); before=s;
        assert(xeno_memory_capture(&m,0,&s)); unchanged(&s,&before);
        assert(!xeno_memory_morph(&m,127,&s)); unchanged(&s,&before);
        assert(xeno_memory_store(&m,1,b,110,5,12)); unchanged(&s,&before);
        saved=m;
        assert(!xeno_memory_store(&m,2,b,110,5,12));
        assert(!xeno_memory_store(&m,0,XENO_PRESETS,110,5,12));
        assert(!xeno_memory_store(&m,0,a,128,5,12));
        assert(!xeno_memory_store(&m,0,a,110,128,12));
        assert(!xeno_memory_store(&m,0,a,110,5,UINT_MAX));
        assert(!memcmp(&m,&saved,sizeof m));
        assert(!xeno_memory_morph(&m,UINT_MAX,&s));
        assert(!xeno_memory_recall(&m,UINT_MAX,&s)); unchanged(&s,&before);
        ref=s;
        for(unsigned i=0;i<256;i++) {
            unsigned p=i<128?i:255-i;
            unsigned mat=p<64?a:b;
            before=s;
            assert(xeno_memory_morph(&m,p,&s));
            assert(s.held==before.held && s.note==before.note && s.velocity==before.velocity);
            assert(s.rng==before.rng && s.burst==before.burst);
            assert(!memcmp(s.re,before.re,sizeof s.re) && !memcmp(s.im,before.im,sizeof s.im));
            xeno_controls(&ref,oracle(76,110,p),oracle(0,5,p),oracle(84,12,p));
            if(ref.material!=mat)xeno_material(&ref,mat);
            unchanged(&s,&ref);
            if(i%16==3){xeno_strike(&s,48+i/16,110);xeno_strike(&ref,48+i/16,110);}
            if(i%16==1){xeno_release(&s);xeno_release(&ref);}
            xeno_render(&s,pcm,120);xeno_render(&ref,other,120);
            assert(!memcmp(pcm,other,sizeof pcm)); unchanged(&s,&ref); blocks++;
            for(unsigned j=0;j<120;j++) if(pcm[j]) {sounding++;break;}
        }
        xeno_panic(&s); xeno_panic(&ref);
        assert(xeno_memory_recall(&m,1,&s));
        xeno_controls(&ref,110,5,12);if(ref.material!=b)xeno_material(&ref,b);
        xeno_render(&s,pcm,120);xeno_render(&ref,other,120);
        for(unsigned j=0;j<120;j++)assert(pcm[j]==0 && other[j]==0);
        unchanged(&s,&ref);
        assert(!memcmp(&m,&saved,sizeof m));
        xeno_reset(&s,42,0); assert(xeno_memory_recall(&m,0,&s));
        assert(s.material==a && s.excitation==76 && s.damping==0 && s.coupling==84 && !s.held);
    }
    assert(sounding>blocks/2);
    printf("PASS 2097152 interpolation cases; %u native PCM/state blocks (%u sounding), 16 panic tails; controller %zu bytes\n",blocks,sounding,sizeof m);
    return 0;
}
