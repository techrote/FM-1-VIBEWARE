#include "scene_memory.h"
#include <stddef.h>
/* Host-only local ABI. No target or wire ABI changes. Single serialized owner. */
static cm_state state;
static cm_scene_bank bank;
static cm_score score;
void live_reset(uint32_t seed,unsigned preset){
    cm_reset(&state,seed,preset);memset(&bank,0,sizeof bank);cm_score_cancel(&score);
}
void live_stop(void){cm_score_cancel(&score);cm_stop(&state);}
static void scene_render(unsigned playing,int16_t *pcm,uint32_t *snapshot);
int live_block(unsigned bpm,int warp,unsigned variation,unsigned playing,
               const uint32_t *patterns,int16_t *pcm,uint32_t *snapshot){
    cm_state next=state;
    if(playing>1||!cm_controls(&next,bpm,warp,variation))return 0;
    for(unsigned i=0;i<CM_LANES;i++)
        if(!cm_pattern(&next,i,patterns[2*i],patterns[2*i+1]))return 0;
    cm_score_cancel(&score);
    state=next;
    scene_render(playing,pcm,snapshot);
    return 1;
}

// Local session semantic seam; no target or transport ABI.
int live_scene_capture(unsigned slot){
    cm_scene v;cm_scene_capture(&v,&state);return cm_scene_put(&bank,slot,&v);
}
void live_scene_clear(void){memset(&bank,0,sizeof bank);}
unsigned live_scene_mask(void){return bank.occupied;}
static void scene_render(unsigned playing,int16_t *pcm,uint32_t *snapshot){
    if(playing)cm_start(&state);else cm_stop(&state);
    cm_render(&state,pcm,CM_SCORE_BLOCK_FRAMES);
    for(unsigned i=0;i<CM_LANES;i++){
        const cm_lane *l=&state.lane[i];
        snapshot[5*i]=l->step;snapshot[5*i+1]=l->ticks;
        snapshot[5*i+2]=l->hits;snapshot[5*i+3]=l->cycle;
        snapshot[5*i+4]=l->clock;
    }
}
int live_scene_recall(unsigned slot,unsigned playing,int16_t *pcm,uint32_t *snapshot){
    if(slot>=CM_SCENE_SLOTS||!(bank.occupied&(1u<<slot))||playing>1)return 0;
    if(!cm_scene_apply(&state,&bank.slots[slot]))return 0;
    cm_score_cancel(&score);scene_render(playing,pcm,snapshot);return 1;
}
int live_score_begin(unsigned seconds){return cm_score_begin(&score,&bank,seconds);}
void live_score_position(uint32_t *position){
    position[0]=score.remaining?score.slot:CM_SCENE_SLOTS;
    position[1]=score.remaining;
}
int live_score_block(int16_t *pcm,uint32_t *snapshot){
    const cm_scene *v=cm_score_peek(&score);
    if(!v||!cm_scene_apply(&state,v))return 0;
    scene_render(1,pcm,snapshot);
    if(!cm_score_advance(&score))cm_stop(&state);
    return 1;
}

/* Atomic authored score load. The live bank and engine are unchanged; only
 * the detached cursor is replaced after all supplied controls validate.
 * The host ABI uses nine signed 32-bit values per slot, not a wire struct. */
int live_score_start(unsigned seconds,unsigned mask,const int32_t *values){
    cm_scene_bank next={0};
    if(!mask||(mask&~15u)||seconds<1||seconds>CM_SCORE_MAX_SECONDS)return 0;
    for(unsigned slot=0;slot<CM_SCENE_SLOTS;slot++){
        if(!(mask&(1u<<slot)))continue;
        const int32_t *p=values+9*slot;
        if(p[0]<40||p[0]>220||p[1]< -60||p[1]>60||p[2]<0||p[2]>100)return 0;
        cm_scene v={0};
        v.bpm=(uint16_t)p[0];v.warp=(int8_t)p[1];v.variation=(uint8_t)p[2];
        for(unsigned i=0;i<CM_LANES;i++){
            int32_t n=p[3+2*i],m=p[4+2*i];
            if(n<1||n>16||m<0||(uint32_t)m>=(UINT32_C(1)<<n))return 0;
            v.length[i]=(uint8_t)n;v.mask[i]=(uint16_t)m;
        }
        if(!cm_scene_put(&next,slot,&v))return 0;
    }
    return cm_score_begin(&score,&next,seconds);
}
unsigned live_score_total(void){
    unsigned total=score.remaining;
    if(total)for(unsigned i=score.slot+1;i<CM_SCENE_SLOTS;i++)
        if(score.snapshot.occupied&(1u<<i))total+=score.span;
    return total;
}
int live_score_frame(int32_t *values){
    const cm_scene *v=cm_score_peek(&score);
    if(!v)return 0;
    values[0]=(int32_t)score.slot;values[1]=v->bpm;values[2]=v->warp;values[3]=v->variation;
    for(unsigned i=0;i<CM_LANES;i++){values[4+2*i]=v->length[i];values[5+2*i]=v->mask[i];}
    return 1;
}
