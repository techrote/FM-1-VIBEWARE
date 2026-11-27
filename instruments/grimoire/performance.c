/* Instrument-local sustained gesture witness; not a device transport. */
#include "../../companion/grimoire/session.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#define BLOCK 1200u
#define FRAMES (ORBIT_RATE*12u)
static int16_t phrase[FRAMES], repeat[FRAMES];
static void event(OrbitSession *s, unsigned op, unsigned a, unsigned b){
    assert(os_event(s,s->generation,op,a,b));
}
static void silent(const int16_t *a,size_t n){for(size_t i=0;i<n;i++)assert(a[i]==0);}
static void lattice(void){
    OrbitSession s;os_init(&s);assert(os_connect(&s,1));
    int16_t a[BLOCK],b[BLOCK];
    for(unsigned p=0;p<3;p++){
        event(&s,ORBIT_PRESET,p,0);event(&s,ORBIT_GATE,1,0);
        os_render(&s,a,BLOCK*1u);assert(s.core.env==32767);
        uint32_t last=0;unsigned distinct=0;
        for(unsigned x=0;x<128;x++){
            Orbit before=s.core;
            event(&s,ORBIT_XY,x,70);
            assert(s.core.gate==1 && s.core.env==before.env && s.core.ticks==before.ticks);
            assert(!memcmp(s.core.phase,before.phase,sizeof(before.phase)));
            os_render(&s,a,1);
            uint32_t step=s.core.phase[0]-before.phase[0];
            assert(step>=last && step>0);if(step!=last)distinct++;
            if(x && x*23u/127u==(x-1)*23u/127u)assert(step==last);
            else assert(step>last);
            last=step;assert(s.core.env==32767);
        }
        assert(distinct==24);
        OrbitSession low=s,high=s;
        event(&low,ORBIT_XY,64,0);event(&high,ORBIT_XY,64,127);
        os_render(&low,a,BLOCK);os_render(&high,b,BLOCK);
        unsigned changed=0;for(unsigned i=0;i<BLOCK;i++)changed+=a[i]!=b[i];
        assert(changed>BLOCK/2 && !memcmp(low.core.phase,high.core.phase,sizeof(low.core.phase)));
        assert(low.core.env==high.core.env && low.core.gate && high.core.gate);
        printf("preset %u: 24 pitches, 128 held XY updates, material changed %u/%u samples\n",p,changed,BLOCK);
        event(&s,ORBIT_PANIC,0,0);os_render(&s,a,BLOCK);silent(a,BLOCK);
    }
}
static void render(int16_t *out){
    static const unsigned notes[8]={24,48,72,60,96,72,48,36};
    OrbitSession s;os_init(&s);assert(os_connect(&s,1));
    for(unsigned p=0;p<3;p++){
        event(&s,ORBIT_PRESET,p,0);assert(!s.core.gate && !s.core.env);
        event(&s,ORBIT_XY,notes[0],20);event(&s,ORBIT_GATE,1,0);
        for(unsigned k=0;k<80;k++){
            if(k<64 && k%8==0)event(&s,ORBIT_XY,notes[(k/8+p)%8],20+(k*7+p*23)%108);
            if(k==64)event(&s,ORBIT_GATE,0,0);
            if(k==76)event(&s,ORBIT_PANIC,0,0);
            int16_t *dst=out+(p*80u+k)*BLOCK;
            os_render(&s,dst,BLOCK);
            if(k>=68)silent(dst,BLOCK);
        }
    }
}
static void u16(FILE *f,uint32_t n){fputc((int)(n&255),f);fputc((int)((n>>8)&255),f);}
static void u32(FILE *f,uint32_t n){u16(f,n);u16(f,n>>16);}
static void wav(const char *path){
    FILE *f=fopen(path,"wb");assert(f);
    fwrite("RIFF",1,4,f);u32(f,36+FRAMES*2);fwrite("WAVEfmt ",1,8,f);u32(f,16);
    u16(f,1);u16(f,1);u32(f,ORBIT_RATE);u32(f,ORBIT_RATE*2);u16(f,2);u16(f,16);
    fwrite("data",1,4,f);u32(f,FRAMES*2);
    for(unsigned i=0;i<FRAMES;i++)u16(f,(uint16_t)phrase[i]);
    assert(!ferror(f));assert(fclose(f)==0);
}
int main(int argc,char **argv){
    lattice();render(phrase);render(repeat);assert(!memcmp(phrase,repeat,sizeof(phrase)));
    unsigned peak=0,nonzero=0;
    for(unsigned i=0;i<FRAMES;i++){unsigned v=(unsigned)abs(phrase[i]);if(v>peak)peak=v;nonzero+=v!=0;}
    assert(peak>1000 && peak<=28000 && nonzero>ORBIT_RATE*8);
    printf("Orbit Gate passage: %u frames, %u nonzero, peak %u; deterministic repeat PASS\n",FRAMES,nonzero,peak);
    if(argc==2)wav(argv[1]);
    return 0;
}
