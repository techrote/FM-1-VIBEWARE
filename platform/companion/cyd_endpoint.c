/* SPDX-License-Identifier: MIT */
#include "cyd_endpoint.h"

static void put14(uint8_t *p, uint16_t v) { p[0]=(uint8_t)(v&127u);p[1]=(uint8_t)((v>>7)&127u); }
static size_t frame(uint8_t *out,uint8_t op,uint32_t session,uint16_t sequence,uint8_t size) {
    unsigned i;
    out[0]=0xf0;out[1]=0x7d;out[2]='C';out[3]='Y';out[4]=1;out[5]=0;out[6]=op;
    for(i=0;i<4;i++)out[7+i]=(uint8_t)((session>>(7u*i))&127u);
    put14(out+11,sequence);out[13]=size;out[14+size]=0xf7;
    return 15u+size;
}
static size_t error(uint8_t *out,uint32_t session,uint16_t sequence,uint8_t code) {
    size_t n=frame(out,CYD_ERROR,session,sequence,1);out[14]=code;return n;
}
void cyd_endpoint_init(CydEndpoint *s,uint8_t source,void *context,CydApply apply,CydRead read) {
    *s=(CydEndpoint){0};s->source=source;s->context=context;s->apply=apply;s->read=read;
}
int cyd_endpoint_receive(CydEndpoint *s,const uint8_t *d,size_t n,uint32_t now,uint8_t out[CYD_ENDPOINT_MAX_FRAME],size_t *out_n) {
    uint32_t session=0;
    uint16_t sequence,delta;
    uint8_t op,bytes,code=0;
    unsigned i;
    *out_n=0;
    if(!d||n<4||d[0]!=0xf0||d[1]!=0x7d||d[2]!='C'||d[3]!='Y')return 0;
    if(n<15||n>CYD_ENDPOINT_MAX_FRAME||d[n-1]!=0xf7||n!=15u+d[13]){s->rejected++;return 1;}
    for(i=1;i+1<n;i++)if(d[i]>127){s->rejected++;return 1;}
    for(i=0;i<4;i++)session|=(uint32_t)d[7+i]<<(7u*i);
    if(!session){s->rejected++;return 1;}
    sequence=(uint16_t)(d[11]|((uint16_t)d[12]<<7));op=d[6];bytes=d[13];
    if(d[4]!=1||d[5]!=0)code=2;
    else if(op==CYD_DISCOVER) {
        if(bytes!=1||d[14]!=2)code=4;
        else if(s->session && s->session!=session)code=3;
        else if(s->source<1||s->source>3)code=4;
        else {
            if(!s->session){s->session=session;s->sequence=sequence;s->last_ms=now;}
            /* Discovery retry can recover a lost Identity, but an old
             * handshake must not keep notes alive by renewing the lease. */
            s->accepted++;
            *out_n=frame(out,CYD_IDENTITY,session,sequence,6);
            out[14]=2;out[15]=1;out[16]=0;out[17]=31;out[18]=0;out[19]=s->source;
            return 1;
        }
    } else if(!s->session||session!=s->session)code=3;
    else {
        delta=(uint16_t)((sequence-s->sequence)&0x3fffu);
        if(!delta||delta>=0x2000u)code=6;
        else {
            /* A refused mutation consumes its sequence too, matching the
             * native endpoint. It cannot later become a valid replay. */
            s->sequence=sequence;s->reply_pending=0;
            switch(op) {
            case CYD_GET_STATE:case CYD_PANIC:if(bytes)code=1;break;
            case CYD_SET_PARAMETER:if(bytes!=2)code=1;else if(d[14]>=4)code=5;break;
            case CYD_SET_PRESET:if(bytes!=1)code=1;else if(d[14]>=4)code=5;break;
            case CYD_NOTE:if(bytes!=2)code=1;else if(d[14]<36||d[14]>84)code=5;break;
            default:code=4;break;
            }
            if(!code && op!=CYD_GET_STATE && (!s->apply||!s->apply(s->context,op,d+14)))code=4;
            if(!code) {
                s->reply_sequence=sequence;s->reply_pending=1;
                s->last_ms=now;s->accepted++;return 1;
            }
        }
    }
    s->rejected++;*out_n=error(out,session,sequence,code);return 1;
}
size_t cyd_endpoint_reply(CydEndpoint *s,uint8_t out[CYD_ENDPOINT_MAX_FRAME]) {
    CydState state;
    unsigned i;
    size_t n;
    if(!s->session||!s->reply_pending||!s->read||!s->read(s->context,&state))return 0;
    if(state.preset>=4||state.note<36||state.note>84||state.gate>1||state.output_peak>127||state.revision>16383)return 0;
    for(i=0;i<8;i++)if(state.values[i]>127)return 0;
    for(i=0;i<6;i++)if(state.meters[i]>127)return 0;
    n=frame(out,CYD_STATE,s->session,s->reply_sequence,23);
    out[14]=15;out[15]=0;
    for(i=0;i<8;i++)out[16+i]=state.values[i];
    out[24]=state.preset;out[25]=state.note;out[26]=state.gate;out[27]=6;
    for(i=0;i<6;i++)out[28+i]=state.meters[i];
    out[34]=state.output_peak;put14(out+35,state.revision);
    s->reply_pending=0;return n;
}
void cyd_endpoint_disconnect(CydEndpoint *s) {
    const uint8_t empty[2]={0,0};
    if(s->session && s->apply)(void)s->apply(s->context,CYD_PANIC,empty);
    s->session=0;s->reply_pending=0;
}
void cyd_endpoint_tick(CydEndpoint *s,uint32_t now) {
    if(s->session && (uint32_t)(now-s->last_ms)>=CYD_ENDPOINT_LEASE_MS) {
        cyd_endpoint_disconnect(s);s->expired++;
    }
}
