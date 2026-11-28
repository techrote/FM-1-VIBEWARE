/* Original VIBEWARE standalone adapter; emulator experiment only. */
#define APP_NAME "CHRONOMORPH"
#include "platform.c"
#include "chrono_runtime.h"
#if BOARD_SMK37 || FS != 44100u || CM_RATE != 24000u
#error Wrong target audio contract
#endif
static CmRuntime runtime;
static CmScorePanel score_panel;
static volatile uint32_t cmd=112u|(84u<<8)|(12u<<15), score_epoch;
static volatile uint32_t consumed_cmd=~0u, consumed_epoch, audio_status;
static void app_audio(int32_t *out,uint32_t n) {
    uint32_t c=cmd, epoch=score_epoch;
    cm_runtime_score_panel(&runtime,&score_panel,c,epoch,out,n);
    audio_status=(runtime.core.playing||runtime.retiring?1u:0u)|
                 (cm_score_peek(&runtime.score.cursor)?2u:0u);
    consumed_cmd=c; consumed_epoch=epoch;
}
static void app_main(void) {
    CmPanel p={0}; cm_panel_preset(&p,0);
    uint32_t prior=0,shown=~0u,shown_status=~0u,sequence=0;
    static const char *const names[]={"GLASS LATTICE","BROKEN MERIDIAN","SLOW ECLIPSE"};
    for(;;) {
        platform_poll();
        /* Single-core main/ISR handoff: read back only an acknowledged
         * command pair, never a stale completion from the prior score. */
        uint32_t lock=irq_save(), status=0;
        if(consumed_cmd==cmd && consumed_epoch==score_epoch) {
            status=audio_status;
            p.playing=(status&1u)!=0;
        }
        irq_restore(lock);
        uint32_t released,buttons=fm1_input_edges(&released);
        uint32_t keys=fm1_in.notes,down=(keys&~prior)|fm1_input_note_edges();
        prior=keys;
        if(buttons&(1u<<BTN_SEL)) cm_panel_preset(&p,p.preset+1u);
        for(unsigned k=0;k<27;k++) if(down&(1u<<k)) p.warp=(int)(k*120u/26u)-60;
        p.bpm=(unsigned)cm_panel_adjust((int)p.bpm,fm1_enc_take(ENC_KNOB1),40,220);
        p.warp=cm_panel_adjust(p.warp,fm1_enc_take(ENC_KNOB2),-60,60);
        p.variation=(unsigned)cm_panel_adjust((int)p.variation,fm1_enc_take(ENC_KNOB3),0,100);
        if(buttons&(1u<<BTN_PLAY)) p.playing^=1u;
        if(buttons&(1u<<BTN_HOME)) p.playing=0;
        else if(buttons&(1u<<BTN_SEQ)) { p.playing=1; sequence++; }
        uint32_t c=cm_panel_cmd(&p);
        lock=irq_save(); cmd=c; score_epoch=sequence; irq_restore(lock);
        if(c!=shown || status!=shown_status) {
            draw_text_box(0,10,240,&FONT_L,"CHRONOMORPH",C_WHITE,1);
            draw_text_box(0,58,240,&FONT_S,names[p.preset],C_WHITE,1);
            draw_text_box(0,100,240,&FONT_S,p.playing?(status&2u?"SCORE RUNNING":"RUNNING"):"PAUSED",C_WHITE,1);
            draw_text_box(0,144,240,&FONT_S,"K1 TEMPO / K2 WARP / K3 VAR",C_WHITE,1);
            draw_text_box(0,180,240,&FONT_S,"KEY WARP / SCL PRESET RESET",C_WHITE,1);
            draw_text_box(0,210,240,&FONT_S,"SEQ SCORE / PLAY / HOME",C_WHITE,1);
            shown=c; shown_status=status;
        }
    }
}
