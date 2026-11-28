#include "ecophon.h"
#include <string.h>
static uint32_t rnd(Eco *e) { uint32_t x=e->rng; x^=x<<13; x^=x>>17; x^=x<<5; return e->rng=x; }
static unsigned min(unsigned a,unsigned b){return a<b?a:b;}
static unsigned clamp(unsigned x){return min(x,255u);}
static const uint32_t pitches[16]={19685267u,23409932u,26276691u,29495347u,35076406u,39370534u,46819864u,52553382u,58990694u,70152812u,78741068u,93639728u,105106764u,117981388u,140305624u,157482136u};
static void spawn(Eco *e,unsigned i,unsigned patch,unsigned species,unsigned trait,unsigned energy){EcoAgent *a=&e->a[i]; memset(a,0,sizeof *a); a->alive=1; a->patch=(uint8_t)patch; a->species=(uint8_t)species; a->trait=(uint8_t)trait; a->energy=(uint16_t)energy; a->phase=rnd(e); a->inc=pitches[trait];}
void eco_controls(Eco *e,unsigned f,unsigned s,unsigned p,unsigned ab){e->fertility=(uint8_t)clamp(f);e->sharing=(uint8_t)clamp(s);e->pressure=(uint8_t)clamp(p);e->ablation=(uint8_t)(ab!=0);}
void eco_reset(Eco *e,uint32_t seed,unsigned preset){memset(e,0,sizeof *e);e->rng=seed?seed:1u;e->regime=(uint8_t)(preset%3u);if(e->regime==0)eco_controls(e,180,200,40,0);else if(e->regime==1)eco_controls(e,100,20,150,0);else eco_controls(e,230,90,85,0);for(unsigned p=0;p<ECO_PATCHES;++p)e->resource[p]=2000;for(unsigned i=0;i<5;++i)spawn(e,i,i%4,i%2,(i*3u)%16u,900u+i*180u);}
void eco_mute(Eco *e,unsigned mute){e->muted=(uint8_t)(mute!=0);}
static void tick(Eco *e){
    ++e->ticks;
    for(unsigned p=0;p<ECO_PATCHES;++p){unsigned sun=6u+e->fertility/4u; if(e->regime==2 && ((e->ticks/100u+p)%4u)==0) sun*=3u; e->resource[p]=(uint16_t)min(ECO_CAP,e->resource[p]+sun);}
    if(e->ablation)return;
    for(unsigned k=0;k<ECO_AGENTS;++k){unsigned i=(k+e->ticks)%ECO_AGENTS;EcoAgent *a=&e->a[i];if(!a->alive)continue;
        unsigned p=a->patch, dest=(p+1u+(rnd(e)%3u))%ECO_PATCHES;
        if(e->resource[dest]>e->resource[p]+200u && (rnd(e)&255u)<80u){a->patch=(uint8_t)dest;p=dest;++e->moves;}
        unsigned take=min(e->resource[p],24u+2u*a->trait+8u*a->species);e->resource[p]=(uint16_t)(e->resource[p]-take);e->consumed+=take;
        unsigned gross=min(ECO_CAP,a->energy+take),cost=20u+e->pressure/5u+3u*a->species;
        a->energy=(uint16_t)(gross>cost?gross-cost:0u);if(a->age<65535u)++a->age;
        if(!a->energy){a->alive=0;++e->deaths;continue;}
        if(a->energy>900u && (rnd(e)&255u)<e->sharing){for(unsigned j=0;j<ECO_AGENTS;++j){EcoAgent *b=&e->a[j];if(j!=i && b->alive && b->patch==p && b->energy+250u<a->energy){unsigned gift=min(80u,(a->energy-b->energy)/4u);a->energy=(uint16_t)(a->energy-gift);b->energy=(uint16_t)min(ECO_CAP,b->energy+gift);++e->gifts;break;}}}
        if(a->energy>2500u && a->age>100u && (rnd(e)&255u)<20u){for(unsigned j=0;j<ECO_AGENTS;++j){if(!e->a[j].alive && e->a[j].envelope==0u){unsigned trait=(a->trait+15u+(rnd(e)%3u))%16u; a->energy=(uint16_t)(a->energy-1000u);spawn(e,j,p,a->species,trait,1000u);++e->births;break;}}}
    }
    /* A seed bank prevents permanent extinction; it consumes patch resources. */
    unsigned alive=0;for(unsigned i=0;i<ECO_AGENTS;++i)alive+=e->a[i].alive;
    if(!alive && e->resource[0]>=1000u && !e->a[0].envelope){e->resource[0]-=1000u;unsigned species=rnd(e)%2u;unsigned trait=rnd(e)%16u;spawn(e,0,0,species,trait,1000u);++e->births;}
}
void eco_render(Eco *e,int16_t *out,size_t frames){for(size_t n=0;n<frames;++n){if(!e->countdown){tick(e);e->countdown=ECO_TICK;}--e->countdown;int32_t mix=0;for(unsigned i=0;i<ECO_AGENTS;++i){EcoAgent *a=&e->a[i];unsigned target=a->alive?min(3000u,a->energy):0u;unsigned env=a->envelope;if(env<target)env+=min(8u,target-env);else if(env>target)env-=min(8u,env-target);a->envelope=(uint16_t)env;uint32_t inc=a->inc;if(a->alive && !e->ablation)inc+=(inc/4096u)*(e->resource[a->patch]/128u);
        a->phase+=inc;unsigned q=a->phase>>16;int32_t tri=(q<32768u?(int32_t)q:(int32_t)(65535u-q))*2-32767;int32_t wave=a->species?(tri*3+(q<16384u?32767:-32767))/4:tri;mix+=wave*(int32_t)env/32768;}
    out[n]=e->muted?0:(int16_t)mix;
}}
