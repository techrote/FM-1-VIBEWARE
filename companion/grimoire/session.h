#ifndef GRIMOIRE_SESSION_H
#define GRIMOIRE_SESSION_H
#include "../../instruments/grimoire/orbit.h"
/* Local simulator contract, NOT an FM-1 wire protocol. */
typedef struct { Orbit core; uint32_t generation; uint8_t connected; } OrbitSession;
enum { ORBIT_XY=1, ORBIT_GATE=2, ORBIT_PRESET=3, ORBIT_PANIC=4 };
void os_init(OrbitSession *s);
uint32_t os_connect(OrbitSession *s,unsigned version);
void os_disconnect(OrbitSession *s);
int os_event(OrbitSession *s,uint32_t generation,unsigned op,unsigned a,unsigned b);
void os_render(OrbitSession *s,int16_t *out,size_t n);
#endif
