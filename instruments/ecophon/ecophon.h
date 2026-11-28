#ifndef ECOPHON_H
#define ECOPHON_H
#include <stdint.h>
#include <stddef.h>
#define ECO_AGENTS 8
#define ECO_PATCHES 4
#define ECO_RATE 24000u
#define ECO_TICK 240u
#define ECO_CAP 4096u
typedef struct { uint32_t phase, inc; uint16_t energy, age, envelope; uint8_t patch, species, trait, alive; } EcoAgent;
typedef struct { EcoAgent a[ECO_AGENTS]; uint16_t resource[ECO_PATCHES]; uint32_t rng, ticks, births, deaths, gifts, moves, consumed; uint16_t countdown; uint8_t fertility, sharing, pressure, regime, ablation, muted; } Eco;
void eco_reset(Eco *e, uint32_t seed, unsigned preset);
void eco_controls(Eco *e, unsigned fertility, unsigned sharing, unsigned pressure, unsigned ablation);
void eco_mute(Eco *e, unsigned mute);
void eco_render(Eco *e, int16_t *out, size_t frames);
#endif
