#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "chrono_runtime.h"
static unsigned compared, nonzero_final;
static uint32_t trace=2166136261u;
static cm_scene_bank bank(void) {
    cm_scene_bank b={0};
    cm_scene a={.bpm=60,.mask={1,1,1},.warp=0,.variation=0,.length={1,1,1}};
    cm_scene z={.bpm=83,.mask={5,1,9},.warp=-35,.variation=22,.length={3,2,4}};
    assert(cm_scene_put(&b,0,&a)); assert(cm_scene_put(&b,3,&z)); return b;
}
/* Independent direct-core render, then rational hold indexed by output frame. */
static void comparison(unsigned preset,unsigned seed,unsigned mask,unsigned offset) {
    static int16_t native[2*CM_RATE+128];
    CmRuntime r={0}; cm_state ref; cm_scene_bank b=bank(); b.occupied=(uint8_t)mask;
    assert(cm_runtime_reset(&r,preset,seed)==3); cm_reset(&ref,seed,preset);
    assert(cm_runtime_transport(&r,CM_ORIGIN_PANEL,CM_TRANSPORT_START)==1); cm_start(&ref);
    int32_t out[2*257]={0};
    cm_runtime_audio(&r,out,offset);
    unsigned already=offset?((offset-1)*80u/147u+1):0;
    cm_render(&ref,native,already);
    assert(cm_runtime_score_begin(&r,&b,1));
    unsigned total=already;
    for(unsigned i=0;i<4;i++) if(mask&(1u<<i)) {
        for(unsigned k=0;k<CM_RATE/CM_SCORE_BLOCK_FRAMES;k++) {
            assert(cm_scene_apply(&ref,&b.slots[i]));
            cm_render(&ref,native+total,CM_SCORE_BLOCK_FRAMES); total+=CM_SCORE_BLOCK_FRAMES;
        }
    }
    cm_stop(&ref);
    unsigned end=(total*147u+79u)/80u;
    nonzero_final+=native[total-1]!=0;
    /* Invalid commands and ignored remote lifecycle must not cancel score. */
    cm_scene bad=b.slots[0];bad.bpm=0;
    assert(!cm_runtime_scene(&r,&bad));assert(!cm_runtime_score_begin(&r,&b,0));
    assert(cm_runtime_transport(&r,CM_ORIGIN_COMPANION,CM_TRANSPORT_START)==5);
    assert(cm_runtime_transport(&r,CM_ORIGIN_SESSION_LOST,CM_TRANSPORT_STOP)==5);
    for(unsigned pos=offset;pos<end+257;) {
        unsigned n=1+(pos+seed)%257;
        if(n>end+257-pos)n=end+257-pos;
        memset(out,0,sizeof out);cm_runtime_audio(&r,out,n);
        for(unsigned i=0;i<n;i++) {
            unsigned at=pos+i;
            int16_t v=at<end?native[at*80u/147u]:0;
            assert(out[2*i]==v && out[2*i+1]==v);
            trace=(trace^(uint16_t)v)*16777619u;
        }
        pos+=n;
    }
    assert(!memcmp(&r.core,&ref,sizeof ref));
    assert(!r.core.playing && !r.retiring && !r.rate.valid && r.owner==CM_OWNER_NONE);
    compared++;
}
static void lifecycle(void) {
    CmRuntime r={0}; cm_scene_bank b=bank(); int32_t out[2]={0};
    assert(cm_runtime_reset(&r,0,42)==3);
    assert(cm_runtime_transport(&r,CM_ORIGIN_COMPANION,CM_TRANSPORT_START)==1);
    assert(cm_runtime_score_begin(&r,&b,1));
    cm_runtime_audio(&r,out,1); assert(r.rate.valid && cm_score_peek(&r.score.cursor));
    assert(cm_runtime_transport(&r,CM_ORIGIN_PANEL,CM_TRANSPORT_START)==1);
    assert(!cm_score_peek(&r.score.cursor));
    assert(cm_runtime_score_begin(&r,&b,1));
    assert(cm_runtime_scene(&r,&b.slots[0]));assert(!cm_score_peek(&r.score.cursor));
    assert(cm_runtime_score_begin(&r,&b,1));
    assert(cm_runtime_transport(&r,CM_ORIGIN_COMPANION,CM_TRANSPORT_PANIC)==3);
    assert(!r.rate.valid && !r.retiring && !cm_score_peek(&r.score.cursor));
    out[0]=out[1]=0;cm_runtime_audio(&r,out,1);assert(!out[0]&&!out[1]);
    /* Panic in the final held-sample window must also be immediate. */
    b.occupied=1;assert(cm_runtime_transport(&r,CM_ORIGIN_PANEL,CM_TRANSPORT_START)==1);
    out[0]=out[1]=0;cm_runtime_audio(&r,out,1); /* shift final sample to a two-frame hold */
    assert(cm_runtime_score_begin(&r,&b,1));
    unsigned n=0;while(r.core.playing && n<44102){out[0]=out[1]=0;cm_runtime_audio(&r,out,1);n++;}
    assert(r.retiring && r.rate.valid && r.owner==CM_OWNER_PANEL);
    assert(cm_runtime_transport(&r,CM_ORIGIN_COMPANION,CM_TRANSPORT_STOP)==5);
    assert(r.retiring && r.rate.valid);
    assert(cm_runtime_transport(&r,CM_ORIGIN_COMPANION,CM_TRANSPORT_PANIC)==3);
    out[0]=out[1]=0;cm_runtime_audio(&r,out,1);assert(!out[0]&&!out[1]);
}
static void panel(void) {
    CmRuntime r={0};CmScorePanel q={0};CmPanel p={0};cm_panel_preset(&p,0);p.playing=1;
    int32_t out[2]={0};uint32_t c=cm_panel_cmd(&p);
    cm_runtime_score_panel(&r,&q,c,1,out,1);assert(cm_score_peek(&r.score.cursor));
    unsigned n=1;
    while((r.core.playing||r.retiring)&&n<12*44100u+1) {
        out[0]=out[1]=0;cm_runtime_score_panel(&r,&q,c,1,out,1);n++;
    }
    assert(n==12*44100u);assert(!r.core.playing && !r.retiring);
    out[0]=out[1]=0;cm_runtime_score_panel(&r,&q,c,1,out,1);assert(!out[0]&&!out[1]&&!r.core.playing);
    cm_runtime_score_panel(&r,&q,c,2,out,1);assert(r.core.playing&&cm_score_peek(&r.score.cursor));
    p.bpm++;cm_runtime_score_panel(&r,&q,cm_panel_cmd(&p),2,out,1);assert(r.core.playing&&!cm_score_peek(&r.score.cursor));
    p.playing=0;out[0]=out[1]=0;cm_runtime_score_panel(&r,&q,cm_panel_cmd(&p),2,out,1);assert(!out[0]&&!out[1]&&!r.core.playing);
}
int main(void) {
    for(unsigned p=0;p<3;p++)for(unsigned s=1;s<=3;s++)for(unsigned m=1;m<=9;m+=(m==1?7:1))
        for(unsigned off=0;off<4;off++)comparison(p,s,m,off);
    lifecycle();panel();assert(nonzero_final);
    printf("Chronomorph score/rate PASS: %u full PCM/state comparisons, %u nonzero final core samples, trace %08x, runtime %zu bytes\n",compared,nonzero_final,trace,sizeof(CmRuntime));
    return 0;
}
