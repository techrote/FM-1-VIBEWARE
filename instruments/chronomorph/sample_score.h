#ifndef CM_SAMPLE_SCORE_H
#define CM_SAMPLE_SCORE_H
#include "scene_memory.h"

/* Sample-clock scene performance for the serialized native audio owner.
 * No wall clock, allocation, target ABI or wire encoding. Zero-initialize.
 * Arm only while playing; caller owns transport and cancels on effective
 * manual edits/takeover, reset or panic (not ignored remote commands).
 * A natural completion stops the core at the exact final scored sample;
 * outer rate converters must retire the final audio before marking stopped.
 * External stop/panic must still flush any outer cached audio immediately. */
typedef struct {
    cm_score cursor;
    uint16_t offset;
} cm_sample_score;

static inline void cm_sample_score_cancel(cm_sample_score *p) {
    cm_score_cancel(&p->cursor);
    p->offset=0;
}

static inline int cm_sample_score_begin(cm_sample_score *p, const cm_state *s,
                                        const cm_scene_bank *b, unsigned seconds) {
    if (!s->playing || !cm_score_begin(&p->cursor,b,seconds)) return 0;
    p->offset=0;
    return 1;
}

/* Returns 1 exactly once for natural completion, 0 otherwise. A zero-size
 * callback does not advance or apply a cue. Controls are applied at the
 * original 1200-frame semantic block boundaries, including the first. */
static inline int cm_sample_score_render(cm_sample_score *p, cm_state *s,
                                         int16_t *out, unsigned count) {
    int completed=0;
    if (!count) return 0;
    if (!s->playing) cm_sample_score_cancel(p);
    while (count && cm_score_peek(&p->cursor)) {
        if (!p->offset) cm_scene_apply(s,cm_score_peek(&p->cursor));
        unsigned n=CM_SCORE_BLOCK_FRAMES-p->offset;
        if (n>count) n=count;
        cm_render(s,out,n);
        out+=n; count-=n;
        p->offset=(uint16_t)(p->offset+n);
        if (p->offset==CM_SCORE_BLOCK_FRAMES) {
            p->offset=0;
            if (!cm_score_advance(&p->cursor)) {
                cm_stop(s);
                completed=1;
            }
        }
    }
    if (count) cm_render(s,out,count);
    return completed;
}
#endif
