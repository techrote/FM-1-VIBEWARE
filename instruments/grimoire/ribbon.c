/* Orbit Ribbon: instrument-local gesture automation, no wire or gate ownership.
 * A 50 Hz caller supplies one tick. 256 phase units, 8 linear segments;
 * speed 1/2/4 gives periods 5.12/2.56/1.28 s at that illustrative host rate.
 * Manual override leaves the loop clock running; release blends over 8 ticks.
 * Only XY is generated. The caller must own gate, panic and session lifetime. */
#include "../../companion/grimoire/session.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#define BLOCK 480u
#define TICKS 300u
#define FRAMES (3u*TICKS*BLOCK)
typedef struct { unsigned phase,speed,manual,blend,x,y,from_x,from_y; } Ribbon;
static const unsigned path[8][2]={{24,18},{48,48},{84,110},{108,76},{72,26},{36,98},{12,120},{36,46}};
static void ribbon_init(Ribbon *r){*r=(Ribbon){.speed=1,.x=24,.y=18};}
static int ribbon_speed(Ribbon *r,unsigned speed){
    if(speed!=1 && speed!=2 && speed!=4)return 0;
    r->speed=speed;return 1;
}
static int ribbon_manual(Ribbon *r,unsigned x,unsigned y){
    if(x>127 || y>127)return 0;
    r->manual=1;r->blend=0;r->x=x;r->y=y;return 1;
}
static void ribbon_resume(Ribbon *r){
    if(r->manual){r->manual=0;r->blend=8;r->from_x=r->x;r->from_y=r->y;}
}
static unsigned lerp(unsigned a,unsigned b,unsigned n,unsigned d){return (a*(d-n)+b*n+d/2)/d;}
static void ribbon_tick(Ribbon *r){
    unsigned i=r->phase/32u,k=r->phase%32u,j=(i+1u)%8u;
    unsigned x=lerp(path[i][0],path[j][0],k,32),y=lerp(path[i][1],path[j][1],k,32);
    if(!r->manual){
        if(r->blend){unsigned n=9u-r->blend;r->x=lerp(r->from_x,x,n,8);r->y=lerp(r->from_y,y,n,8);r->blend--;}
        else{r->x=x;r->y=y;}
    }
    r->phase=(r->phase+r->speed)%256u;
}
static void event(OrbitSession *s,unsigned op,unsigned a,unsigned b){assert(os_event(s,s->generation,op,a,b));}
static void test_ribbon(void){
    Ribbon r; ribbon_init(&r);
    for(unsigned k=0;k<256;k++){assert(r.phase==k);ribbon_tick(&r);assert(r.x<=127 && r.y<=127);}
    assert(r.phase==0);ribbon_tick(&r);assert(r.x==24 && r.y==18);
    assert(!ribbon_speed(&r,0) && !ribbon_speed(&r,3));assert(!ribbon_manual(&r,128,0));
    assert(ribbon_speed(&r,4));unsigned phase=r.phase;
    assert(ribbon_manual(&r,127,0));for(unsigned k=0;k<20;k++){ribbon_tick(&r);assert(r.x==127 && r.y==0);}
    assert(r.phase==(phase+80)%256);ribbon_resume(&r);
    for(unsigned k=0;k<8;k++){ribbon_tick(&r);assert(r.blend==7-k && r.x<=127 && r.y<=127);}
    Ribbon a=r,b=r;assert(ribbon_manual(&a,0,127));ribbon_tick(&a);ribbon_tick(&b);assert(a.phase==b.phase);
    ribbon_resume(&a);for(unsigned k=0;k<8;k++){ribbon_tick(&a);ribbon_tick(&b);}assert(a.x==b.x && a.y==b.y);
}
static int16_t dynamic[FRAMES], baseline[FRAMES], repeat[FRAMES];
static void render(int16_t *pcm,int frozen,int split,FILE *trace){
    OrbitSession s;os_init(&s);assert(os_connect(&s,1));
    for(unsigned p=0;p<3;p++){
        Ribbon r;ribbon_init(&r);event(&s,ORBIT_PRESET,p,0);event(&s,ORBIT_GATE,1,0);
        for(unsigned k=0;k<TICKS;k++){
            if(k==80)assert(ribbon_speed(&r,2));
            if(k==160)assert(ribbon_speed(&r,4));
            if(k==100)assert(ribbon_manual(&r,60,40));
            if(k==130)ribbon_resume(&r);
            if(k==260)event(&s,ORBIT_GATE,0,0);
            if(k==280)event(&s,ORBIT_PANIC,0,0);
            unsigned phase=r.phase;ribbon_tick(&r);
            unsigned y=frozen && !r.manual ? 40 : r.y;
            Orbit before=s.core;event(&s,ORBIT_XY,r.x,y);
            assert(!memcmp(before.phase,s.core.phase,sizeof(before.phase)) && before.env==s.core.env && before.gate==s.core.gate && before.ticks==s.core.ticks);
            int16_t *dst=pcm+(p*TICKS+k)*BLOCK;
            if(split){os_render(&s,dst,113);os_render(&s,dst+113,BLOCK-113);}else os_render(&s,dst,BLOCK);
            unsigned peak=0;for(unsigned i=0;i<BLOCK;i++){unsigned a=dst[i]<0?(unsigned)(-(int)dst[i]):(unsigned)dst[i];if(a>peak)peak=a;}
            assert(peak<=28000 && s.core.env<=32767 && s.core.energy<=28000);
            if(k>=280)assert(peak==0 && !s.core.env && !s.core.energy && !s.core.gate);
            if(trace)fprintf(trace,"%u,%u,%u,%u,%u,%u,%u,%u,%u,%u,%u\n",(p*TICKS+k+1)*BLOCK,p,phase,r.speed,r.manual,r.blend,s.core.x,s.core.y,s.core.gate,s.core.env,peak);
        }
    }
    os_disconnect(&s);assert(os_connect(&s,1)==2);assert(!os_event(&s,1,ORBIT_GATE,1,0));
    int16_t tail[BLOCK];os_render(&s,tail,BLOCK);for(unsigned i=0;i<BLOCK;i++)assert(!tail[i]);
}
static void u16(FILE *f,unsigned n){fputc((int)(n&255),f);fputc((int)((n>>8)&255),f);}
static void u32(FILE *f,unsigned n){u16(f,n);u16(f,n>>16);}
static void wav(const char *name,const int16_t *pcm){
    FILE *f=fopen(name,"wb");assert(f);fwrite("RIFF",1,4,f);u32(f,36+FRAMES*2);fwrite("WAVEfmt ",1,8,f);u32(f,16);
    u16(f,1);u16(f,1);u32(f,ORBIT_RATE);u32(f,ORBIT_RATE*2);u16(f,2);u16(f,16);fwrite("data",1,4,f);u32(f,FRAMES*2);
    for(unsigned i=0;i<FRAMES;i++){u16(f,(uint16_t)pcm[i]);}assert(!ferror(f));assert(fclose(f)==0);
}
int main(int argc,char **argv){
    assert(argc==1 || argc==4);test_ribbon();FILE *trace=NULL;
    if(argc==4){trace=fopen(argv[3],"wb");assert(trace);fputs("end_sample,preset,loop_phase,speed,manual,blend_remaining,x,y,gate,env,peak\n",trace);}
    render(dynamic,0,0,trace);if(trace){assert(!ferror(trace));assert(fclose(trace)==0);}
    render(repeat,0,1,NULL);assert(!memcmp(dynamic,repeat,sizeof(dynamic)));render(baseline,1,0,NULL);
    for(unsigned p=0;p<3;p++){
        unsigned changed=0,nonzero=0;for(unsigned i=0;i<TICKS*BLOCK;i++){
            unsigned j=p*TICKS*BLOCK+i;changed+=dynamic[j]!=baseline[j];nonzero+=dynamic[j]!=0;
        }
        assert(changed>TICKS*BLOCK/2 && nonzero>TICKS*BLOCK/2);
        printf("preset %u: %u/%u changed vs fixed Y; %u nonzero\n",p,changed,TICKS*BLOCK,nonzero);
    }
    if(argc==4){wav(argv[1],dynamic);wav(argv[2],baseline);}
    puts("PASS: ribbon bounds, manual takeover, 8-tick pickup, phase continuity, partition identity, panic and stale reconnect");return 0;
}
