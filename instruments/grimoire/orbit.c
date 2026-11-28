#include "orbit.h"
#include <string.h>
/* Original bounded fixed-point orbit: carrier and two detuned satellites.
 * Phase wraps by unsigned arithmetic; signal intermediates fit int32_t. */
static int32_t tri(uint32_t phase) {
    uint32_t t=phase>>16;
    return (int32_t)(t<32768u?t:65535u-t)*2-32767;
}
static unsigned clamp7(unsigned v){return v>127u?127u:v;}
void orbit_reset(Orbit *s,unsigned preset){
    memset(s,0,sizeof(*s));s->preset=(uint8_t)(preset<3u?preset:0u);
    s->x=48;s->y=70;
    s->phase[1]=0x40000000u;s->phase[2]=0x90000000u;
}
void orbit_xy(Orbit *s,unsigned x,unsigned y){s->x=(uint8_t)clamp7(x);s->y=(uint8_t)clamp7(y);}
void orbit_gate(Orbit *s,unsigned on){s->gate=(uint8_t)(on!=0);}
void orbit_panic(Orbit *s){s->gate=0;s->env=0;s->energy=0;s->low=0;}
void orbit_render(Orbit *s,int16_t *out,size_t n){
    /* 65.4..246.9 Hz, chromatic pitch lattice at 24kHz. */
    static const uint32_t inc[24]={11704839u,12400858u,13138248u,13919321u,14747295u,15624121u,16553262u,17537478u,18580344u,19685241u,20855441u,22095721u,23409778u,24801716u,26276596u,27838721u,29494390u,31248242u,33106524u,35074956u,37160688u,39370482u,41710882u,44191442u};
    const uint32_t f=inc[(unsigned)s->x*23u/127u];
    const unsigned y=s->y,p=s->preset;
    const uint32_t a=p==0?96u:p==1?220u:40u;
    const uint32_t d=p==0?19u:p==1?44u:11u;
    for(size_t i=0;i<n;i++){
        if(s->gate){s->env=s->env>32767u-a?32767u:s->env+a;}
        else{s->env=s->env>d?s->env-d:0u;}
        const int32_t m=tri(s->phase[2]);
        const int32_t depth=(m*(int32_t)y)/128;
        /* The signed offset is converted before modular phase addition. */
        const uint32_t off=(uint32_t)depth*4096u;
        const int32_t c=tri(s->phase[0]+off);
        const int32_t b=tri(s->phase[1]-off);
        int32_t raw;
        if(p==0) raw=(c*3+b*2+m)/6;
        else if(p==1) raw=(c+b)/2 + (c*b)/65536;
        else raw=(c*2+b+m*3)/6;
        const int32_t cut=(int32_t)(8u+y/2u);
        s->low+=(raw-s->low)*cut/128;
        int32_t z=s->low*(int32_t)s->env/32768;
        z=z>28000?28000:z<-28000?-28000:z;
        out[i]=(int16_t)z;
        s->energy=(s->energy*31u+(uint32_t)(z<0?-z:z))/32u;
        s->phase[0]+=f;
        s->phase[1]+=p==1?f*2u+f/97u:p==2?f/2u+f/173u:f+f/53u;
        s->phase[2]+=p==2?f/3u:f/2u+f/113u;
        s->ticks++;
    }
}
