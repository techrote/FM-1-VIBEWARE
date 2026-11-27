/* Original VIBEWARE adapter. Linked against the separately fetched Dinghy platform
 * only in an owner-authorized emulator experiment. No physical installation. */
#define APP_NAME "ORBIT GATE"
#include "platform.c"
#include "orbit.h"
#include "rate.h"
#if BOARD_SMK37 || FS != 44100u || ORBIT_RATE != 24000u
#error Wrong target audio contract
#endif
static Orbit orbit;
static VwRate rate;
/* Aligned 32-bit snapshot: only main publishes; only audio ISR owns DSP state. */
static volatile uint32_t cmd=(48u|(70u<<7)|(1u<<17));
static unsigned initialized;
static int16_t next_sample(void *ctx) {
    int16_t v;
    orbit_render((Orbit *)ctx,&v,1);
    return v;
}
static void app_audio(int32_t *out,uint32_t n) {
    uint32_t c=cmd;
    unsigned x=c&127u,y=(c>>7)&127u,p=(c>>14)&3u;
    if(!initialized || orbit.preset!=p) {
        orbit_reset(&orbit,p);
        vw_rate_clear(&rate);
        initialized=1;
    }
    if(c&(1u<<17)) {
        orbit_panic(&orbit);
        vw_rate_clear(&rate);
        return; /* Dinghy clears buffer before callback. */
    }
    orbit_xy(&orbit,x,y);
    orbit_gate(&orbit,(c>>16)&1u);
    for(uint32_t i=0;i<n;i++) {
        int32_t v=vw_rate_step(&rate,next_sample,&orbit);
        out[2u*i]+=v; out[2u*i+1u]+=v;
    }
}
static void app_main(void) {
    unsigned x=48,y=70,p=0,gate=0,panic=1;
    uint32_t prior=0,shown=~0u;
    for(;;) {
        platform_poll();
        uint32_t released,buttons=fm1_input_edges(&released);
        uint32_t keys=fm1_in.notes,down=(keys&~prior)|fm1_input_note_edges();
        prior=keys;
        for(unsigned k=0;k<27;k++) if(down&(1u<<k)) x=k*127u/26u;
        int32_t d=fm1_enc_take(ENC_KNOB1);
        if(d>127)d=127;
        if(d< -127)d= -127;
        int32_t next=(int32_t)y+d;
        y=next<0?0u:next>127?127u:(unsigned)next;
        if(buttons&(1u<<BTN_SEL)) p=(p+1u)%3u;
        if(buttons&(1u<<BTN_PLAY)) {gate^=1u;panic=0;}
        if(buttons&(1u<<BTN_HOME)) {gate=0;panic=1;}
        uint32_t c=x|(y<<7)|(p<<14)|(gate<<16)|(panic<<17);
        cmd=c;
        if(c!=shown) {
            draw_text_box(0,10,240,&FONT_L,"ORBIT GATE",C_WHITE,1);
            draw_text_box(0,58,240,&FONT_S,p==0?"AMBER":p==1?"IRON":"ABYSS",C_WHITE,1);
            draw_text_box(0,100,240,&FONT_S,gate?"PLAYING":"STOPPED",C_WHITE,1);
            draw_text_box(0,144,240,&FONT_S,"KEY PITCH / K1 MATERIAL",C_WHITE,1);
            draw_text_box(0,180,240,&FONT_S,"SEL PRESET / PLAY GATE",C_WHITE,1);
            draw_text_box(0,210,240,&FONT_S,"HOME PANIC",C_WHITE,1);
            shown=c;
        }
    }
}
