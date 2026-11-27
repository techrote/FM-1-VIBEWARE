// SPDX-License-Identifier: MIT
#include "fm1/companion.hpp"
#include "cyd_endpoint.h"
#include <cassert>
#include <cstring>
#include <iostream>
#include <array>
extern "C" {
#include "xeno.h"
}
using namespace fm1;
struct Fixture {Xeno x{};uint16_t revision=0;uint8_t peak=0,preset=0;};
static int apply(void* opaque,uint8_t op,const uint8_t* p) {
    auto& f=*static_cast<Fixture*>(opaque);
    if(op==CYD_SET_PARAMETER) {
        if(p[0]==0)f.x.excitation=p[1];
        else if(p[0]==1)f.x.damping=p[1];
        else if(p[0]==2)f.x.coupling=p[1];
        else if(p[0]==3)xeno_material(&f.x,(unsigned(p[1])*3+63)/127);
        else return 0;
    } else if(op==CYD_SET_PRESET) {xeno_reset(&f.x,0x43594431u,p[0]);f.preset=p[0];}
    else if(op==CYD_NOTE) {if(p[1])xeno_strike(&f.x,p[0],p[1]);else if(f.x.note==p[0])xeno_release(&f.x);}
    else if(op==CYD_PANIC)xeno_panic(&f.x);
    else return 0;
    f.revision=(f.revision+1)&16383;return 1;
}
static int readState(void* opaque,CydState* s) {
    auto& f=*static_cast<Fixture*>(opaque);*s={};
    s->values[0]=f.x.excitation;s->values[1]=f.x.damping;s->values[2]=f.x.coupling;
    s->values[3]=static_cast<uint8_t>((f.x.material*127+1)/3);
    s->preset=f.preset;s->note=f.x.note;s->gate=f.x.held;s->output_peak=f.peak;s->revision=f.revision;
    for(unsigned i=0;i<6;i++)s->meters[i]=static_cast<uint8_t>(xeno_mode_level(&f.x,i)*127/131070);
    return 1;
}
static MidiMessage exchange(CydEndpoint& endpoint,const MidiMessage& message,uint32_t now) {
    MidiMessage reply;size_t size=0;
    assert(cyd_endpoint_receive(&endpoint,message.data.data(),message.size,now,reply.data.data(),&size));
    if(!size)size=cyd_endpoint_reply(&endpoint,reply.data.data());
    reply.size=static_cast<uint16_t>(size);return reply;
}
static void accepted(CompanionSession& client,CydEndpoint& endpoint,MidiMessage message,uint32_t now) {
    assert(message.size);client.sent(message,now);
    const auto reply=exchange(endpoint,message,now);
    assert(reply.size && client.receive(reply.data.data(),reply.size,now));
}
int main() {
    Fixture f;xeno_reset(&f.x,0x43594431u,0);CydEndpoint endpoint;
    cyd_endpoint_init(&endpoint,1,&f,apply,readState);
    CompanionSession client;client.begin(CompanionInstrument::Xenoresonator,0x1234567,0);
    accepted(client,endpoint,client.discover(0),0);
    accepted(client,endpoint,client.requestState(1),1);
    assert(client.snapshot().values[0]==76 && client.identity().capabilities==31);
    accepted(client,endpoint,client.setPreset(2),2);
    accepted(client,endpoint,client.setParameter(0,127),3);
    accepted(client,endpoint,client.setParameter(2,90),4);
    assert(f.x.material==2 && client.snapshot().preset==2);
    accepted(client,endpoint,client.note(48,110),5);
    std::array<int16_t,2048> pcm{};xeno_render(&f.x,pcm.data(),pcm.size());
    Xeno independent;xeno_reset(&independent,0x43594431u,2);xeno_controls(&independent,127,38,90);
    xeno_strike(&independent,48,110);std::array<int16_t,2048> reference{};
    xeno_render(&independent,reference.data(),reference.size());assert(pcm==reference);
    unsigned nonzero=0;for(auto sample:pcm)if(sample)nonzero++;
    std::cout<<"2048-frame actual-core strike nonzero samples="<<nonzero<<"\n"<<std::flush;
    assert(nonzero>256 && f.x.held);
    const auto last=client.note(48,0);accepted(client,endpoint,last,6);
    assert(!f.x.held);
    auto duplicate=exchange(endpoint,last,7);CompanionPacket packet;
    assert(decodeCompanion(duplicate.data.data(),duplicate.size,packet) && packet.op==CompanionOp::Error && packet.payload[0]==6);
    accepted(client,endpoint,client.note(60,100),8);
    const auto oldSession=endpoint.session;cyd_endpoint_tick(&endpoint,1508);
    assert(!endpoint.session && endpoint.expired==1 && !f.x.held);
    assert(oldSession==0x1234567);
    client.begin(CompanionInstrument::Xenoresonator,oldSession+1,1510);
    accepted(client,endpoint,client.discover(1510),1510);
    const auto stale=exchange(endpoint,last,1511);
    assert(decodeCompanion(stale.data.data(),stale.size,packet) && packet.payload[0]==3);
    accepted(client,endpoint,client.note(72,127),1512);
    accepted(client,endpoint,client.panic(),1513);
    xeno_render(&f.x,pcm.data(),pcm.size());for(auto sample:pcm)assert(!sample);
    auto malformed=client.setParameter(0,88);
    const auto before=endpoint.accepted;
    for(std::size_t n=0;n<malformed.size;n++) {
        uint8_t out[CYD_ENDPOINT_MAX_FRAME];size_t outSize=999;
        cyd_endpoint_receive(&endpoint,malformed.data.data(),n,1600,out,&outSize);
        assert(endpoint.accepted==before && f.x.excitation==127);
    }
    for(unsigned n=0;n<20000;n++) accepted(client,endpoint,client.setParameter(1,n%128),2000+n);
    std::cout<<"CY1 independent C/C++ interoperability with actual Xeno core: PASS; 20000 sequence-wrap controls, lease/panic/session/malformed/audio checks\n";
}
