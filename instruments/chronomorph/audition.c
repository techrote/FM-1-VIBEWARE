#include "chrono.h"
#include <assert.h>
#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static void le(FILE *f,uint32_t x,unsigned n){while(n--){fputc((int)(x&255u),f);x>>=8;}}
static int render(const char *path,cm_state *s,unsigned seconds){
    FILE *f=fopen(path,"wb");if(!f)return 0;uint32_t samples=CM_RATE*seconds;
    fwrite("RIFF",1,4,f);le(f,36+samples*2,4);fwrite("WAVEfmt ",1,8,f);le(f,16,4);le(f,1,2);le(f,1,2);le(f,CM_RATE,4);le(f,CM_RATE*2,4);le(f,2,2);le(f,16,2);fwrite("data",1,4,f);le(f,samples*2,4);
    cm_start(s);for(uint32_t n=0;n<samples;n++){int16_t x;cm_render(s,&x,1);le(f,(uint16_t)x,2);}
    int ok=!ferror(f);return fclose(f)==0&&ok;
}
static void test(void){
    cm_state a,b;int16_t x[257],y[257];uint64_t nonzero=0,diff=0;int peak=0;
    cm_reset(&a,17,0);cm_reset(&b,17,0);cm_start(&a);cm_start(&b);
    for(unsigned i=0;i<2000;i++){
        cm_render(&a,x,257);cm_render(&b,y,1);cm_render(&b,y+1,256);assert(!memcmp(x,y,sizeof x));
        for(unsigned j=0;j<257;j++){int v=x[j];if(v<0)v=-v;if(v>peak)peak=v;nonzero+=v!=0;}
    }
    assert(nonzero>100000&&peak<24000);assert(a.lane[0].ticks==160);
    assert(a.lane[1].ticks!=a.lane[0].ticks||a.lane[1].step!=a.lane[0].step);
    printf("partition: 514000 samples, peak=%d, nonzero=%llu, ticks=%u/%u/%u, state=%zu bytes\n",peak,(unsigned long long)nonzero,a.lane[0].ticks,a.lane[1].ticks,a.lane[2].ticks,sizeof a);
    cm_reset(&a,17,0);cm_reset(&b,17,0);cm_controls(&b,112,0,12);cm_start(&a);cm_start(&b);
    for(unsigned i=0;i<1000;i++){cm_render(&a,x,257);cm_render(&b,y,257);for(unsigned j=0;j<257;j++)diff+=x[j]!=y[j];}assert(diff>10000);
    printf("warp ablation: %llu differing samples / 257000\n",(unsigned long long)diff);
    uint32_t t=a.lane[0].ticks,phase=a.lane[0].clock;assert(cm_controls(&a,220,-60,100));assert(a.lane[0].clock==phase);assert(!cm_controls(&a,221,0,0));
    assert(!cm_pattern(&a,3,4,1));assert(!cm_pattern(&a,0,17,1));assert(!cm_pattern(&a,0,4,16));assert(cm_pattern(&a,0,1,0));
    for(unsigned i=0;i<2000;i++){cm_render(&a,x,257);}assert(a.lane[0].ticks>t);assert(a.lane[0].env==0);
    cm_stop(&a);t=a.lane[0].ticks;cm_render(&a,x,257);for(unsigned j=0;j<257;j++)assert(x[j]==0);assert(a.lane[0].ticks==t);
    cm_start(&a);cm_render(&a,x,257);assert(a.playing);cm_reset(&a,0,2);cm_render(&a,x,257);for(unsigned j=0;j<257;j++)assert(x[j]==0);
    puts("transport, edit, tempo, invalid bounds, mute: PASS");
}
static int num(const char *s,long lo,long hi,long *v){char *end;errno=0;long n=strtol(s,&end,10);if(errno==ERANGE||!*s||*end||n<lo||n>hi)return 0;*v=n;return 1;}
int main(int argc,char **argv){
    if(argc==2&&!strcmp(argv[1],"--test")){test();return 0;}
    if(argc!=15||strcmp(argv[1],"--render")){fputs("--render PATH PRESET SEED BPM WARP VARIATION SECONDS LEN0 MASK0 LEN1 MASK1 LEN2 MASK2\n",stderr);return 2;}
    long p[12];const long lo[]={0,1,40,-60,0,1,1,0,1,0,1,0},hi[]={2,2147483647,220,60,100,20,16,65535,16,65535,16,65535};
    for(unsigned i=0;i<12;i++)if(!num(argv[i+3],lo[i],hi[i],&p[i]))return 2;
    cm_state s;cm_reset(&s,(uint32_t)p[1],(unsigned)p[0]);cm_controls(&s,(unsigned)p[2],(int)p[3],(unsigned)p[4]);
    for(unsigned i=0;i<3;i++)if(!cm_pattern(&s,i,(unsigned)p[6+i*2],(unsigned)p[7+i*2]))return 2;
    if(!render(argv[2],&s,(unsigned)p[5]))return 1;
    for(unsigned i=0;i<3;i++)printf("%u:%u:%u%s",s.lane[i].step,s.lane[i].ticks,s.lane[i].hits,i==2?"\n":" ");
    return 0;
}
