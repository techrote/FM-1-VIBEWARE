#include "xeno.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static void u16(FILE*f,unsigned v){fputc(v&255u,f);fputc((v>>8)&255u,f);}
static void u32(FILE*f,uint32_t v){u16(f,v&65535u);u16(f,v>>16);}
static void header(FILE*f,unsigned n){fwrite("RIFF",1,4,f);u32(f,36u+2u*n);fwrite("WAVEfmt ",1,8,f);u32(f,16);u16(f,1);u16(f,1);u32(f,XENO_RATE);u32(f,XENO_RATE*2);u16(f,2);u16(f,16);fwrite("data",1,4,f);u32(f,n*2u);}
static int arg(const char*s,unsigned max,unsigned*out){char*end;unsigned long v;if(!*s||*s<'0'||*s>'9')return 0;v=strtoul(s,&end,10);if(*end||v>max)return 0;*out=(unsigned)v;return 1;}
int main(int argc,char **argv){
    unsigned p,e,d,c,n,v;int phrase=0;Xeno s;FILE*f;
    if(argc!=8&&argc!=9){fprintf(stderr,"usage: render WAV material excitation damping coupling note velocity [phrase]\n");return 2;}
    if(!arg(argv[2],3,&p)||!arg(argv[3],127,&e)||!arg(argv[4],127,&d)||!arg(argv[5],127,&c)||!arg(argv[6],84,&n)||n<36||!arg(argv[7],127,&v)||(argc==9&&strcmp(argv[8],"phrase")))return 2;
    phrase=argc==9;unsigned count=XENO_RATE*(phrase?6u:2u);f=fopen(argv[1],"wb");if(!f)return 3;
    header(f,count);xeno_reset(&s,42,p);xeno_controls(&s,e,d,c);
    static const unsigned notes[]={0,7,12,3,10,0};
    for(unsigned i=0;i<count;i++){
        if(i%XENO_RATE==0&&(phrase||i==0)){unsigned note=n+notes[i/XENO_RATE];xeno_strike(&s,note,v);}
        if(i%XENO_RATE==XENO_RATE*3u/4u)xeno_release(&s);
        int16_t sample;xeno_render(&s,&sample,1);u16(f,(uint16_t)sample);
    }
    int failed=ferror(f);if(fclose(f)||failed)return 4;return 0;
}
