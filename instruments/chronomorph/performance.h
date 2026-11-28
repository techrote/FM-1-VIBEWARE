#ifndef CM_PERFORMANCE_H
#define CM_PERFORMANCE_H
#include "scene_memory.h"

/* Instrument-local semantic interface v1, not a serialized or wire ABI.
 * Only the serialized audio owner may mutate core/owner or sample snapshots.
 * Caller validates session/profile/sequence, queues commands, cancels any
 * active score on manual takeover, and flushes cached audio on FLUSH. */
#define CM_PERFORMANCE_VERSION 1u
enum { CM_OWNER_NONE, CM_OWNER_PANEL, CM_OWNER_COMPANION };
enum { CM_ORIGIN_PANEL, CM_ORIGIN_COMPANION, CM_ORIGIN_SESSION_LOST };
enum { CM_TRANSPORT_START, CM_TRANSPORT_STOP, CM_TRANSPORT_PANIC };
enum { CM_PERF_REJECT = 0, CM_PERF_ACCEPT = 1, CM_PERF_FLUSH = 2, CM_PERF_IGNORED = 4 };

static inline unsigned cm_perf_transport(cm_state *s, uint8_t *owner,
                                        unsigned origin, unsigned op) {
    if (origin == CM_ORIGIN_SESSION_LOST) {
        if (op != CM_TRANSPORT_STOP) return CM_PERF_REJECT;
        if (*owner != CM_OWNER_COMPANION) return CM_PERF_ACCEPT | CM_PERF_IGNORED;
    } else if (origin != CM_ORIGIN_PANEL && origin != CM_ORIGIN_COMPANION) {
        return CM_PERF_REJECT;
    }
    if (op == CM_TRANSPORT_START) {
        /* Duplicate remote start cannot steal an already-running panel score.
         * An explicit panel start can always take local ownership. */
        if (origin == CM_ORIGIN_COMPANION && s->playing && *owner == CM_OWNER_PANEL)
            return CM_PERF_ACCEPT | CM_PERF_IGNORED;
        if (origin == CM_ORIGIN_PANEL || !s->playing)
            *owner = origin == CM_ORIGIN_PANEL ? CM_OWNER_PANEL : CM_OWNER_COMPANION;
        cm_start(s);
        return CM_PERF_ACCEPT;
    }
    if (op != CM_TRANSPORT_STOP && op != CM_TRANSPORT_PANIC)
        return CM_PERF_REJECT;
    if (op == CM_TRANSPORT_STOP && origin == CM_ORIGIN_COMPANION &&
        *owner == CM_OWNER_PANEL) return CM_PERF_ACCEPT | CM_PERF_IGNORED;
    cm_stop(s);
    *owner = CM_OWNER_NONE;
    return CM_PERF_ACCEPT | CM_PERF_FLUSH;
}

/* Explicit preset/reset is global, stopped, and requires rate-cache flush.
 * Reject invalid presets before changing either the core or ownership. */
static inline unsigned cm_perf_reset(cm_state *s, uint8_t *owner,
                                    unsigned preset, uint32_t seed) {
    if (preset >= 3u) return CM_PERF_REJECT;
    cm_reset(s, seed, preset);
    *owner = CM_OWNER_NONE;
    return CM_PERF_ACCEPT | CM_PERF_FLUSH;
}

/* Whole edits preserve clock phase, seed and ownership. Validation precedes
 * mutation, including for all three lanes. Individual parameter and pattern
 * edits use the existing cm_controls / cm_pattern operations. */
static inline int cm_perf_scene(cm_state *s, const cm_scene *scene) {
    return cm_scene_apply(s, scene);
}

typedef struct {
    uint32_t clock, ticks, hits;
    uint16_t mask;
    uint8_t length, step, cycle;
} cm_perf_lane;
typedef struct {
    cm_perf_lane lane[CM_LANES];
    uint32_t master;
    uint16_t bpm;
    int8_t warp;
    uint8_t variation, preset, beat, playing, owner;
} cm_perf_state;

/* Actual native state at the caller's chosen audio boundary, not device
 * telemetry until a qualified target exposes it. No unbounded event log. */
static inline void cm_perf_snapshot(cm_perf_state *v, const cm_state *s,
                                    uint8_t owner) {
    memset(v, 0, sizeof *v);
    v->master=s->master; v->bpm=s->bpm; v->warp=s->warp;
    v->variation=s->variation; v->preset=s->preset; v->beat=s->beat;
    v->playing=s->playing; v->owner=owner;
    for (unsigned i=0; i<CM_LANES; ++i) {
        const cm_lane *l=&s->lane[i];
        cm_perf_lane *d=&v->lane[i];
        d->clock=l->clock; d->ticks=l->ticks; d->hits=l->hits;
        d->mask=l->mask; d->length=l->length; d->step=l->step; d->cycle=l->cycle;
    }
}
#endif
