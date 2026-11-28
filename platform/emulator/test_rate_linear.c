/* Host-only comparison fixture. Optional raw native-endian int16 PCM conversion:
 * test_rate_linear hold|linear input.raw output.raw (input frames multiple of 80). */
#include "rate_linear.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

typedef struct { uint32_t calls; int16_t constant; int alternate; } Source;
static int16_t generate(void *ctx) {
    Source *s=ctx;
    uint32_t index=s->calls++;
    return s->alternate ? (index&1u ? INT16_MIN : INT16_MAX) : s->constant;
}
static int16_t read_sample(void *ctx) {
    int16_t x;
    if(fread(&x,sizeof x,1,ctx)!=1) { fputs("short source\n",stderr); exit(2); }
    return x;
}
static int convert(const char *mode,const char *input,const char *output) {
    FILE *in=fopen(input,"rb"),*out=NULL;
    if(!in) return 2;
    if(fseek(in,0,SEEK_END)) { fclose(in); return 2; }
    long bytes=ftell(in);
    if(bytes<=0 || bytes%160 || fseek(in,0,SEEK_SET)) { fclose(in); return 2; }
    out=fopen(output,"wb");
    if(!out) { fclose(in); return 2; }
    VwRate hold; VwRateLinear linear;
    vw_rate_clear(&hold); vw_linear_clear(&linear);
    for(long i=0;i<bytes/160;i++) for(unsigned j=0;j<147;j++) {
        int16_t x=strcmp(mode,"hold")==0 ? vw_rate_step(&hold,read_sample,in) : vw_linear_step(&linear,read_sample,in);
        if(fwrite(&x,sizeof x,1,out)!=1) { fclose(in); fclose(out); return 2; }
    }
    int extra=fgetc(in),err=ferror(in); fclose(in);
    return fclose(out)||extra!=EOF||err ? 2 : 0;
}
int main(int argc,char **argv) {
    if(argc==4 && (!strcmp(argv[1],"hold")||!strcmp(argv[1],"linear"))) return convert(argv[1],argv[2],argv[3]);
    if(argc!=1) return 2;
    VwRate h; VwRateLinear l;
    Source a={0,0,1},b=a;
    vw_rate_clear(&h); vw_linear_clear(&l);
    for(unsigned i=0;i<441000;i++) {
        int16_t x=vw_rate_step(&h,generate,&a), y=vw_linear_step(&l,generate,&b);
        assert(a.calls==b.calls && h.phase==l.phase && h.valid==l.valid);
        int16_t other=l.previous;
        assert(y>=(x<other?x:other) && y<=(x>other?x:other));
    }
    assert(a.calls==240000 && b.calls==240000);
    for(int value=-32768;value<=32767;value+=32767) {
        b=(Source){0,(int16_t)value,0}; vw_linear_clear(&l);
        for(unsigned i=0;i<147;i++) {
            int16_t y=vw_linear_step(&l,generate,&b);
            if(i>=2) assert(y==value);
        }
        assert(b.calls==80);
    }
    b=(Source){0,0,0}; vw_linear_clear(&l);
    for(unsigned i=0;i<147;i++) assert(vw_linear_step(&l,generate,&b)==0);
    assert(b.calls==80);
    printf("PASS 441000 clock/bounds samples, DC extrema, clear silence; hold=%zu linear=%zu bytes\n",sizeof h,sizeof l);
    return 0;
}
