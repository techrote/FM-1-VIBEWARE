#include "chrono.h"
#include <stddef.h>
/* Host-only local ABI. No target or wire ABI changes. Single serialized owner. */
static cm_state state;
void live_reset(uint32_t seed,unsigned preset){cm_reset(&state,seed,preset);}
void live_stop(void){cm_stop(&state);}
int live_block(unsigned bpm,int warp,unsigned variation,unsigned playing,
               const uint32_t *patterns,int16_t *pcm,uint32_t *snapshot){
    cm_state next=state;
    if(playing>1||!cm_controls(&next,bpm,warp,variation))return 0;
    for(unsigned i=0;i<CM_LANES;i++)
        if(!cm_pattern(&next,i,patterns[2*i],patterns[2*i+1]))return 0;
    state=next;
    if(playing)cm_start(&state);else cm_stop(&state);
    cm_render(&state,pcm,1200);
    for(unsigned i=0;i<CM_LANES;i++){
        const cm_lane *l=&state.lane[i];
        snapshot[5*i]=l->step;snapshot[5*i+1]=l->ticks;
        snapshot[5*i+2]=l->hits;snapshot[5*i+3]=l->cycle;
        snapshot[5*i+4]=l->clock;
    }
    return 1;
}
