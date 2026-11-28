/* Host-only single-engine fixture. No target or transport ABI. */
#include "material_memory.h"
#ifdef _WIN32
#define EXPORT __declspec(dllexport)
#else
#define EXPORT
#endif
static Xeno engine;
static XenoMaterialMemory memory;
EXPORT void live_reset(void){xeno_reset(&engine,42,0);}
EXPORT void live_panic(void){xeno_panic(&engine);}
/* Five 10 ms slices; peak sampled modal magnitude within each 50 ms block. */
static void render_block(int16_t *pcm,uint32_t *levels){
    for(unsigned m=0;m<XENO_MODES;m++)levels[m]=0;
    for(unsigned i=0;i<5;i++){
        xeno_render(&engine,pcm+i*240,240);
        for(unsigned m=0;m<XENO_MODES;m++){
            uint32_t level=xeno_mode_level(&engine,m);
            if(level>levels[m])levels[m]=level;
        }
    }
}

EXPORT void live_block(unsigned p,unsigned e,unsigned d,unsigned c,unsigned n,
                       unsigned v,unsigned event,int16_t *pcm,uint32_t *levels){
    xeno_controls(&engine,e,d,c);
    if(engine.material!=p)xeno_material(&engine,p);
    if(event==1)xeno_strike(&engine,n,v);
    else if(event==2)xeno_release(&engine);
    render_block(pcm,levels);
}

/* Local single-owner calls only. A rejected request does not render or touch
 * output buffers. Reset/panic retain user patches; explicit clear erases them. */
EXPORT void live_memory_clear(void){xeno_memory_init(&memory);}
EXPORT int live_memory_store(unsigned slot,unsigned p,unsigned e,unsigned d,unsigned c){
    return xeno_memory_store(&memory,slot,p,e,d,c);
}
EXPORT int live_memory_capture(unsigned slot){return xeno_memory_capture(&memory,slot,&engine);}
EXPORT int live_memory_block(unsigned op,unsigned value,int16_t *pcm,uint32_t *levels){
    if(!pcm || !levels)return 0;
    int accepted=op==0 ? xeno_memory_recall(&memory,value,&engine) :
                 op==1 ? xeno_memory_morph(&memory,value,&engine) : 0;
    if(!accepted)return 0;
    render_block(pcm,levels);
    return 1;
}

/* Read actual local native patch: slot 0/1, or current engine patch (2). */
EXPORT int live_memory_read(unsigned slot,uint32_t *out){
    if(!out || slot>2u)return 0;
    XenoMaterialPatch patch;
    if(slot==2u)patch=(XenoMaterialPatch){engine.material,engine.excitation,engine.damping,engine.coupling};
    else {
        if(!(memory.valid & (1u<<slot)))return 0;
        patch=memory.slot[slot];
    }
    out[0]=patch.material;out[1]=patch.excitation;out[2]=patch.damping;out[3]=patch.coupling;
    return 1;
}
