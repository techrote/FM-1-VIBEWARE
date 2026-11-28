/* SPDX-License-Identifier: MIT */
#ifndef VIBEWARE_CYD_ENDPOINT_H
#define VIBEWARE_CYD_ENDPOINT_H
#include <stdint.h>
#include <stddef.h>
#ifdef __cplusplus
extern "C" {
#endif
/* CY1 compatibility is exercised against FM-1-CYDaux's C++ codec in test_contract.cpp.
 * Profiles: Xenoresonator identity 2 and Grimoire identity 3, both 1.0.
 * Source is declared by the build: 1 native, 2 emulated firmware, 3 device.
 * A source tag is never a physical qualification receipt. */
#define CYD_ENDPOINT_MAX_FRAME 63u
#define CYD_ENDPOINT_LEASE_MS 1500u
enum { CYD_XENORESONATOR=2, CYD_GRIMOIRE=3 };
enum { CYD_DISCOVER=1, CYD_IDENTITY, CYD_GET_STATE, CYD_STATE,
       CYD_SET_PARAMETER, CYD_SET_PRESET, CYD_NOTE, CYD_PANIC, CYD_ERROR };
typedef struct {
    uint8_t values[8], preset, note, gate, meters[6], output_peak;
    uint16_t revision;
} CydState;
typedef int (*CydApply)(void *, uint8_t op, const uint8_t *payload);
typedef int (*CydRead)(void *, CydState *);
typedef struct {
    uint32_t session, last_ms, accepted, rejected, expired;
    uint16_t sequence, reply_sequence;
    uint8_t source, reply_pending, instrument;
    void *context;
    CydApply apply;
    CydRead read;
} CydEndpoint;
void cyd_endpoint_init(CydEndpoint *, uint8_t source, void *, CydApply, CydRead);
/* Select a reviewed profile at initialization; unknown identities fail closed.
 * The legacy initializer retains Xenoresonator behavior. No wire negotiation
 * beyond the existing CY1 Discovery/Identity exchange is introduced. */
int cyd_endpoint_init_profile(CydEndpoint *, uint8_t instrument, uint8_t source, void *, CydApply, CydRead);
/* Returns zero only for another SysEx namespace, otherwise one. reply_size is
 * always initialized; replies never exceed 38 bytes. Unknown/malformed data
 * cannot mutate engine state or extend its lease. */
int cyd_endpoint_receive(CydEndpoint *, const uint8_t *, size_t, uint32_t now,
                         uint8_t reply[CYD_ENDPOINT_MAX_FRAME], size_t *reply_size);
/* Coalesces state replies to the newest accepted command. read may return zero
 * until the audio callback has applied the published command, with no waiting. */
size_t cyd_endpoint_reply(CydEndpoint *, uint8_t reply[CYD_ENDPOINT_MAX_FRAME]);
void cyd_endpoint_tick(CydEndpoint *, uint32_t now);
void cyd_endpoint_disconnect(CydEndpoint *);
#ifdef __cplusplus
}
#endif
#endif
