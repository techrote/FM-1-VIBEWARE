#include "sample_ribbon.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#define N 24000u
static const uint8_t paths[4][8][2]={
    {{24,18},{48,48},{84,110},{108,76},{72,26},{36,98},{12,120},{36,46}},
    {{24,96},{44,104},{66,112},{88,120},{104,112},{88,104},{66,96},{44,104}},
    {{32,24},{48,30},{80,42},{96,48},{80,42},{48,30},{32,24},{24,30}},
    {{0,127},{127,0},{10,20},{100,120},{15,100},{60,60},{127,127},{0,0}}
};
static int16_t expected[N], actual[N];
static uint32_t trace=2166136261u;
static void oracle(Orbit *s,const uint8_t path[8][2],unsigned speed,int dir) {
    unsigned phase=0,blend=0;int manual=0;unsigned fx=0,fy=0;
    orbit_gate(s,1);
    for(unsigned t=0;t<N;t++){
        if(t==1001){manual=1;orbit_xy(s,91,7);}
        if(t==5107){manual=0;blend=8;fx=s->x;fy=s->y;}
        if(t==8119){speed=4;dir=-dir;}
        if(t==17003)speed=0;
        if(t==19000)orbit_gate(s,0);
        if(t==22000)orbit_panic(s);
        if(speed&&t%480u==0){
            unsigned a=phase/32u,b=(a+1u)%8u,k=phase%32u;
            if(!manual){
                unsigned x=(path[a][0]*(32u-k)+path[b][0]*k+16u)/32u;
                unsigned y=(path[a][1]*(32u-k)+path[b][1]*k+16u)/32u;
                if(blend){x=(fx*(blend-1u)+x*(9u-blend)+4u)/8u;y=(fy*(blend-1u)+y*(9u-blend)+4u)/8u;blend--;}
                orbit_xy(s,x,y);
            }
            phase=(phase+(dir>0?speed:256u-speed))%256u;
        }
        orbit_render(s,expected+t,1);
    }
}
static void compare(unsigned preset,unsigned shape,unsigned speed,int dir,unsigned partition){
    Orbit a,b;orbit_reset(&a,preset);orbit_reset(&b,preset);oracle(&a,paths[shape],speed,dir);
    GrSampleRibbon r={0};uint8_t detached[8][2];memcpy(detached,paths[shape],sizeof(detached));
    assert(grs_arm(&r,(const uint8_t (*)[2])detached,speed,dir));memset(detached,255,sizeof(detached));
    GrSampleRibbon saved=r;assert(!grs_arm(&r,(const uint8_t (*)[2])detached,1,1));assert(!grs_motion(&r,3,1));assert(!memcmp(&r,&saved,sizeof(r)));
    orbit_gate(&b,1);const unsigned boundaries[]={1001,5107,8119,17003,19000,22000,N};unsigned pos=0;
    for(unsigned e=0;e<7;e++){
        while(pos<boundaries[e]){
            unsigned chunk=partition==0?1:partition==1?7919:1+(pos*17u+13u)%997u;
            if(chunk>boundaries[e]-pos)chunk=boundaries[e]-pos;
            grs_render(&r,&b,actual+pos,chunk);pos+=chunk;
            if(e==1)assert(b.x==91&&b.y==7&&b.gate);
        }
        if(e==0){assert(!grs_take(&r,&b,128,0));assert(grs_take(&r,&b,91,7));}
        if(e==1)grs_resume(&r,&b);
        if(e==2)assert(grs_motion(&r,4,-dir));
        if(e==3)grs_cancel(&r);
        if(e==4)orbit_gate(&b,0);
        if(e==5)grs_panic(&r,&b);
    }
    assert(!memcmp(expected,actual,sizeof(actual)));assert(!memcmp(&a,&b,sizeof(a)));
    assert(!r.speed&&!r.remaining&&!b.gate&&!b.env&&!b.energy);
    for(unsigned t=22000;t<N;t++)assert(actual[t]==0);
    for(unsigned t=0;t<N;t++){trace^=(uint16_t)actual[t];trace*=16777619u;}
}
static void u16(FILE *f,unsigned n){fputc((int)(n&255u),f);fputc((int)((n>>8)&255u),f);}
static void u32(FILE *f,uint32_t n){u16(f,n);u16(f,n>>16);}
static void demo(const char *name,int dir){
    FILE *f=fopen(name,"wb");assert(f);const unsigned frames=6u*ORBIT_RATE;
    fwrite("RIFF",1,4,f);u32(f,36u+2u*frames);fwrite("WAVEfmt ",1,8,f);u32(f,16);u16(f,1);u16(f,1);u32(f,ORBIT_RATE);u32(f,ORBIT_RATE*2);u16(f,2);u16(f,16);fwrite("data",1,4,f);u32(f,frames*2);
    Orbit s;orbit_reset(&s,2);GrSampleRibbon r={0};assert(grs_arm(&r,paths[0],2,dir));orbit_gate(&s,1);
    unsigned peak=0,nonzero=0;int16_t pcm[480];
    for(unsigned k=0;k<300;k++){
        if(k==100)assert(grs_motion(&r,4,dir));
        if(k==150)assert(grs_take(&r,&s,60,90));
        if(k==175)grs_resume(&r,&s);
        if(k==225)orbit_gate(&s,0);
        if(k==250)grs_panic(&r,&s);
        grs_render(&r,&s,pcm,480);
        for(unsigned i=0;i<480;i++){
            unsigned m=pcm[i]<0?(unsigned)-(int)pcm[i]:(unsigned)pcm[i];if(m>peak)peak=m;nonzero+=m!=0;
            if(k>=250){assert(m==0);}u16(f,(uint16_t)pcm[i]);
        }
    }
    assert(peak>1000&&peak<=28000&&nonzero>ORBIT_RATE*4);assert(!ferror(f));assert(fclose(f)==0);
    printf("direction %d: %u frames, peak %u, nonzero %u\n",dir,frames,peak,nonzero);
}
int main(int argc,char **argv){
    unsigned count=0;for(unsigned p=0;p<3;p++)for(unsigned h=0;h<4;h++)for(unsigned v=1;v<=4;v*=2)for(int d=-1;d<=1;d+=2)for(unsigned q=0;q<3;q++){compare(p,h,v,d,q);count++;}
    printf("PASS %u full PCM/core-state comparisons, trace %08x, state %zu bytes\n",count,(unsigned)trace,sizeof(GrSampleRibbon));
    assert(argc==1||argc==3);if(argc==3){demo(argv[1],1);demo(argv[2],-1);}return 0;
}
