#ifndef XENO_SAMPLE_MORPH_H
#define XENO_SAMPLE_MORPH_H
#include "material_memory.h"

/* Instrument-local, detached one-shot control trajectory. One audio owner;
 * the caller cancels before manual material edits, reset or panic. Notes and
 * releases remain independent. No transport, allocator or wall clock. */
#define XENO_MORPH_QUANTUM (XENO_RATE / 200u)
#define XENO_MORPH_MAX_STEPS 1200u

typedef struct {
    XenoMaterialMemory memory;
    uint16_t steps, elapsed, remaining;
    uint8_t from, to, position, active;
} XenoSampleMorph;

static inline void xeno_sample_morph_cancel(XenoSampleMorph *m) {
    *m = (XenoSampleMorph){0};
}

static inline int xeno_sample_morph_arm(XenoSampleMorph *m, Xeno *s,
    const XenoMaterialMemory *source, unsigned from, unsigned to, unsigned steps) {
    if (source->valid != 3u || from > 127u || to > 127u || !steps ||
        steps > XENO_MORPH_MAX_STEPS) return 0;
    XenoSampleMorph next = {0};
    for (unsigned i = 0; i < 2; ++i) {
        XenoMaterialPatch p = source->slot[i];
        if (!xeno_memory_store(&next.memory, i, p.material, p.excitation,
                               p.damping, p.coupling)) return 0;
    }
    next.steps = (uint16_t)steps;
    next.remaining = XENO_MORPH_QUANTUM;
    next.from = next.position = (uint8_t)from;
    next.to = (uint8_t)to;
    next.active = 1;
    *m = next;
    xeno_memory_morph(&m->memory, from, s);
    return 1;
}

static inline void xeno_sample_morph_render(XenoSampleMorph *m, Xeno *s,
    int16_t *out, size_t frames) {
    while (frames && m->active) {
        size_t n = frames < m->remaining ? frames : m->remaining;
        xeno_render(s, out, n);
        out += n;
        frames -= n;
        m->remaining -= (uint16_t)n;
        if (!m->remaining) {
            ++m->elapsed;
            unsigned pos = ((unsigned)m->from * (m->steps - m->elapsed) +
                (unsigned)m->to * m->elapsed + m->steps / 2u) / m->steps;
            if (pos != m->position) {
                xeno_memory_morph(&m->memory, pos, s);
                m->position = (uint8_t)pos;
            }
            if (m->elapsed == m->steps) m->active = 0;
            else m->remaining = XENO_MORPH_QUANTUM;
        }
    }
    if (frames) xeno_render(s, out, frames);
}
#endif
