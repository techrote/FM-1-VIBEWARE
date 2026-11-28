/* Local audition fixture, not a device transport or a shared ABI. */
#include "ecophon.h"
#include "environment_memory.h"
#define FRAMES 2400
#define WORDS (12+ECO_PATCHES+5*ECO_AGENTS)
static Eco model;
static EcoMemory memory;
void ecof_reset(uint32_t seed, unsigned preset) {
    eco_reset(&model,seed,preset);
    if(preset==3) eco_controls(&model,model.fertility,model.sharing,model.pressure,1);
    eco_memory_reset(&memory,(EcoEnvironment){model.fertility,model.sharing,model.pressure});
    eco_memory_freeze(&memory,model.ablation);
}
void ecof_panic(void) { eco_memory_stop(&memory); eco_mute(&model,1); }
static int render_step(unsigned f,unsigned s,unsigned p,unsigned ab,int16_t *pcm,uint32_t *snap) {
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
int ecof_step(unsigned f,unsigned s,unsigned p,unsigned ab,int16_t *pcm,uint32_t *snap) {
    if(f>255 || s>255 || p>255 || ab>1 || !pcm || !snap) return 0;
    eco_memory_manual(&memory,f,s,p);
    eco_memory_freeze(&memory,ab);
    return render_step(f,s,p,ab,pcm,snap);
}
/* Optional local single-owner consumer. Direct step overrides an active recall.
 * Callers must serialize requests and enforce their own session generations. */
int ecof_memory_capture(unsigned slot) {
    return memory.running && eco_memory_capture(&memory,slot);
}
int ecof_memory_recall(unsigned slot) { return eco_memory_recall(&memory,slot); }
int ecof_memory_step(int16_t *pcm,uint32_t *snap) {
    if(!memory.running || !pcm || !snap) return 0;
    EcoEnvironment env=eco_memory_next(&memory);
    return render_step(env.f,env.s,env.p,memory.frozen,pcm,snap);
}

/* Read-only local capture receipt; never advances the model. */
int ecof_memory_get(unsigned slot, uint8_t *out) {
    if(slot>=2 || !out || !(memory.valid & (1u<<slot))) return 0;
    out[0]=memory.slots[slot].f;
    out[1]=memory.slots[slot].s;
    out[2]=memory.slots[slot].p;
    return 1;
}
