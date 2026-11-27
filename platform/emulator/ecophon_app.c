/* Original VIBEWARE standalone adapter; emulator experiment only. */
#define APP_NAME "ECOPHON"
#include "platform.c"
#include "ecophon_runtime.h"
#if BOARD_SMK37 || FS != 44100u || ECO_RATE != 24000u
#error Wrong target audio contract
#endif
static EcoRuntime runtime;
static volatile uint32_t cmd=180u|(40u<<8);
static void app_audio(int32_t *out,uint32_t n) {
    eco_runtime_render(&runtime,cmd,out,n);
}
static void app_main(void) {
    EcoPanel p={0}; eco_panel_preset(&p,0);
    uint32_t prior=0,shown=~0u;
    static const char *const names[]={"MUTUALISM","SCARCITY","SEASONAL BLOOM","FROZEN"};
    for(;;) {
        platform_poll();
        uint32_t released,buttons=fm1_input_edges(&released);
        uint32_t keys=fm1_in.notes,down=(keys&~prior)|fm1_input_note_edges();
        prior=keys;
        if(buttons&(1u<<BTN_SEL)) eco_panel_preset(&p,p.preset+1u);
        for(unsigned k=0;k<27;k++) if(down&(1u<<k)) p.pressure=k*255u/26u;
        p.fertility=eco_panel_adjust(p.fertility,fm1_enc_take(ENC_KNOB1));
        p.pressure=eco_panel_adjust(p.pressure,fm1_enc_take(ENC_KNOB2));
        if(buttons&(1u<<BTN_PLAY)) p.playing^=1u;
        if(buttons&(1u<<BTN_HOME)) p.playing=0;
        uint32_t c=eco_panel_cmd(&p); cmd=c;
        if(c!=shown) {
            draw_text_box(0,10,240,&FONT_L,"ECOPHON",C_WHITE,1);
            draw_text_box(0,58,240,&FONT_S,names[p.preset],C_WHITE,1);
            draw_text_box(0,100,240,&FONT_S,p.playing?"LIVING":"PAUSED",C_WHITE,1);
            draw_text_box(0,144,240,&FONT_S,"K1 FERTILITY / K2 PRESSURE",C_WHITE,1);
            draw_text_box(0,180,240,&FONT_S,"KEY PRESSURE / SEL RESET",C_WHITE,1);
            draw_text_box(0,210,240,&FONT_S,"PLAY / HOME MUTE",C_WHITE,1);
            shown=c;
        }
    }
}
