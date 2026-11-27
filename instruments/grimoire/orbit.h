#ifndef GRIMOIRE_ORBIT_H
#define GRIMOIRE_ORBIT_H
#include <stdint.h>
#include <stddef.h>
#define ORBIT_RATE 24000u
#define ORBIT_VERSION 1u
typedef struct {
    uint32_t phase[3], env, energy, ticks;
    int32_t low;
    uint8_t x,y,preset,gate;
} Orbit;
void orbit_reset(Orbit *s, unsigned preset);
void orbit_xy(Orbit *s, unsigned x, unsigned y);
void orbit_gate(Orbit *s, unsigned on);
void orbit_panic(Orbit *s);
void orbit_render(Orbit *s, int16_t *out, size_t n);
#endif
