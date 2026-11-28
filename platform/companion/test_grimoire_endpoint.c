/* SPDX-License-Identifier: MIT */
#include "grimoire_control.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

typedef struct {CydOrbitCommand cmd;CydOrbitRuntime rt;CydState state;uint32_t applied;int ready;} Fixture;
static int apply(void *p,uint8_t op,const uint8_t *v) {return cyd_orbit_apply(&((Fixture *)p)->cmd,op,v);}
static int read_state(void *p,CydState *s) {
    Fixture *f=p;if(!f->ready||f->applied!=f->cmd.version)return 0;
    *s=f->state;return 1;
}
static void render(Fixture *f,int16_t *pcm,size_t n) {
    cyd_orbit_sync(&f->rt,&f->cmd);
    for(size_t i=0;i<n;i++) {
        pcm[i]=f->cmd.panic?0:cyd_orbit_next(&f->rt);cyd_orbit_observe(&f->rt,pcm[i]);
    }
    cyd_orbit_snapshot(&f->rt,&f->cmd,&f->state);f->applied=f->cmd.version;f->ready=1;
}
static size_t send(CydEndpoint *e,uint32_t session,uint16_t seq,uint32_t now,uint8_t op,const uint8_t *data,uint8_t n,uint8_t *out) {
    uint8_t packet[63]={0xf0,0x7d,'C','Y',1,0,op};size_t size=0;
    for(unsigned i=0;i<4;i++)packet[7+i]=(uint8_t)((session>>(7*i))&127u);
    packet[11]=(uint8_t)(seq&127u);packet[12]=(uint8_t)(seq>>7);packet[13]=n;
    for(unsigned i=0;i<n;i++)packet[14+i]=data[i];
    packet[14+n]=0xf7;assert(cyd_endpoint_receive(e,packet,15u+n,now,out,&size));return size;
}
static void mutation(CydEndpoint *e,uint16_t *seq,uint8_t op,uint8_t a,uint8_t b,uint8_t n,uint8_t *out) {
    const uint8_t p[2]={a,b};++*seq;assert(!send(e,42,*seq,*seq,op,p,n,out));
}
static void ownership_test(void) {
    Fixture f={0};uint8_t owner=CYD_ORBIT_OWNER_NONE;
    int16_t pcm[2048],direct[2048];const uint8_t note[2]={48,127},release[2]={48,0},empty[2]={0,0};
    cyd_orbit_init(&f.cmd);
    assert(cyd_orbit_apply_owned(&f.cmd,&owner,CYD_ORBIT_PANEL,CYD_NOTE,note));
    assert(owner==CYD_ORBIT_OWNER_PANEL);
    render(&f,pcm,2048);
    Orbit ref=f.rt.core;uint32_t version=f.cmd.version;
    assert(cyd_orbit_apply_owned(&f.cmd,&owner,CYD_ORBIT_REMOTE,CYD_NOTE,release));
    assert(cyd_orbit_apply_owned(&f.cmd,&owner,CYD_ORBIT_SESSION_LOSS,CYD_PANIC,empty));
    assert(f.cmd.version==version&&f.cmd.gate&&owner==CYD_ORBIT_OWNER_PANEL);
    render(&f,pcm,2048);orbit_render(&ref,direct,2048);assert(!memcmp(pcm,direct,sizeof pcm));
    unsigned nonzero=0;for(unsigned i=0;i<2048;i++)nonzero+=pcm[i]!=0;assert(nonzero>1000);
    /* An explicit remote emergency panic is still global. */
    assert(cyd_orbit_apply_owned(&f.cmd,&owner,CYD_ORBIT_REMOTE,CYD_PANIC,empty));
    render(&f,pcm,2048);for(unsigned i=0;i<2048;i++)assert(!pcm[i]);
    assert(owner==CYD_ORBIT_OWNER_NONE);
    /* A new remote note owns the gesture and expiry must still kill its tail,
     * even after a note-off. */
    assert(cyd_orbit_apply_owned(&f.cmd,&owner,CYD_ORBIT_REMOTE,CYD_NOTE,note));
    render(&f,pcm,2048);
    assert(cyd_orbit_apply_owned(&f.cmd,&owner,CYD_ORBIT_REMOTE,CYD_NOTE,release));
    assert(owner==CYD_ORBIT_OWNER_REMOTE);
    assert(cyd_orbit_apply_owned(&f.cmd,&owner,CYD_ORBIT_SESSION_LOSS,CYD_PANIC,empty));
    render(&f,pcm,2048);for(unsigned i=0;i<2048;i++)assert(!pcm[i]);
    assert(owner==CYD_ORBIT_OWNER_NONE);
    printf("PASS: panel ownership, 2048 exact held PCM comparisons (%u sounding), 4096 exact silent panic/expiry samples\n",nonzero);
}
int main(void) {
    ownership_test();
    Fixture f={0};CydEndpoint e;uint8_t out[63];uint16_t seq=0;int16_t pcm[2048],direct[2048];unsigned total=0;
    cyd_orbit_init(&f.cmd);
    assert(!cyd_endpoint_init_profile(&e,99,1,&f,apply,read_state));
    assert(send(&e,42,0,0,CYD_DISCOVER,(uint8_t[]){99},1,out)==16&&out[14]==4);
    cyd_endpoint_init(&e,1,&f,apply,read_state);
    assert(send(&e,42,0,0,CYD_DISCOVER,(uint8_t[]){2},1,out)==21&&out[14]==2&&out[17]==31);
    assert(cyd_endpoint_init_profile(&e,CYD_GRIMOIRE,1,&f,apply,read_state));
    assert(send(&e,42,0,0,CYD_DISCOVER,(uint8_t[]){2},1,out)==16&&out[14]==4&&!e.session);
    assert(send(&e,42,0,0,CYD_DISCOVER,(uint8_t[]){3},1,out)==21&&out[14]==3&&out[17]==31);
    for(unsigned preset=0;preset<3;preset++) {
        Orbit ref;orbit_reset(&ref,preset);orbit_xy(&ref,63,107);orbit_gate(&ref,1);
        mutation(&e,&seq,CYD_SET_PRESET,(uint8_t)preset,0,1,out);
        mutation(&e,&seq,CYD_SET_PARAMETER,0,63,2,out);
        mutation(&e,&seq,CYD_SET_PARAMETER,1,107,2,out);
        mutation(&e,&seq,CYD_NOTE,59,1,2,out); /* gate token; velocity does not change X */
        assert(!cyd_endpoint_reply(&e,out));render(&f,pcm,2048);orbit_render(&ref,direct,2048);
        assert(!memcmp(pcm,direct,sizeof pcm));for(unsigned i=0;i<2048;i++)total+=pcm[i]!=0;
        assert(cyd_endpoint_reply(&e,out)==38&&out[14]==3&&out[16]==63&&out[17]==107&&out[24]==preset&&out[25]==59&&out[26]==1&&out[27]==2&&out[28]>0&&out[29]>0&&out[34]>0);
        for(unsigned i=18;i<24;i++)assert(!out[i]);
        for(unsigned i=30;i<34;i++)assert(!out[i]);
        mutation(&e,&seq,CYD_NOTE,36,0,2,out);render(&f,pcm,2048);orbit_render(&ref,direct,2048);assert(!memcmp(pcm,direct,sizeof pcm));assert(f.rt.core.gate);
        mutation(&e,&seq,CYD_NOTE,59,0,2,out);render(&f,pcm,2048);orbit_gate(&ref,0);orbit_render(&ref,direct,2048);assert(!memcmp(pcm,direct,sizeof pcm));
    }
    assert(total>6000);
    /* Panic and a fresh note coalesced before render must still clear energy. */
    mutation(&e,&seq,CYD_NOTE,48,127,2,out);render(&f,pcm,2048);
    Orbit ref=f.rt.core;orbit_panic(&ref);orbit_gate(&ref,1);
    mutation(&e,&seq,CYD_PANIC,0,0,0,out);mutation(&e,&seq,CYD_NOTE,48,127,2,out);
    render(&f,pcm,2048);orbit_render(&ref,direct,2048);assert(!memcmp(pcm,direct,sizeof pcm));
    const uint32_t version=f.cmd.version;
    ++seq;assert(send(&e,42,seq,seq,CYD_SET_PARAMETER,(uint8_t[]){2,127},2,out)==16&&out[14]==5);
    ++seq;assert(send(&e,42,seq,seq,CYD_SET_PRESET,(uint8_t[]){3},1,out)==16&&out[14]==5);
    ++seq;assert(send(&e,42,seq,seq,CYD_NOTE,(uint8_t[]){60,127},2,out)==16&&out[14]==5);
    assert(f.cmd.version==version);
    assert(send(&e,42,0,500,CYD_DISCOVER,(uint8_t[]){3},1,out)==21);assert(e.sequence==seq);
    cyd_endpoint_tick(&e,e.last_ms+1500u);assert(!e.session&&!e.reply_pending&&e.expired==1);
    render(&f,pcm,2048);for(unsigned i=0;i<2048;i++)assert(!pcm[i]);assert(!f.state.output_peak&&!f.state.meters[0]&&!f.state.meters[1]);
    assert(send(&e,42,seq+1,2000,CYD_NOTE,(uint8_t[]){48,127},2,out)==16&&out[14]==3);
    assert(send(&e,43,0,2001,CYD_DISCOVER,(uint8_t[]){3},1,out)==21);
    assert(!send(&e,43,1,2002,CYD_NOTE,(uint8_t[]){36,127},2,out));render(&f,pcm,2048);
    unsigned resumed=0;for(unsigned i=0;i<2048;i++)resumed+=pcm[i]!=0;assert(resumed>1000);
    assert(cyd_endpoint_reply(&e,out)==38&&out[25]==36&&out[26]==1);
    printf("PASS: 3 presets, 18432 exact PCM comparisons + 2048 coalesced panic comparisons, %u sounding initial samples, %u recovery samples, profile/session/range/lease/telemetry checks\n",total,resumed);
}
