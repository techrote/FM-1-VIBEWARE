#include "chrono.h"
#include <string.h>
static const uint8_t lengths[3][3]={{7,5,11},{5,9,7},{9,7,13}};
static const uint16_t masks[3][3]={{0x49,0x15,0x529},{0x15,0x129,0x55},{0x125,0x49,0x1255}};
static const uint16_t tempos[3]={112,142,84};
static const int8_t warps[3]={24,-32,48};
static const uint8_t scales[3][5]={{0,3,7,10,12},{0,2,5,7,9},{0,1,5,7,10}};
/* Phase increments at MIDI notes 36..47, rounded at 24 kHz. */
static const uint32_t pitch[12]={11704930,12401080,13138695,13920052,14747643,15624500,16553750,17538185,18581238,19685995,20856515,22096842};
static uint32_t next(uint32_t *x){uint32_t v=*x;v^=v<<13;v^=v>>17;v^=v<<5;return *x=v;}
static uint32_t note(unsigned n){return pitch[n%12u]<<(n/12u);}
int cm_controls(cm_state *s,unsigned bpm,int warp,unsigned variation){
    if(bpm<40||bpm>220||warp< -60||warp>60||variation>100)return 0;
    s->bpm=(uint16_t)bpm;s->warp=(int8_t)warp;s->variation=(uint8_t)variation;return 1;
}
int cm_pattern(cm_state *s,unsigned i,unsigned len,unsigned mask){
    if(i>=CM_LANES||len<1||len>16||mask>=(1u<<len))return 0;
    cm_lane *l=&s->lane[i];l->length=(uint8_t)len;l->mask=(uint16_t)mask;
    l->step=(uint8_t)(l->ticks?l->step%len:len-1u);return 1;
}
void cm_reset(cm_state *s,uint32_t seed,unsigned preset){
    memset(s,0,sizeof *s);preset%=3;s->preset=(uint8_t)preset;
    cm_controls(s,tempos[preset],warps[preset],12);s->noise=seed?seed:1;
    for(unsigned i=0;i<CM_LANES;i++){
        cm_lane *l=&s->lane[i];l->length=lengths[preset][i];l->mask=masks[preset][i];
        l->step=(uint8_t)(l->length-1);l->clock=CM_CYCLE-1;
        l->rng=next(&s->noise);l->increment=note(i*12);
    }
    s->master=CM_CYCLE-1;s->beat=7;
}
void cm_start(cm_state *s){s->playing=1;}
void cm_stop(cm_state *s){s->playing=0;for(unsigned i=0;i<CM_LANES;i++)s->lane[i].env=0;}
static void tick(cm_state *s,unsigned i){
    cm_lane *l=&s->lane[i];uint32_t r=next(&l->rng);l->ticks++;
    l->step=(uint8_t)((l->step+1u)%l->length);if(!l->step)l->cycle=(uint8_t)((l->cycle+1u)%4u);
    unsigned hit=(l->mask>>l->step)&1u;
    /* Seeded ghost hits only; empty patterns stay silent. */
    if(!hit&&l->mask&&((r>>8)%100u)<s->variation/3u)hit=1;
    if(hit){unsigned degree=(l->step+l->cycle+(s->beat/4u))%5u;
        if((r%100u)<s->variation)degree=(degree+1u)%5u;
        l->increment=note(scales[s->preset][degree]+i*12u);l->phase=0;
        l->env=(uint16_t)(l->step==0?24000u:16000u+(r%4000u));l->hits++;
    }
}
static int32_t tri(uint32_t p){uint32_t q=p>>16;return (int32_t)(q<32768u?q:65535u-q)*2-32767;}
void cm_render(cm_state *s,int16_t *out,unsigned count){
    for(unsigned n=0;n<count;n++){
        if(!s->playing){out[n]=0;continue;}
        uint32_t base=(uint32_t)s->bpm*4u;s->master+=base*100u;
        if(s->master>=CM_CYCLE){s->master-=CM_CYCLE;s->beat=(uint8_t)((s->beat+1u)%8u);}
        int w=s->beat<4?s->warp:-s->warp;
        unsigned rates[3]={100u,(unsigned)(100+w),(unsigned)(100-w/2)};
        int32_t mix=0;
        for(unsigned i=0;i<CM_LANES;i++){
            cm_lane *l=&s->lane[i];l->clock+=base*rates[i];
            if(l->clock>=CM_CYCLE){l->clock-=CM_CYCLE;tick(s,i);}
            int32_t v=tri(l->phase);l->phase+=l->increment;
            if(i==1)v=(v+tri(l->phase*3u))/2;
            if(i==2)v=(v+(int32_t)(next(&s->noise)>>16)-32768)/2;
            mix+=v*(int32_t)l->env/131072;
            unsigned decay=i==0?3u:i==1?5u:17u;
            l->env=(uint16_t)(l->env>decay?l->env-decay:0);
        }
        out[n]=(int16_t)mix;
    }
}
