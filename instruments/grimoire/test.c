#include "orbit.h"
#include "../../companion/grimoire/session.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
static void u16(FILE*f,uint32_t n){fputc((int)(n&255),f);fputc((int)((n>>8)&255),f);}
static void u32(FILE*f,uint32_t n){u16(f,n);u16(f,n>>16);}
static void wav(const char *name,unsigned p){
    FILE*f=fopen(name,"wb");assert(f);
    const unsigned n=ORBIT_RATE*6;
    fwrite("RIFF",1,4,f);u32(f,36+n*2);fwrite("WAVEfmt ",1,8,f);u32(f,16);u16(f,1);u16(f,1);u32(f,ORBIT_RATE);u32(f,ORBIT_RATE*2);u16(f,2);u16(f,16);fwrite("data",1,4,f);u32(f,n*2);
    Orbit s;orbit_reset(&s,p);orbit_gate(&s,1);int16_t b[240];
    for(unsigned k=0;k<n/240;k++){
        if(k%20==0)orbit_xy(&s,20+(k/20*13)%108,(k/20*19)%128);
        if(k==500)orbit_gate(&s,0);
        orbit_render(&s,b,240);for(unsigned i=0;i<240;i++)u16(f,(uint16_t)b[i]);
    }
    assert(fclose(f)==0);
}
int main(int argc,char**argv){
    Orbit s,t;int16_t a[1024],b[1024];uint64_t sum=0;
    for(unsigned p=0;p<3;p++){
        orbit_reset(&s,p);orbit_gate(&s,1);t=s;
        orbit_render(&s,a,1024);orbit_render(&t,b,13);orbit_render(&t,b+13,1011);
        assert(!memcmp(a,b,sizeof(a)));assert(!memcmp(&s,&t,sizeof(s)));
        for(unsigned k=0;k<1024;k++){assert(a[k]>=-28000&&a[k]<=28000);sum+=(uint64_t)abs(a[k]);}
        assert(sum>0);orbit_panic(&s);orbit_render(&s,a,1024);for(unsigned k=0;k<1024;k++)assert(a[k]==0);
        orbit_gate(&s,1);
        for(unsigned k=0;k<2400;k++){orbit_xy(&s,k%128,(k*23)%128);orbit_render(&s,a,1024);}
        orbit_gate(&s,0);for(unsigned k=0;k<4;k++)orbit_render(&s,a,1024);assert(s.env==0);for(unsigned k=0;k<1024;k++)assert(a[k]==0);
    }
    OrbitSession q;os_init(&q);assert(os_connect(&q,2)==0);
    uint32_t g=os_connect(&q,1);assert(g);
    assert(os_event(&q,g,ORBIT_XY,0,127));assert(!os_event(&q,g,ORBIT_XY,128,0));
    assert(os_event(&q,g,ORBIT_GATE,1,0));os_render(&q,a,1024);assert(q.core.env>0);
    os_disconnect(&q);os_render(&q,a,1024);for(unsigned k=0;k<1024;k++)assert(a[k]==0);
    uint32_t h=os_connect(&q,1);assert(h!=g);assert(!os_event(&q,g,ORBIT_GATE,1,0));assert(!q.core.gate);
    assert(os_event(&q,h,ORBIT_PRESET,2,0));assert(os_event(&q,h,ORBIT_GATE,1,0));assert(os_event(&q,h,ORBIT_PANIC,0,0));assert(!q.core.gate);
    if(argc==4){for(unsigned p=0;p<3;p++)wav(argv[p+1],p);}
    printf("Orbit partition/mute/transition/session stress PASS; host state %zu bytes; absolute witness %llu\n",sizeof(Orbit),(unsigned long long)sum);
    return 0;
}
