#ifndef CHRONO_H
#define CHRONO_H
#include <stdint.h>
#define CM_RATE 24000u
#define CM_LANES 3u
#define CM_CYCLE (CM_RATE*60u*100u)
typedef struct {
    uint32_t clock, phase, increment, rng, hits, ticks;
    uint16_t mask, env;
    uint8_t length, step, cycle;
} cm_lane;
typedef struct {
    cm_lane lane[CM_LANES];
    uint32_t master, noise;
    uint16_t bpm;
    int8_t warp;
    uint8_t beat, variation, playing, preset;
} cm_state;
void cm_reset(cm_state *s, uint32_t seed, unsigned preset);
int cm_controls(cm_state *s, unsigned bpm, int warp, unsigned variation);
int cm_pattern(cm_state *s, unsigned lane, unsigned length, unsigned mask);
void cm_start(cm_state *s);
void cm_stop(cm_state *s);
void cm_render(cm_state *s, int16_t *out, unsigned count);
#endif
