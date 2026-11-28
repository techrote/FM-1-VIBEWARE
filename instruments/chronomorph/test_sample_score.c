#include "sample_score.h"
#include <assert.h>
#include <stdio.h>

#define MAX_FRAMES (4u*CM_SCORE_MAX_SECONDS*CM_RATE+123u)
static int16_t reference[MAX_FRAMES], actual[MAX_FRAMES];
static uint32_t trace=2166136261u;

static cm_scene_bank bank_for(unsigned mask) {
    cm_scene_bank bank={0};
    for (unsigned i=0;i<4;i++) if (mask&(1u<<i)) {
        cm_scene v={0};
        v.bpm=(uint16_t)(40u+60u*i); v.warp=(int8_t)(-60+40*(int)i);
        v.variation=(uint8_t)(i*30u);
        for (unsigned l=0;l<CM_LANES;l++) {
            v.length[l]=(uint8_t)(1u+i*3u+l*2u);
            v.mask[l]=(uint16_t)(((1u<<v.length[l])-1u)&(0x5555u>>l));
        }
        assert(cm_scene_put(&bank,i,&v));
    }
    return bank;
}

/* Independent direct-control oracle; no score cursor or performer calls. */
static unsigned oracle(cm_state *s,const cm_scene_bank *b,unsigned seconds) {
    unsigned at=0;
    for (unsigned i=0;i<4;i++) if (b->occupied&(1u<<i)) {
        const cm_scene *v=&b->slots[i];
        for (unsigned block=0;block<seconds*20u;block++) {
            assert(cm_controls(s,v->bpm,v->warp,v->variation));
            for (unsigned l=0;l<CM_LANES;l++)
                assert(cm_pattern(s,l,v->length[l],v->mask[l]));
            cm_render(s,reference+at,1200u); at+=1200u;
        }
    }
    cm_stop(s); cm_render(s,reference+at,123u);
    return at+123u;
}

static void compare(unsigned mask,unsigned seconds,unsigned preset,uint32_t seed) {
    cm_state a,b; cm_reset(&a,seed,preset); cm_start(&a);
    /* Start from a running, nonzero clock phase, not a fresh score reset. */
    cm_render(&a,actual,137u); b=a;
    cm_scene_bank bank=bank_for(mask);
    unsigned frames=oracle(&a,&bank,seconds);
    cm_sample_score p={0};
    assert(cm_sample_score_begin(&p,&b,&bank,seconds));
    bank.occupied=0; /* detached snapshot survives bank edits */
    const unsigned parts[]={1,1199,4801,17,1200,1201,8191,31};
    unsigned at=0,step=0,ends=0;
    while (at<frames) {
        unsigned n=parts[step++%8u]; if(n>frames-at)n=frames-at;
        assert(!cm_sample_score_render(&p,&b,actual+at,0));
        unsigned end=(unsigned)cm_sample_score_render(&p,&b,actual+at,n);
        assert(end==(at<frames-123u && at+n>=frames-123u));
        ends+=end; at+=n;
    }
    assert(ends==1 && !b.playing && !p.cursor.remaining && !p.offset);
    assert(!memcmp(&a,&b,sizeof a));
    assert(!memcmp(reference,actual,frames*sizeof actual[0]));
    unsigned sounding=0;
    for(unsigned i=0;i<frames;i++) {
        sounding+=(actual[i]!=0);
        trace=(trace^(uint16_t)actual[i])*16777619u;
        if(i>=frames-123u) assert(!actual[i]);
    }
    assert(sounding);
}

static void lifecycle(void) {
    cm_state a,b; cm_reset(&a,17,0); cm_sample_score p={0};
    cm_scene_bank bank=bank_for(10), invalid=bank;
    assert(!cm_sample_score_begin(&p,&a,&bank,1));
    cm_start(&a); assert(cm_sample_score_begin(&p,&a,&bank,1));
    assert(!cm_sample_score_render(&p,&a,actual,37));
    assert(p.offset==37 && p.cursor.slot==1);
    cm_sample_score before=p; b=a; invalid.slots[1].bpm=0;
    assert(!cm_sample_score_begin(&p,&a,&invalid,1));
    assert(!cm_sample_score_begin(&p,&a,&bank,11));
    assert(!memcmp(&p,&before,sizeof p) && !memcmp(&a,&b,sizeof a));
    cm_sample_score_cancel(&p); /* manual takeover, no stop or phase reset */
    assert(cm_controls(&a,123,-17,19)); assert(cm_controls(&b,123,-17,19));
    assert(!cm_sample_score_render(&p,&a,actual,4801));
    cm_render(&b,reference,4801);
    assert(!memcmp(&a,&b,sizeof a) && !memcmp(actual,reference,4801*sizeof actual[0]));
    assert(cm_sample_score_begin(&p,&a,&bank,1));
    assert(!cm_sample_score_render(&p,&a,actual,3));
    cm_stop(&a); b=a;
    assert(!cm_sample_score_render(&p,&a,actual,1201));
    assert(!p.cursor.remaining && !p.offset && !memcmp(&a,&b,sizeof a));
    for(unsigned i=0;i<1201;i++)assert(!actual[i]);
    cm_start(&a); assert(cm_sample_score_begin(&p,&a,&bank,1));
    assert(!cm_sample_score_render(&p,&a,actual,1));
    assert(p.offset==1 && p.cursor.slot==1);
    cm_sample_score_cancel(&p); cm_reset(&a,17,0);
    assert(!cm_sample_score_render(&p,&a,actual,123));
    for(unsigned i=0;i<123;i++)assert(!actual[i]);
}
int main(void) {
    unsigned cases=0;
    for(unsigned mask=1;mask<16;mask++)for(unsigned preset=0;preset<3;preset++)
        for(unsigned seconds=1;seconds<=10;seconds+=9)
            for(unsigned seed=0;seed<2;seed++) {
                compare(mask,seconds,preset,seed?0xffffffffu:17u); cases++;
            }
    lifecycle();
    printf("sample-score PASS cases=%u trace=%08x performer=%zu cursor=%zu\n",
           cases,(unsigned)trace,sizeof(cm_sample_score),sizeof(cm_score));
    return 0;
}
