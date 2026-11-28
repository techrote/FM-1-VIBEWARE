/* Exercise the same local fixture used by browser/native audition. */
#include "ecophon.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>
void ecof_reset(uint32_t seed,unsigned preset);
void ecof_panic(void);
int ecof_step(unsigned f,unsigned s,unsigned p,unsigned ab,int16_t *pcm,uint32_t *snap);
int ecof_memory_capture(unsigned slot);
int ecof_memory_recall(unsigned slot);
int ecof_memory_step(int16_t *pcm,uint32_t *snap);
#define N 2400u
#define W 56u
#define BLOCKS 110u
static int16_t expected[BLOCKS][N];
static uint32_t states[BLOCKS][W];
static const unsigned initial[3][3]={{180,200,40},{100,20,150},{230,90,85}};
static const unsigned a[3]={0,0,255}, b[3]={255,220,0}, manual[3]={150,240,70};
static void mix(unsigned out[3],const unsigned *from,const unsigned *to,unsigned n) {
    for(unsigned i=0;i<3;++i) out[i]=(from[i]*(40-n)+to[i]*n)/40;
}
static void trial(unsigned preset,unsigned takeover) {
    int16_t pcm[N]; uint32_t snap[W]; unsigned env[3],captured[3];
    mix(captured,initial[preset],a,20);
    ecof_reset(42,preset);
    for(unsigned i=1;i<=BLOCKS;++i) {
        if(i<=40) mix(env,initial[preset],a,i);
        else if(i<=80) mix(env,a,b,i-40);
        else mix(env,b,captured,i-80);
        if(takeover&&i>=61) memcpy(env,manual,sizeof env);
        assert(ecof_step(env[0],env[1],env[2],0,expected[i-1],states[i-1])==W);
    }
    /* Capture two slots with the existing manual path, then reset only habitat. */
    ecof_reset(42,preset);
    assert(ecof_step(a[0],a[1],a[2],0,pcm,snap)==W && ecof_memory_capture(0));
    assert(ecof_step(b[0],b[1],b[2],0,pcm,snap)==W && ecof_memory_capture(1));
    ecof_reset(42,preset);
    assert(ecof_memory_recall(0));
    for(unsigned i=1;i<=BLOCKS;++i) {
        if(i==21) assert(ecof_memory_capture(0));
        if(i==41) assert(ecof_memory_recall(1));
        if(i==81&&!takeover) assert(ecof_memory_recall(0));
        /* Invalid requests must not advance either the ramp or core. */
        assert(!ecof_memory_step(NULL,snap)&&!ecof_memory_step(pcm,NULL));
        assert(!ecof_memory_capture(2)&&!ecof_memory_recall(2));
        assert(!ecof_step(256,0,0,0,pcm,snap));
        int rc=(takeover&&i==61)?ecof_step(manual[0],manual[1],manual[2],0,pcm,snap):ecof_memory_step(pcm,snap);
        assert(rc==W && snap[0]==i*10u);
        assert(!memcmp(pcm,expected[i-1],sizeof pcm));
        assert(!memcmp(snap,states[i-1],sizeof snap));
    }
    /* Freeze via direct path cancels recall; unfreeze never resumes it. */
    assert(ecof_memory_recall(1));
    assert(ecof_step(33,44,55,1,pcm,snap)==W&&!ecof_memory_recall(1));
    assert(ecof_memory_step(pcm,snap)==W&&snap[7]==1&&snap[9]==33&&snap[10]==44&&snap[11]==55);
    assert(ecof_step(33,44,55,0,pcm,snap)==W);
    assert(ecof_memory_step(pcm,snap)==W&&snap[7]==0&&snap[9]==33&&snap[10]==44&&snap[11]==55);
    assert(ecof_memory_recall(1)); ecof_panic();
    assert(!ecof_memory_step(pcm,snap)&&!ecof_memory_capture(0)&&!ecof_memory_recall(1));
    /* Preserve the legacy explicit step's post-panic silence witness. */
    assert(ecof_step(33,44,55,0,pcm,snap)==W&&snap[8]==1&&snap[0]==(BLOCKS+5)*10u);
    for(unsigned i=0;i<N;++i) assert(!pcm[i]);
    ecof_reset(42,preset); assert(ecof_memory_step(pcm,snap)==W&&snap[0]==10&&snap[8]==0);
    assert(snap[9]==initial[preset][0]&&snap[10]==initial[preset][1]&&snap[11]==initial[preset][2]);
}
int main(void) {
    int16_t pcm[N]; uint32_t snap[W];
    assert(!ecof_memory_step(pcm,snap)&&!ecof_memory_capture(0)&&!ecof_memory_recall(0));
    ecof_reset(42,0); assert(!ecof_memory_recall(0));
    for(unsigned p=0;p<3;++p){trial(p,0);trial(p,1);}
    ecof_reset(42,3); assert(!ecof_memory_recall(0));
    assert(ecof_memory_step(pcm,snap)==W&&snap[7]==1);
    puts("PASS 660 actual-core PCM and snapshot blocks; invalid requests, manual takeover, freeze, panic and restart");
    return 0;
}
