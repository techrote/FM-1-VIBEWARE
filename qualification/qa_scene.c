/* Independent score cursor/PCM oracle, with partition and invalid-operation checks. */
#include "scene_memory.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
static uint32_t rnd(uint32_t *s){*s=*s*1664525u+1013904223u;return *s;}
static cm_scene cue(uint32_t *r){
    cm_scene v={0};v.bpm=(uint16_t)(40+rnd(r)%181);v.warp=(int8_t)((int)(rnd(r)%121)-60);v.variation=(uint8_t)(rnd(r)%101);
    for(unsigned i=0;i<CM_LANES;i++){v.length[i]=(uint8_t)(1+rnd(r)%16);v.mask[i]=(uint16_t)((rnd(r)>>8)&((1u<<v.length[i])-1));}
    return v;
}
static void direct(cm_state *s,const cm_scene *v){
    assert(cm_controls(s,v->bpm,v->warp,v->variation));
    for(unsigned i=0;i<CM_LANES;i++)assert(cm_pattern(s,i,v->length[i],v->mask[i]));
}
int main(void){
    uint32_t rng=0xa23f118du; unsigned blocks=0,sounding=0,rejects=0;
    for(unsigned trial=0;trial<90;trial++){
        cm_scene_bank bank={0};cm_score score={0};cm_scene expected[4];unsigned order[4],n=0;
        unsigned occupied=1+trial%15,seconds=1+trial%10,span=20*seconds;
        for(unsigned i=0;i<4;i++)if(occupied&(1u<<i)){expected[i]=cue(&rng);order[n++]=i;assert(cm_scene_put(&bank,i,&expected[i]));}
        assert(cm_score_begin(&score,&bank,seconds));
        cm_state a,b;cm_reset(&a,trial+1,trial%3);cm_reset(&b,trial+1,trial%3);cm_start(&a);cm_start(&b);
        for(unsigned k=0;k<n*span;k++){
            unsigned slot=order[k/span];const cm_scene *p=cm_score_peek(&score);assert(p&&score.slot==slot&&score.remaining==span-k%span);
            /* Change the source bank while the detached score is active. */
            cm_scene replacement=cue(&rng);assert(cm_scene_put(&bank,slot,&replacement));
            cm_score saved=score;cm_scene invalid=replacement;invalid.bpm=221;cm_state prev=a;
            assert(!cm_score_begin(&score,&bank,0));assert(!cm_scene_apply(&a,&invalid));
            assert(!memcmp(&saved,&score,sizeof score)&&!memcmp(&prev,&a,sizeof a));rejects+=2;
            assert(cm_scene_apply(&a,p));direct(&b,&expected[slot]);
            int16_t x[1200],y[1200];cm_render(&a,x,1200);
            unsigned cut=1+rnd(&rng)%1199;cm_render(&b,y,cut);cm_render(&b,y+cut,1200-cut);
            assert(!memcmp(x,y,sizeof x)&&!memcmp(&a,&b,sizeof a));
            for(unsigned j=0;j<1200;j++)if(x[j]){sounding++;break;}
            blocks++;assert(cm_score_advance(&score)==(k+1<n*span));
        }
        assert(!cm_score_peek(&score)&&!cm_score_advance(&score));
        assert(cm_score_begin(&score,&bank,1));cm_score_cancel(&score);cm_stop(&a);
        int16_t silence[1200];cm_render(&a,silence,1200);for(unsigned j=0;j<1200;j++)assert(!silence[j]);
        assert(!cm_score_peek(&score));
    }
    assert(sounding>0);printf("QA scene: %u blocks, %u sounding, %u rejected operations, 90 silent cancellations\n",blocks,sounding,rejects);return 0;
}
