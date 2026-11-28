#ifndef CM_SCENE_MEMORY_H
#define CM_SCENE_MEMORY_H
#include "chrono.h"
#include <string.h>
/* Local semantic values only. Never serialize this struct or use as a wire ABI.
 * Single serialized owner; session validity and panic remain caller duties. */
#define CM_SCENE_SLOTS 4u
#define CM_SCORE_BLOCK_FRAMES 1200u
#define CM_SCORE_BLOCKS_PER_SECOND 20u
#define CM_SCORE_MAX_SECONDS 10u
typedef struct {
    uint16_t bpm, mask[CM_LANES];
    int8_t warp;
    uint8_t variation, length[CM_LANES];
} cm_scene;
typedef struct { cm_scene slots[CM_SCENE_SLOTS]; uint8_t occupied; } cm_scene_bank;
typedef struct { cm_scene_bank snapshot; uint16_t remaining, span; uint8_t slot; } cm_score;
static inline int cm_scene_valid(const cm_scene *v){
    if(v->bpm<40||v->bpm>220||v->warp< -60||v->warp>60||v->variation>100)return 0;
    for(unsigned i=0;i<CM_LANES;i++)
        if(v->length[i]<1||v->length[i]>16||v->mask[i]>=(UINT32_C(1)<<v->length[i]))return 0;
    return 1;
}
static inline void cm_scene_capture(cm_scene *v,const cm_state *s){
    memset(v,0,sizeof *v);v->bpm=s->bpm;v->warp=s->warp;v->variation=s->variation;
    for(unsigned i=0;i<CM_LANES;i++){v->length[i]=s->lane[i].length;v->mask[i]=s->lane[i].mask;}
}
static inline int cm_scene_put(cm_scene_bank *b,unsigned slot,const cm_scene *v){
    if(slot>=CM_SCENE_SLOTS||!cm_scene_valid(v))return 0;
    b->slots[slot]=*v;b->occupied|=(uint8_t)(1u<<slot);return 1;
}
static inline int cm_scene_apply(cm_state *s,const cm_scene *v){
    if(!cm_scene_valid(v))return 0;
    cm_controls(s,v->bpm,v->warp,v->variation);
    for(unsigned i=0;i<CM_LANES;i++)cm_pattern(s,i,v->length[i],v->mask[i]);
    return 1;
}
static inline void cm_score_cancel(cm_score *p){memset(p,0,sizeof *p);}
/* Begin captures the complete bank. Invalid requests leave a prior score intact. */
static inline int cm_score_begin(cm_score *p,const cm_scene_bank *b,unsigned seconds){
    if(seconds<1||seconds>CM_SCORE_MAX_SECONDS||!b->occupied||(b->occupied&~15u))return 0;
    for(unsigned i=0;i<CM_SCENE_SLOTS;i++)
        if((b->occupied&(1u<<i))&&!cm_scene_valid(&b->slots[i]))return 0;
    cm_score next={0};next.snapshot=*b;next.span=(uint16_t)(seconds*CM_SCORE_BLOCKS_PER_SECOND);
    while(!(b->occupied&(1u<<next.slot)))next.slot++;
    next.remaining=next.span;*p=next;return 1;
}
/* Peek is idempotent. Advance exactly once per accepted 1200-frame block.
 * On completion the caller pauses; on manual control/panic cancel before applying.
 * No auto-start/stop, queue, timer, or transport side effects. */
static inline const cm_scene *cm_score_peek(const cm_score *p){
    return p->remaining?&p->snapshot.slots[p->slot]:0;
}
static inline int cm_score_advance(cm_score *p){
    if(!p->remaining)return 0;
    if(--p->remaining)return 1;
    while(++p->slot<CM_SCENE_SLOTS){
        if(p->snapshot.occupied&(1u<<p->slot)){p->remaining=p->span;return 1;}
    }
    return 0;
}
#endif
