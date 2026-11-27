/* Local audition fixture, not a device transport or a shared ABI. */
#include "ecophon.h"
#define FRAMES 2400
#define WORDS (12+ECO_PATCHES+5*ECO_AGENTS)
static Eco model;
void ecof_reset(uint32_t seed, unsigned preset) {
    eco_reset(&model,seed,preset);
    if(preset==3) eco_controls(&model,model.fertility,model.sharing,model.pressure,1);
}
void ecof_panic(void) { eco_mute(&model,1); }
int ecof_step(unsigned f,unsigned s,unsigned p,unsigned ab,int16_t *pcm,uint32_t *snap) {
    if(f>255 || s>255 || p>255 || ab>1 || !pcm || !snap) return 0;
    eco_controls(&model,f,s,p,ab);
    eco_render(&model,pcm,FRAMES);
    snap[0]=model.ticks; snap[1]=model.births; snap[2]=model.deaths;
    snap[3]=model.gifts; snap[4]=model.moves; snap[5]=model.consumed;
    snap[6]=model.regime; snap[7]=model.ablation; snap[8]=model.muted;
    snap[9]=model.fertility; snap[10]=model.sharing; snap[11]=model.pressure;
    for(unsigned i=0;i<ECO_PATCHES;++i) snap[12+i]=model.resource[i];
    for(unsigned i=0;i<ECO_AGENTS;++i){
        const EcoAgent *a=&model.a[i]; uint32_t *v=snap+16+5*i;
        v[0]=a->alive;v[1]=a->patch;v[2]=a->species;v[3]=a->trait;v[4]=a->energy;
    }
    return WORDS;
}
