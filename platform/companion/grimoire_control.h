/* SPDX-License-Identifier: MIT */
#ifndef VIBEWARE_GRIMOIRE_CONTROL_H
#define VIBEWARE_GRIMOIRE_CONTROL_H
#include "cyd_endpoint.h"
#include "orbit.h"
/* Main publishes whole commands; only the renderer owns Orbit and telemetry.
 * CY1 Note is the captured gesture's gate token, not a pitch or velocity macro.
 * Reset/panic serials preserve a safety event even if a later note arrives
 * before the audio callback. All storage is fixed and all operations bounded. */
typedef struct {
    uint32_t version,reset_serial,panic_serial;
    uint8_t x,y,preset,note,gate,panic;
} CydOrbitCommand;
typedef struct {
    Orbit core;
    uint32_t reset_serial,panic_serial,peak,env,energy;
    uint8_t initialized;
} CydOrbitRuntime;
static inline void cyd_orbit_init(CydOrbitCommand *c) {
    *c=(CydOrbitCommand){0,0,0,48,70,0,44,0,1};
}
static inline int cyd_orbit_apply(CydOrbitCommand *c,uint8_t op,const uint8_t *p) {
    if(op==CYD_SET_PARAMETER) {
        if(p[1]>127)return 0;
        if(p[0]==0)c->x=p[1];else if(p[0]==1)c->y=p[1];else return 0;
    } else if(op==CYD_SET_PRESET) {
        if(p[0]>=3)return 0;
        c->preset=p[0];c->x=48;c->y=70;c->note=44;c->gate=0;c->panic=1;c->reset_serial++;
    } else if(op==CYD_NOTE) {
        if(p[0]<36||p[0]>59||p[1]>127)return 0;
        if(p[1]){c->note=p[0];c->gate=1;c->panic=0;}
        else if(c->note==p[0])c->gate=0;
    } else if(op==CYD_PANIC) {
        c->gate=0;c->panic=1;c->panic_serial++;
    } else return 0;
    c->version++;return 1;
}
/* Ownership is a local performance policy, not a CY1 field. Explicit panic
 * and preset selection remain global safety/reset commands. Automatic
 * session loss only clears remote-owned gestures (including their tails).
 * A delayed remote release cannot cancel a panel-owned gate. */
enum { CYD_ORBIT_OWNER_NONE, CYD_ORBIT_OWNER_PANEL, CYD_ORBIT_OWNER_REMOTE };
enum { CYD_ORBIT_PANEL, CYD_ORBIT_REMOTE, CYD_ORBIT_SESSION_LOSS };
static inline int cyd_orbit_apply_owned(CydOrbitCommand *c,uint8_t *owner,
        uint8_t origin,uint8_t op,const uint8_t *p) {
    if(origin==CYD_ORBIT_SESSION_LOSS) {
        if(op!=CYD_PANIC)return 0;
        if(*owner!=CYD_ORBIT_OWNER_REMOTE)return 1;
    } else if(origin!=CYD_ORBIT_PANEL && origin!=CYD_ORBIT_REMOTE)return 0;
    if(op==CYD_NOTE && origin==CYD_ORBIT_REMOTE && *owner==CYD_ORBIT_OWNER_PANEL && !p[1]) {
        /* Validate even when the release is safely ignored. */
        return p[0]>=36 && p[0]<=59;
    }
    if(!cyd_orbit_apply(c,op,p))return 0;
    if(op==CYD_NOTE && p[1])
        *owner=origin==CYD_ORBIT_PANEL?CYD_ORBIT_OWNER_PANEL:CYD_ORBIT_OWNER_REMOTE;
    if(op==CYD_PANIC||op==CYD_SET_PRESET)*owner=CYD_ORBIT_OWNER_NONE;
    return 1;
}
static inline void cyd_orbit_clear_peaks(CydOrbitRuntime *r) {r->peak=0;r->env=0;r->energy=0;}
/* Nonzero means the outer rate converter must also clear its buffered sample. */
static inline int cyd_orbit_sync(CydOrbitRuntime *r,const CydOrbitCommand *c) {
    int reset=!r->initialized||r->reset_serial!=c->reset_serial;
    int panic=c->panic||r->panic_serial!=c->panic_serial;
    if(reset)orbit_reset(&r->core,c->preset);
    if(panic)orbit_panic(&r->core);
    if(reset||panic)cyd_orbit_clear_peaks(r);
    r->initialized=1;r->reset_serial=c->reset_serial;r->panic_serial=c->panic_serial;
    orbit_xy(&r->core,c->x,c->y);orbit_gate(&r->core,c->gate);
    return reset||panic;
}
static inline int16_t cyd_orbit_next(void *opaque) {
    CydOrbitRuntime *r=(CydOrbitRuntime *)opaque;int16_t v;
    orbit_render(&r->core,&v,1);
    if(r->core.env>r->env)r->env=r->core.env;
    if(r->core.energy>r->energy)r->energy=r->core.energy;
    return v;
}
static inline void cyd_orbit_observe(CydOrbitRuntime *r,int16_t v) {
    int32_t s=v;uint32_t magnitude=(uint32_t)(s<0?-s:s);
    if(magnitude>r->peak)r->peak=magnitude;
}
static inline uint8_t cyd_orbit_meter(uint32_t v,uint32_t maximum) {
    return (uint8_t)(v>=maximum?127u:v*127u/maximum);
}
static inline void cyd_orbit_snapshot(const CydOrbitRuntime *r,const CydOrbitCommand *c,CydState *s) {
    *s=(CydState){{0},0,0,0,{0},0,0};s->values[0]=r->core.x;s->values[1]=r->core.y;
    s->preset=r->core.preset;s->note=c->note;s->gate=r->core.gate;
    s->meters[0]=cyd_orbit_meter(r->env,32767u);s->meters[1]=cyd_orbit_meter(r->energy,28000u);
    s->output_peak=cyd_orbit_meter(r->peak,32768u);s->revision=(uint16_t)(c->version&16383u);
}
#endif
