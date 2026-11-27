#include "session.h"
#include <string.h>
void os_init(OrbitSession *s){memset(s,0,sizeof(*s));orbit_reset(&s->core,0);}
void os_disconnect(OrbitSession *s){s->connected=0;orbit_panic(&s->core);}
uint32_t os_connect(OrbitSession *s,unsigned version){
    os_disconnect(s);
    if(version!=ORBIT_VERSION || s->generation==UINT32_MAX)return 0;
    s->generation++;s->connected=1;return s->generation;
}
int os_event(OrbitSession *s,uint32_t generation,unsigned op,unsigned a,unsigned b){
    if(!s->connected||generation!=s->generation)return 0;
    switch(op){
    case ORBIT_XY: if(a>127||b>127)return 0;orbit_xy(&s->core,a,b);break;
    case ORBIT_GATE: if(a>1||b)return 0;orbit_gate(&s->core,a);break;
    case ORBIT_PRESET: if(a>2||b)return 0;orbit_reset(&s->core,a);break;
    case ORBIT_PANIC: if(a||b)return 0;orbit_panic(&s->core);break;
    default:return 0;
    }
    return 1;
}
void os_render(OrbitSession *s,int16_t *out,size_t n){orbit_render(&s->core,out,n);}
