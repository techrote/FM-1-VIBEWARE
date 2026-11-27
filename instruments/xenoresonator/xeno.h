#ifndef XENO_H
#define XENO_H
#include <stdint.h>
#include <stddef.h>
#define XENO_RATE 24000u
#define XENO_MODES 6u
#define XENO_PRESETS 4u
/* Local semantic API; no wire or target ABI implied. */
typedef struct {
    int32_t re[XENO_MODES], im[XENO_MODES];
    int16_t cs[XENO_MODES], sn[XENO_MODES];
    uint32_t rng;
    uint16_t burst;
    uint8_t material, note, velocity, excitation, damping, coupling, held;
} Xeno;
void xeno_reset(Xeno *s, uint32_t seed, unsigned material);
void xeno_controls(Xeno *s, unsigned excitation, unsigned damping, unsigned coupling);
void xeno_material(Xeno *s, unsigned material);
void xeno_strike(Xeno *s, unsigned note, unsigned velocity);
void xeno_release(Xeno *s);
void xeno_panic(Xeno *s);
void xeno_render(Xeno *s, int16_t *out, size_t frames);
/* Local state magnitude proxy, not audio RMS or device telemetry. */
uint32_t xeno_mode_level(const Xeno *s, unsigned mode);
#endif
