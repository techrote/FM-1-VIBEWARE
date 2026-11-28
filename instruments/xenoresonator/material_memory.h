#ifndef XENO_MATERIAL_MEMORY_H
#define XENO_MATERIAL_MEMORY_H
#include "xeno.h"

/* Optional local semantic controller, not a wire format. Single owner at
 * committed audio-block boundaries; caller owns session invalidation. */
typedef struct {
    uint8_t material, excitation, damping, coupling;
} XenoMaterialPatch;
typedef struct {
    XenoMaterialPatch slot[2];
    uint8_t valid;
} XenoMaterialMemory;

static inline void xeno_memory_init(XenoMaterialMemory *m) {
    *m = (XenoMaterialMemory){0};
}
static inline int xeno_memory_store(XenoMaterialMemory *m, unsigned slot,
    unsigned p, unsigned e, unsigned d, unsigned c) {
    if (slot >= 2u || p >= XENO_PRESETS || e > 127u || d > 127u || c > 127u)
        return 0;
    m->slot[slot] = (XenoMaterialPatch){(uint8_t)p,(uint8_t)e,(uint8_t)d,(uint8_t)c};
    m->valid |= (uint8_t)(1u << slot);
    return 1;
}
static inline int xeno_memory_capture(XenoMaterialMemory *m, unsigned slot, const Xeno *s) {
    return xeno_memory_store(m,slot,s->material,s->excitation,s->damping,s->coupling);
}
static inline unsigned xeno_memory_mix(unsigned a, unsigned b, unsigned pos) {
    return (a*(127u-pos)+b*pos+63u)/127u;
}
static inline void xeno_memory_apply(Xeno *s, XenoMaterialPatch p) {
    xeno_controls(s,p.excitation,p.damping,p.coupling);
    if (s->material != p.material) xeno_material(s,p.material);
}
static inline int xeno_memory_recall(const XenoMaterialMemory *m, unsigned slot, Xeno *s) {
    if (slot >= 2u || !(m->valid & (1u << slot))) return 0;
    xeno_memory_apply(s,m->slot[slot]);
    return 1;
}
static inline int xeno_memory_morph(const XenoMaterialMemory *m, unsigned pos, Xeno *s) {
    if (m->valid != 3u || pos > 127u) return 0;
    XenoMaterialPatch a=m->slot[0], b=m->slot[1];
    XenoMaterialPatch p={pos < 64u ? a.material : b.material,
        (uint8_t)xeno_memory_mix(a.excitation,b.excitation,pos),
        (uint8_t)xeno_memory_mix(a.damping,b.damping,pos),
        (uint8_t)xeno_memory_mix(a.coupling,b.coupling,pos)};
    xeno_memory_apply(s,p);
    return 1;
}
#endif
