// SPDX-License-Identifier: MIT
#include "fm1/companion.hpp"
extern "C" {
#include "grimoire_control.h"
}
#include <cassert>
#include <iostream>
using namespace fm1;
struct Fixture {
    CydOrbitCommand command{};
    CydOrbitRuntime runtime{};
    CydState state{};
};
static int apply(void *opaque,uint8_t op,const uint8_t *p) {
    auto& f=*static_cast<Fixture *>(opaque);return cyd_orbit_apply(&f.command,op,p);
}
static int readState(void *opaque,CydState *s) {
    auto& f=*static_cast<Fixture *>(opaque);*s=f.state;return 1;
}
static void render(Fixture& f) {
    cyd_orbit_sync(&f.runtime,&f.command);
    for(unsigned i=0;i<512;i++) {
        int16_t v=f.command.panic?0:cyd_orbit_next(&f.runtime);cyd_orbit_observe(&f.runtime,v);
    }
    cyd_orbit_snapshot(&f.runtime,&f.command,&f.state);
}
static void exchange(CompanionSession& client,CydEndpoint& endpoint,Fixture& f,MidiMessage message,uint32_t now) {
    assert(message.size);client.sent(message,now);
    MidiMessage reply;size_t n=0;
    assert(cyd_endpoint_receive(&endpoint,message.data.data(),message.size,now,reply.data.data(),&n));
    if(!n){render(f);n=cyd_endpoint_reply(&endpoint,reply.data.data());}
    assert(n&&client.receive(reply.data.data(),n,now));
}
int main() {
    Fixture f;CydEndpoint endpoint;cyd_orbit_init(&f.command);render(f);
    const auto* profile=companionProfileFor(CompanionInstrument::Grimoire);
    assert(profile&&profile->major==1&&profile->minor==0&&profile->capabilities==31&&profile->parameterMask==3&&profile->presetCount==3&&profile->noteMinimum==36&&profile->noteMaximum==59);
    assert(cyd_endpoint_init_profile(&endpoint,CYD_GRIMOIRE,1,&f,apply,readState));
    CompanionSession client;client.begin(CompanionInstrument::Grimoire,42,0);
    exchange(client,endpoint,f,client.discover(0),0);
    assert(client.identity().instrument==CompanionInstrument::Grimoire&&client.identity().source==CompanionSource::NativeEngine);
    exchange(client,endpoint,f,client.requestState(1),1);
    assert(client.snapshot().validMask==3&&client.snapshot().values[0]==48&&client.snapshot().values[1]==70&&client.snapshot().meterCount==2);
    exchange(client,endpoint,f,client.setPreset(2),2);
    exchange(client,endpoint,f,client.setParameter(0,91),3);
    exchange(client,endpoint,f,client.setParameter(1,127),4);
    assert(!client.setParameter(2,127).size&&!client.setPreset(3).size&&!client.note(60,100).size);
    exchange(client,endpoint,f,client.note(59,1),5);
    assert(client.snapshot().gate&&client.snapshot().note==59&&client.snapshot().values[0]==91&&client.snapshot().outputPeak>0&&client.snapshot().meters[0]>0);
    exchange(client,endpoint,f,client.note(36,0),6);assert(client.snapshot().gate);
    exchange(client,endpoint,f,client.note(59,0),7);assert(!client.snapshot().gate);
    exchange(client,endpoint,f,client.panic(),8);assert(!client.snapshot().outputPeak&&!client.snapshot().meters[0]&&!client.snapshot().meters[1]);
    exchange(client,endpoint,f,client.note(36,100),9);cyd_endpoint_tick(&endpoint,1509);
    assert(!endpoint.session&&!f.command.gate&&f.command.panic);render(f);
    client.begin(CompanionInstrument::Grimoire,43,1510);
    exchange(client,endpoint,f,client.discover(1510),1510);
    exchange(client,endpoint,f,client.requestState(1511),1511);assert(!client.snapshot().gate&&!client.snapshot().outputPeak);
    std::cout<<"PASS: pinned common CYDaux C++ codec <-> Grimoire C endpoint, actual Orbit PCM/state, profile limits, stale release, panic and new-session recovery\n";
}
