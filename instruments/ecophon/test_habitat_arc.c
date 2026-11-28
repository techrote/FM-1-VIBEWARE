#include "habitat_arc.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

#define TOTAL (ECO_ARC_FRAMES*ECO_ARC_BLOCKS)
#define TAIL 777u
static int16_t actual[TOTAL+TAIL], expected[TOTAL+TAIL];

/* Independent block-clock score oracle: signed interpolation with floor of
 * the weighted result, not truncation of a negative delta. */
static unsigned blend(unsigned x,unsigned y,unsigned i) {
    int numerator=(int)x*40+((int)y-(int)x)*(int)i;
    return (unsigned)(numerator/40);
}
static void oracle(Eco *e) {
    const unsigned origin[3]={e->fertility,e->sharing,e->pressure};
    const unsigned base[3]={180,200,40}, dry[3]={0,0,255}, wet[3]={255,220,0};
    for(unsigned i=0;i<ECO_ARC_BLOCKS;++i) {
        unsigned v[3];
        for(unsigned k=0;k<3;++k) {
            if(i<40) v[k]=blend(origin[k],base[k],i+1);
            else if(i<80) v[k]=blend(base[k],dry[k],i-39);
            else if(i<120) v[k]=dry[k];
            else if(i<160) v[k]=blend(dry[k],wet[k],i-119);
            else v[k]=wet[k];
        }
        eco_controls(e,v[0],v[1],v[2],0);
        eco_render(e,expected+i*ECO_ARC_FRAMES,ECO_ARC_FRAMES);
    }
    eco_render(e,expected+TOTAL,TAIL);
}
static uint32_t trace=2166136261u;
static void compare(unsigned seed,unsigned preset,unsigned warmup) {
    Eco a,b; EcoArc arc={0}; int16_t scratch[241];
    eco_reset(&a,seed,preset);
    eco_controls(&a,(seed*17u)&255u,(seed*29u)&255u,(seed*31u)&255u,0);
    if(warmup) eco_render(&a,scratch,warmup);
    memcpy(&b,&a,sizeof b);
    assert(eco_arc_arm(&arc,&a));
    assert(arc.completed==0 && arc.remaining==0);
    eco_arc_render(&arc,&a,scratch,0);
    assert(memcmp(&a,&b,sizeof a)==0);
    oracle(&b);
    const unsigned sizes[]={1,256,2399,257,4801,113,2400,64};
    size_t pos=0; unsigned k=0;
    while(pos<TOTAL+TAIL) {
        size_t n=sizes[k++%8];
        if(n>TOTAL+TAIL-pos) n=TOTAL+TAIL-pos;
        eco_arc_render(&arc,&a,actual+pos,n);
        pos+=n;
        assert(arc.completed==(pos<TOTAL?pos/ECO_ARC_FRAMES:ECO_ARC_BLOCKS));
        assert((arc.active!=0)==(pos<TOTAL));
    }
    assert(!memcmp(actual,expected,sizeof actual));
    assert(!memcmp(&a,&b,sizeof a));
    assert(a.fertility==255 && a.sharing==220 && a.pressure==0);
    unsigned sounding=0;
    for(size_t i=0;i<TOTAL+TAIL;++i) {
        uint16_t s=(uint16_t)actual[i]; sounding+=s!=0;
        trace=(trace^(s&255u))*16777619u; trace=(trace^(s>>8))*16777619u;
    }
    assert(sounding>0);
}
static void lifecycle(void) {
    Eco a,b; EcoArc arc={0}; int16_t x[256],y[256];
    eco_reset(&a,42,0);
    assert(eco_arc_arm(&arc,&a));
    eco_arc_render(&arc,&a,x,17);
    assert(arc.active && arc.remaining==ECO_ARC_FRAMES-17);
    /* Manual takeover: no delayed cue can overwrite the new environment. */
    eco_arc_cancel(&arc); eco_controls(&a,23,45,67,0); memcpy(&b,&a,sizeof b);
    eco_arc_render(&arc,&a,x,256); eco_render(&b,y,256);
    assert(!memcmp(x,y,sizeof x) && !memcmp(&a,&b,sizeof a));
    assert(eco_arc_arm(&arc,&a)); eco_arc_render(&arc,&a,x,17);
    eco_controls(&a,1,2,3,1); memcpy(&b,&a,sizeof b);
    eco_arc_render(&arc,&a,x,256); eco_render(&b,y,256);
    assert(!arc.active && !eco_arc_arm(&arc,&a));
    assert(!memcmp(x,y,sizeof x) && !memcmp(&a,&b,sizeof a));
    eco_controls(&a,40,50,60,0); assert(eco_arc_arm(&arc,&a));
    eco_arc_render(&arc,&a,x,17); eco_mute(&a,1); eco_arc_render(&arc,&a,x,256);
    assert(!arc.active && !eco_arc_arm(&arc,&a));
    for(unsigned i=0;i<256;++i) assert(x[i]==0);
    eco_mute(&a,0); eco_controls(&a,70,80,90,0); memcpy(&b,&a,sizeof b);
    eco_arc_render(&arc,&a,x,256); eco_render(&b,y,256);
    assert(!memcmp(x,y,sizeof x) && !memcmp(&a,&b,sizeof a));
    /* Explicit fresh arm after panic, then cancel before preset/reset. */
    assert(eco_arc_arm(&arc,&a)); eco_arc_render(&arc,&a,x,17);
    eco_arc_cancel(&arc); eco_reset(&a,99,2); eco_reset(&b,99,2);
    eco_arc_render(&arc,&a,x,256); eco_render(&b,y,256);
    assert(!memcmp(x,y,sizeof x) && !memcmp(&a,&b,sizeof a));
}
int main(void) {
    const unsigned seeds[]={1,42,65535};
    for(unsigned preset=0;preset<3;++preset)
        for(unsigned i=0;i<3;++i) compare(seeds[i],preset,0),compare(seeds[i],preset,241);
    lifecycle();
    printf("PASS 18 full score/continuation PCM+state comparisons, manual/freeze/mute/reset, arc state %zu B, trace %08x\n",sizeof(EcoArc),(unsigned)trace);
    return 0;
}
