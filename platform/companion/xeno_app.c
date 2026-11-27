/* SPDX-License-Identifier: MIT
 * Original VIBEWARE USB companion adapter; linked with the separately fetched
 * GPL-3.0 Dinghy platform only for the qualified raw-XIP emulator experiment.
 * Audio owns Xeno. Main owns protocol/USB and publishes bounded command copies.
 */
#define APP_NAME "XENO CYDAUX"
#define CYD_ENDPOINT_SERVICE 1
#include "platform.c"
#include "xeno.h"
#include "rate.h"
#include "cyd_endpoint.h"
#if BOARD_SMK37 || FS != 44100u || XENO_RATE != 24000u
#error Wrong target audio contract
#endif
typedef struct {
    uint32_t version, strike, reset, panic_serial;
    uint8_t excitation,damping,coupling,material,preset,note,velocity,gate,panic;
} Command;
static Command desired={0,0,0,0,76,38,48,0,0,48,100,0,1}, commands[2];
static volatile uint32_t command_slot, applied_version;
static CydState observations[2];
static volatile uint32_t observation_slot, observation_generation;
static volatile uint32_t telemetry_consumed;
static Xeno xeno;
static VwRate rate;
static CydEndpoint endpoint;
static uint32_t initialized,last_strike,last_reset,last_panic;
static uint32_t telemetry_ack,held_peak;
static uint8_t held_meters[6];
static volatile uint32_t target_audio_blocks,target_audio_max_ticks,target_reply_deferrals;
static uint8_t queued_reply[CYD_ENDPOINT_MAX_FRAME];
static size_t queued_size;
static void publish(void) {
    unsigned next=(command_slot^1u)&1u;
    desired.version++;
    commands[next]=desired;
    RING_PUBLISH();command_slot=next;
}
static int apply(void *ctx,uint8_t op,const uint8_t *p) {
    (void)ctx;
    if(op==CYD_SET_PARAMETER) {
        if(p[0]==0)desired.excitation=p[1];
        else if(p[0]==1)desired.damping=p[1];
        else if(p[0]==2)desired.coupling=p[1];
        else if(p[0]==3)desired.material=(uint8_t)(((unsigned)p[1]*3u+63u)/127u);
        else return 0;
    } else if(op==CYD_SET_PRESET) {
        desired.excitation=76;desired.damping=38;desired.coupling=48;
        desired.material=desired.preset=p[0];desired.note=48;desired.gate=0;desired.panic=1;desired.reset++;
    } else if(op==CYD_NOTE) {
        if(p[1]) {desired.note=p[0];desired.velocity=p[1];desired.gate=1;desired.panic=0;desired.strike++;}
        else if(desired.note==p[0])desired.gate=0;
    } else if(op==CYD_PANIC) {desired.gate=0;desired.panic=1;desired.panic_serial++;}
    else return 0;
    publish();return 1;
}
static int read_state(void *ctx,CydState *out) {
    uint32_t before,after;
    unsigned slot;
    (void)ctx;
    if(applied_version!=desired.version)return 0;
    before=observation_generation;RING_PUBLISH();slot=observation_slot;
    *out=observations[slot];RING_PUBLISH();after=observation_generation;
    if(before!=after)return 0; /* bounded retry on the next main iteration */
    telemetry_consumed=after; /* audio owns/reset the measured peak accumulators */
    return 1;
}
static int16_t next_sample(void *ctx) {
    int16_t value;xeno_render((Xeno *)ctx,&value,1);return value;
}
static void app_audio(int32_t *out,uint32_t n) {
    uint32_t started=fm1_ticks(),peak=0;
    Command command=commands[command_slot];
    if(telemetry_ack!=telemetry_consumed || command.panic || last_reset!=command.reset || last_panic!=command.panic_serial) {
        telemetry_ack=telemetry_consumed;held_peak=0;
        for(unsigned i=0;i<6;i++)held_meters[i]=0;
    }
    if(!initialized || last_reset!=command.reset) {
        xeno_reset(&xeno,0x43594431u,command.material);vw_rate_clear(&rate);
        initialized=1;last_reset=command.reset;
    }
    xeno_controls(&xeno,command.excitation,command.damping,command.coupling);
    if(xeno.material!=command.material)xeno_material(&xeno,command.material);
    if(command.panic || command.panic_serial!=last_panic) {xeno_panic(&xeno);vw_rate_clear(&rate);}
    if(!command.panic && command.strike!=last_strike && command.gate)xeno_strike(&xeno,command.note,command.velocity);
    if(!command.gate)xeno_release(&xeno);
    last_strike=command.strike;last_panic=command.panic_serial;
    if(!command.panic) for(uint32_t i=0;i<n;i++) {
        int32_t value=vw_rate_step(&rate,next_sample,&xeno);
        uint32_t magnitude=(uint32_t)(value<0?-value:value);
        if(magnitude>peak)peak=magnitude;
        out[2u*i]+=value;out[2u*i+1u]+=value;
    }
    unsigned next=(observation_slot^1u)&1u;
    CydState *state=&observations[next];
    *state=(CydState){0};state->values[0]=xeno.excitation;state->values[1]=xeno.damping;
    state->values[2]=xeno.coupling;state->values[3]=(uint8_t)(((unsigned)xeno.material*127u+1u)/3u);
    state->preset=command.preset;state->note=xeno.note;state->gate=xeno.held;
    if(peak>held_peak)held_peak=peak;
    state->revision=(uint16_t)(command.version&16383u);state->output_peak=(uint8_t)(held_peak*127u/32768u);
    for(unsigned i=0;i<6;i++) {
        uint8_t level=(uint8_t)(xeno_mode_level(&xeno,i)*127u/131070u);
        if(level>held_meters[i])held_meters[i]=level;
        state->meters[i]=held_meters[i];
    }
    RING_PUBLISH();observation_slot=next;observation_generation++;applied_version=command.version;
    uint32_t elapsed=fm1_ticks()-started;
    if(elapsed>target_audio_max_ticks)target_audio_max_ticks=elapsed;
    target_audio_blocks++;
}
/* A complete short reply fits or is retained as one bounded main-loop item.
 * No waiting for a host read; no USB call from the audio ISR. */
static int try_reply(const uint8_t *data,size_t length) {
    uint32_t packets=(uint32_t)((length+2u)/3u),at=0;
    if(!usb.config||sx_open||so_w-so_r+packets>SXQ)return 0;
    sx_busy=1;
    while(at<length) {
        uint32_t k=(uint32_t)length-at;if(k>3u)k=3u;
        uint32_t cin=k==3u&&at+3u<length?4u:k==3u?7u:4u+k;
        sx_out_q[so_w%SXQ]=cin|((uint32_t)data[at]<<8)|
            (k>1u?(uint32_t)data[at+1]<<16:0u)|(k>2u?(uint32_t)data[at+2]<<24:0u);
        RING_PUBLISH();so_w++;at+=k;
    }
    sx_busy=0;return 1;
}
static void companion_service(void) {
    const uint8_t *body;uint32_t length;
    cyd_endpoint_tick(&endpoint,fm1_ms);
    if(queued_size) {
        if(!try_reply(queued_reply,queued_size)){target_reply_deferrals++;return;}
        queued_size=0;
    }
    if(ota_frame_get(&body,&length) && length>=3 && body[0]==0x7d && body[1]=='C' && body[2]=='Y') {
        if(length+2u<=CYD_ENDPOINT_MAX_FRAME) {
            uint8_t message[CYD_ENDPOINT_MAX_FRAME];
            message[0]=0xf0;for(uint32_t i=0;i<length;i++)message[i+1]=body[i];message[length+1]=0xf7;
            cyd_endpoint_receive(&endpoint,message,length+2u,fm1_ms,queued_reply,&queued_size);
        } else endpoint.rejected++;
        ota_frame_done();
    }
    if(!queued_size)queued_size=cyd_endpoint_reply(&endpoint,queued_reply);
    if(queued_size && try_reply(queued_reply,queued_size))queued_size=0;
    else if(queued_size)target_reply_deferrals++; /* deferred iterations, not lost engine events */
}
static void app_main(void) {
    uint32_t prior=0,shown=~0u;
    commands[0]=desired;commands[1]=desired;
    cyd_endpoint_init(&endpoint,2,0,apply,read_state); /* this build is emulator-only */
    publish();
    draw_text_box(0,16,240,&FONT_L,"XENO CYDAUX",C_WHITE,1);
    draw_text_box(0,118,240,&FONT_S,"USB CY1 / STANDALONE",C_WHITE,1);
    draw_text_box(0,170,240,&FONT_S,"KEY STRIKE / K1 DAMP",C_WHITE,1);
    draw_text_box(0,208,240,&FONT_S,"SEL MATERIAL / HOME MUTE",C_WHITE,1);
    for(;;) {
        companion_service();platform_poll();
        uint32_t released,buttons=fm1_input_edges(&released),keys=fm1_in.notes;
        uint32_t down=(keys&~prior)|fm1_input_note_edges(),up=prior&~keys;prior=keys;
        for(unsigned k=0;k<27;k++)if(down&(1u<<k)) {
            const uint8_t note[2]={(uint8_t)(48u+k),110};apply(0,CYD_NOTE,note);
        }
        if(desired.note>=48u && desired.note<75u && (up&(1u<<(desired.note-48u)))) {
            const uint8_t note[2]={desired.note,0};apply(0,CYD_NOTE,note);
        }
        if(buttons&(1u<<BTN_HOME)){uint8_t p[2]={0,0};apply(0,CYD_PANIC,p);}
        if(buttons&(1u<<BTN_SEL)){uint8_t p[2]={(uint8_t)((desired.preset+1u)%4u),0};apply(0,CYD_SET_PRESET,p);}
        int32_t turn=fm1_enc_take(ENC_KNOB1);
        if(turn) {
            int32_t value=(int32_t)desired.damping+turn;if(value<0)value=0;if(value>127)value=127;
            uint8_t p[2]={1,(uint8_t)value};apply(0,CYD_SET_PARAMETER,p);
        }
        if(desired.material!=shown) {
            draw_text_box(0,70,240,&FONT_S,desired.material==0?"CERAMIC":desired.material==1?"WOODGLASS":desired.material==2?"ALIEN METAL":"MEMBRANE",C_WHITE,1);
            shown=desired.material;
        }
    }
}
