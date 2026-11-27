/* Host-only single-engine fixture. No target or transport ABI. */
#include "xeno.h"
#ifdef _WIN32
#define EXPORT __declspec(dllexport)
#else
#define EXPORT
#endif
static Xeno engine;
EXPORT void live_reset(void){xeno_reset(&engine,42,0);}
EXPORT void live_panic(void){xeno_panic(&engine);}
/* Five 10 ms slices; peak sampled modal magnitude within each 50 ms block. */
EXPORT void live_block(unsigned p,unsigned e,unsigned d,unsigned c,unsigned n,
                       unsigned v,unsigned event,int16_t *pcm,uint32_t *levels){
    xeno_controls(&engine,e,d,c);
    if(engine.material!=p)xeno_material(&engine,p);
    if(event==1)xeno_strike(&engine,n,v);
    else if(event==2)xeno_release(&engine);
    for(unsigned m=0;m<XENO_MODES;m++)levels[m]=0;
    for(unsigned i=0;i<5;i++){
        xeno_render(&engine,pcm+i*240,240);
        for(unsigned m=0;m<XENO_MODES;m++){
            uint32_t level=xeno_mode_level(&engine,m);
            if(level>levels[m])levels[m]=level;
        }
    }
}
