#include "native_ribbon.h"
#include <assert.h>
#include <stdio.h>
/* Independent direct-control comparator. The emitted state trace is also
 * compared against the exact browser controller by the Node test. */
static const uint8_t sketch[8][2]={{0,127},{127,0},{30,40},{50,60},{10,20},{70,90},{100,110},{127,127}};
static void unchanged(const GrRibbon *a,const GrRibbon *b){assert(!memcmp(a,b,sizeof(*a)));}
int main(void){
    unsigned sounding=0,blocks=0;
    int16_t pcm[GR_BLOCK],direct[GR_BLOCK];
    for(unsigned preset=0;preset<3;preset++){
        OrbitSession s,t;os_init(&s);os_init(&t);
        uint32_t g=os_connect(&s,1),h=os_connect(&t,1);
        GrRibbon r;gr_init(&r,g);
        GrRibbon old=r;assert(!gr_shape(&r,GR_SKETCH));unchanged(&r,&old);
        assert(gr_sketch(&r,sketch));assert(gr_speed(&r,2));
        assert(os_event(&s,g,ORBIT_PRESET,preset,0));assert(os_event(&t,h,ORBIT_PRESET,preset,0));
        assert(os_event(&s,g,ORBIT_GATE,1,0));assert(os_event(&t,h,ORBIT_GATE,1,0));
        for(unsigned k=0;k<320;k++){
            if(k==40)assert(gr_direction(&r,-1));
            if(k==60)assert(gr_shape(&r,GR_CROWN));
            if(k==80){assert(gr_take(&r,&s,60,40));assert(os_event(&t,h,ORBIT_XY,60,40));}
            if(k==90)gr_resume(&r);
            if(k==110)assert(gr_direction(&r,1));
            if(k==120){assert(gr_shape(&r,GR_PENDULUM));assert(gr_speed(&r,4));}
            if(k==160)assert(gr_shape(&r,GR_SKETCH));
            if(k==180){assert(gr_sketch(&r,sketch));assert(gr_speed(&r,1));}
            if(k==300){assert(gr_panic(&r,&s));assert(os_event(&t,h,ORBIT_PANIC,0,0));}
            old=r;assert(!gr_direction(&r,0));assert(!gr_speed(&r,3));assert(!gr_shape(&r,4));
            assert(!gr_take(&r,&s,128,0));assert(!gr_render(&r,&s,pcm,GR_BLOCK-1));unchanged(&r,&old);
            assert(gr_render(&r,&s,pcm,GR_BLOCK));
            if(r.speed&&!r.manual)assert(os_event(&t,h,ORBIT_XY,r.x,r.y));
            os_render(&t,direct,GR_BLOCK);
            assert(!memcmp(pcm,direct,sizeof(pcm)));assert(!memcmp(&s.core,&t.core,sizeof(s.core)));
            unsigned nz=0;for(unsigned i=0;i<GR_BLOCK;i++)nz|=pcm[i]!=0;
            if(k>=300)assert(!nz);else assert(s.core.gate==1);
            sounding+=nz;blocks++;
            printf("%u,%u,%u,%u,%u,%u,%u,%u,%u,%d\n",preset,k,r.phase,r.carry,r.x,r.y,r.manual,r.blend,r.shape,r.direction);
        }
        old=r;os_disconnect(&s);memset(pcm,0x5a,sizeof(pcm));
        assert(!gr_render(&r,&s,pcm,GR_BLOCK));assert(!gr_take(&r,&s,1,1));unchanged(&r,&old);
        assert(os_connect(&s,1)!=g);assert(!gr_render(&r,&s,pcm,GR_BLOCK));unchanged(&r,&old);
        for(unsigned i=0;i<GR_BLOCK;i++)assert(pcm[i]==0x5a5a);
        assert(!s.core.gate&&!s.core.env);
    }
    assert(sounding==900);
    fprintf(stderr,"PASS: %u PCM/state blocks, %u sounding, %u silent; controller %zu bytes\n",blocks,sounding,blocks-sounding,sizeof(GrRibbon));
    return 0;
}
