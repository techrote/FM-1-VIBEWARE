#include "sample_morph.h"
#include <stdio.h>
#include <stdlib.h>

/* Three matched six-second performances: fixed A, morph A->B, morph B->A.
 * Note events are explicit and identical; the sweep never generates a note. */
static void le(FILE *f, uint32_t n, unsigned bytes) {
    for(unsigned i=0;i<bytes;++i) { fputc((int)(n&255u),f); n>>=8; }
}
static int render(const char *path, unsigned arm) {
    enum { FRAMES = 6 * XENO_RATE };
    FILE *f=fopen(path,"wb"); if(!f)return 0;
    fputs("RIFF",f); le(f,36u+2u*FRAMES,4); fputs("WAVEfmt ",f);
    le(f,16,4); le(f,1,2); le(f,1,2); le(f,XENO_RATE,4);
    le(f,XENO_RATE*2,4); le(f,2,2); le(f,16,2);
    fputs("data",f); le(f,2u*FRAMES,4);
    Xeno s; XenoMaterialMemory bank; XenoSampleMorph m;
    xeno_reset(&s,2718,0); xeno_memory_init(&bank); xeno_sample_morph_cancel(&m);
    xeno_memory_store(&bank,0,0,95,0,24);
    xeno_memory_store(&bank,1,2,55,8,120);
    /* Four seconds from either extreme; final two seconds retain final patch. */
    if(!xeno_sample_morph_arm(&m,&s,&bank,arm==2?127:0,arm==1?127:0,800)) {
        fclose(f); return 0;
    }
    const unsigned notes[]={45,52,57,48,55,60,50,45,57,52};
    int16_t pcm[XENO_MORPH_QUANTUM]; unsigned peak=0, nonzero=0, tail=0;
    for(unsigned k=0;k<1200;++k) {
        if(k<1000 && k%100==0) xeno_strike(&s,notes[k/100],100+(k/100)%3*10);
        if(k<1000 && k%100==70) xeno_release(&s);
        if(k==1000) { xeno_sample_morph_cancel(&m); xeno_panic(&s); }
        xeno_sample_morph_render(&m,&s,pcm,XENO_MORPH_QUANTUM);
        for(unsigned i=0;i<XENO_MORPH_QUANTUM;++i) {
            unsigned mag=(unsigned)abs((int)pcm[i]);
            if(mag>peak)peak=mag;
            if(mag) { ++nonzero; if(k>=1000)++tail; }
            le(f,(uint16_t)pcm[i],2);
        }
    }
    int bad=ferror(f); if(fclose(f)!=0)bad=1;
    printf("arm %u peak %u nonzero %u tail_nonzero %u\n",arm,peak,nonzero,tail);
    return !bad && peak>100 && peak<24000 && nonzero>1000 && !tail;
}
int main(int argc,char **argv) {
    if(argc!=4) { fputs("usage: morph-demo fixed.wav forward.wav reverse.wav\n",stderr); return 2; }
    for(unsigned i=0;i<3;++i) if(!render(argv[i+1],i))return 1;
    return 0;
}
