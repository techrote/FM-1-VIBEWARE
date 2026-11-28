#ifndef ECOPHON_ENVIRONMENT_MEMORY_H
#define ECOPHON_ENVIRONMENT_MEMORY_H
/* Local instrument semantics only. Not an ABI or transport. Advance once per
 * completed native control block; the caller owns the audio/lease lifecycle. */
#include <stdint.h>
#include <string.h>
#define ECO_MEMORY_BLOCKS 40u
typedef struct { uint8_t f,s,p; } EcoEnvironment;
typedef struct {
    EcoEnvironment current, slots[2], origin, target;
    uint8_t valid, progress, active, running, frozen;
} EcoMemory;
static inline void eco_memory_init(EcoMemory *m) { memset(m,0,sizeof *m); }
static inline void eco_memory_cancel(EcoMemory *m) { m->active=0; m->progress=0; }
static inline void eco_memory_reset(EcoMemory *m,EcoEnvironment initial) {
    eco_memory_cancel(m); m->current=initial; m->running=1; m->frozen=0;
}
static inline void eco_memory_stop(EcoMemory *m) { eco_memory_cancel(m); m->running=0; }
static inline void eco_memory_freeze(EcoMemory *m,unsigned frozen) {
    if(frozen) eco_memory_cancel(m);
    m->frozen=(uint8_t)(frozen!=0);
}
static inline int eco_memory_manual(EcoMemory *m,unsigned f,unsigned s,unsigned p) {
    if(f>255u||s>255u||p>255u) return 0;
    eco_memory_cancel(m); m->current=(EcoEnvironment){(uint8_t)f,(uint8_t)s,(uint8_t)p}; return 1;
}
static inline int eco_memory_capture(EcoMemory *m,unsigned slot) {
    if(slot>=2u) return 0;
    m->slots[slot]=m->current; m->valid=(uint8_t)(m->valid|(1u<<slot)); return 1;
}
static inline int eco_memory_recall(EcoMemory *m,unsigned slot) {
    if(slot>=2u||!m->running||m->frozen||!(m->valid&(1u<<slot))) return 0;
    m->origin=m->current; m->target=m->slots[slot]; m->progress=0; m->active=1; return 1;
}
static inline uint8_t eco_memory_mix(uint8_t a,uint8_t b,unsigned n) {
    return (uint8_t)(((unsigned)a*(ECO_MEMORY_BLOCKS-n)+(unsigned)b*n)/ECO_MEMORY_BLOCKS);
}
static inline EcoEnvironment eco_memory_next(EcoMemory *m) {
    if(m->active&&m->running&&!m->frozen) {
        unsigned n=++m->progress;
        m->current=(EcoEnvironment){eco_memory_mix(m->origin.f,m->target.f,n),
            eco_memory_mix(m->origin.s,m->target.s,n),eco_memory_mix(m->origin.p,m->target.p,n)};
        if(n==ECO_MEMORY_BLOCKS) eco_memory_cancel(m);
    }
    return m->current;
}
#endif
