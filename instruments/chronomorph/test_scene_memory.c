#include "scene_memory.h"
#include <assert.h>
#include <stdio.h>
static cm_scene cue(unsigned i){
    cm_scene v={0};v.bpm=(uint16_t)(40+60*i);v.warp=(int8_t)(-60+40*(int)i);v.variation=(uint8_t)(33*i);
    for(unsigned j=0;j<CM_LANES;j++){v.length[j]=(uint8_t)(1+((5*i+3*j)%16));v.mask[j]=(uint16_t)((UINT32_C(1)<<(v.length[j]-1))|1u);}
    return v;
}
static void direct(cm_state *s,const cm_scene *v){
    assert(cm_controls(s,v->bpm,v->warp,v->variation));
    for(unsigned j=0;j<CM_LANES;j++)assert(cm_pattern(s,j,v->length[j],v->mask[j]));
}
int main(void){
    unsigned cursor=0,blocks=0,sounding=0,panic=0;
    for(unsigned mask=1;mask<16;mask++)for(unsigned sec=1;sec<=10;sec++){
        cm_scene_bank bank={0};cm_score score={0};
        for(unsigned i=0;i<4;i++)if(mask&(1u<<i)){cm_scene v=cue(i);assert(cm_scene_put(&bank,i,&v));}
        assert(cm_score_begin(&score,&bank,sec));
        memset(&bank,0,sizeof bank); /* detached playback */
        for(unsigned i=0;i<4;i++)if(mask&(1u<<i))for(unsigned n=0;n<sec*20;n++){
            cm_scene v=cue(i);const cm_scene *p=cm_score_peek(&score);
            assert(p&&score.slot==i&&p==cm_score_peek(&score));
            assert(p->bpm==v.bpm&&p->warp==v.warp&&p->variation==v.variation);
            for(unsigned j=0;j<3;j++)assert(p->length[j]==v.length[j]&&p->mask[j]==v.mask[j]);
            cursor++;cm_score_advance(&score);
        }
        assert(!cm_score_peek(&score)&&!cm_score_advance(&score));
    }
    for(unsigned preset=0;preset<3;preset++)for(unsigned mask=1;mask<16;mask++){
        cm_state a,b;cm_reset(&a,17,preset);cm_reset(&b,17,preset);cm_start(&a);cm_start(&b);
        cm_scene_bank bank={0};cm_score score={0};
        for(unsigned i=0;i<4;i++)if(mask&(1u<<i)){cm_scene v=cue(i);assert(cm_scene_put(&bank,i,&v));}
        assert(cm_score_begin(&score,&bank,1));
        cm_scene v=cue(0);v.mask[0]=65535;
        cm_score old=score;cm_scene_bank oldbank=bank;cm_state oldstate=a;
        assert(!cm_scene_put(&bank,0,&v)&&!cm_scene_put(&bank,4,&v));
        assert(!cm_scene_apply(&a,&v)&&!cm_score_begin(&score,&bank,11));
        assert(!memcmp(&old,&score,sizeof score)&&!memcmp(&oldbank,&bank,sizeof bank)&&!memcmp(&oldstate,&a,sizeof a));
        bank.occupied=128;assert(!cm_score_begin(&score,&bank,1));
        for(unsigned i=0;i<4;i++)if(mask&(1u<<i))for(unsigned n=0;n<20;n++){
            int16_t x[1200],y[1200];cm_scene expected=cue(i);
            assert(cm_scene_apply(&a,cm_score_peek(&score)));direct(&b,&expected);
            cm_render(&a,x,1200);cm_render(&b,y,1200);
            assert(!memcmp(x,y,sizeof x)&&!memcmp(&a,&b,sizeof a));
            cm_score_advance(&score);blocks++;
            for(unsigned j=0;j<1200;j++)if(x[j]){sounding++;break;}
        }
        assert(!cm_score_peek(&score));
        cm_scene captured;cm_scene_capture(&captured,&a);assert(cm_scene_valid(&captured));
        assert(captured.bpm==a.bpm&&captured.warp==a.warp&&captured.variation==a.variation);
        for(unsigned j=0;j<3;j++)assert(captured.length[j]==a.lane[j].length&&captured.mask[j]==a.lane[j].mask);
        memset(&bank,0,sizeof bank);assert(cm_scene_put(&bank,0,&captured));assert(cm_score_begin(&score,&bank,1));
        cm_score_cancel(&score);cm_stop(&a);int16_t tail[1200];cm_render(&a,tail,1200);
        assert(!cm_score_peek(&score));for(unsigned j=0;j<1200;j++)assert(!tail[j]);panic++;
    }
    printf("scene cursor=%u native blocks=%u sounding=%u panic=%u bank=%zu score=%zu\n",cursor,blocks,sounding,panic,sizeof(cm_scene_bank),sizeof(cm_score));
    assert(sounding>0);return 0;
}
