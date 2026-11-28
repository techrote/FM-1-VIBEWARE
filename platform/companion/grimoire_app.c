/* SPDX-License-Identifier: MIT
 * Grimoire CY1 target. Private raw-XIP emulator experiment only. The common
 * endpoint handles framing and lease; main publishes commands, ISR owns DSP. */
#define APP_NAME "ORBIT GATE CYD"
#define CYD_ENDPOINT_SERVICE 1
#include "platform.c"
#include "grimoire_control.h"
#include "rate.h"
#if BOARD_SMK37 || FS != 44100u || ORBIT_RATE != 24000u
#error Wrong target audio contract
#endif
static CydOrbitCommand desired={0,0,0,48,70,0,44,0,1};
static CydOrbitCommand commands[2]={{0,0,0,48,70,0,44,0,1},{0,0,0,48,70,0,44,0,1}};
static volatile uint32_t command_slot,applied_version;
static CydState observations[2];
static volatile uint32_t observation_slot,observation_generation,telemetry_consumed;
static uint32_t telemetry_ack;
static CydOrbitRuntime runtime;
static VwRate rate;
static CydEndpoint endpoint;
static volatile uint32_t target_audio_blocks,target_audio_max_ticks,target_reply_deferrals;
static uint8_t queued_reply[CYD_ENDPOINT_MAX_FRAME];
static size_t queued_size;
static void publish(void) {
    unsigned next=(command_slot^1u)&1u;commands[next]=desired;
    RING_PUBLISH();command_slot=next;
}
static int apply(void *ctx,uint8_t op,const uint8_t *payload) {
    (void)ctx;if(!cyd_orbit_apply(&desired,op,payload))return 0;
    publish();return 1;
}
static int read_state(void *ctx,CydState *out) {
    (void)ctx;if(applied_version!=desired.version)return 0;
    uint32_t before=observation_generation;RING_PUBLISH();unsigned slot=observation_slot;
    *out=observations[slot];RING_PUBLISH();uint32_t after=observation_generation;
    if(before!=after)return 0;
    telemetry_consumed=after;return 1;
}
static void app_audio(int32_t *out,uint32_t n) {
    uint32_t started=fm1_ticks();CydOrbitCommand command=commands[command_slot];
    if(telemetry_ack!=telemetry_consumed){telemetry_ack=telemetry_consumed;cyd_orbit_clear_peaks(&runtime);}
    if(cyd_orbit_sync(&runtime,&command))vw_rate_clear(&rate);
    if(!command.panic)for(uint32_t i=0;i<n;i++) {
        int16_t value=vw_rate_step(&rate,cyd_orbit_next,&runtime);
        cyd_orbit_observe(&runtime,value);out[2u*i]+=value;out[2u*i+1u]+=value;
    }
    unsigned next=(observation_slot^1u)&1u;
    cyd_orbit_snapshot(&runtime,&command,&observations[next]);
    RING_PUBLISH();observation_slot=next;observation_generation++;applied_version=command.version;
    uint32_t elapsed=fm1_ticks()-started;
    if(elapsed>target_audio_max_ticks)target_audio_max_ticks=elapsed;
    target_audio_blocks++;
}
/* Same pinned Dinghy USB queue contract as the Xenoresonator target. Bounded
 * whole-message enqueue, one deferred reply, no USB work in the audio ISR. */
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
    const uint8_t *body;uint32_t length,session=endpoint.session;
    if(!usb.config){cyd_endpoint_disconnect(&endpoint);queued_size=0;return;}
    cyd_endpoint_tick(&endpoint,fm1_ms);
    if(session&&!endpoint.session)queued_size=0;
    if(queued_size) {
        if(!try_reply(queued_reply,queued_size)){target_reply_deferrals++;return;}
        queued_size=0;
    }
    if(ota_frame_get(&body,&length)&&length>=3&&body[0]==0x7d&&body[1]=='C'&&body[2]=='Y') {
        if(length<=CYD_ENDPOINT_MAX_FRAME-2u) {
            uint8_t message[CYD_ENDPOINT_MAX_FRAME];message[0]=0xf0;
            for(uint32_t i=0;i<length;i++)message[i+1]=body[i];
            message[length+1]=0xf7;
            cyd_endpoint_receive(&endpoint,message,length+2u,fm1_ms,queued_reply,&queued_size);
        } else endpoint.rejected++;
        ota_frame_done();
    }
    if(!queued_size)queued_size=cyd_endpoint_reply(&endpoint,queued_reply);
    if(queued_size&&try_reply(queued_reply,queued_size))queued_size=0;
    else if(queued_size)target_reply_deferrals++;
}
static void panel(uint8_t op,uint8_t a,uint8_t b) {const uint8_t p[2]={a,b};(void)apply(0,op,p);}
static void app_main(void) {
    uint32_t prior=0,shown=~0u;
    (void)cyd_endpoint_init_profile(&endpoint,CYD_GRIMOIRE,2,0,apply,read_state);
    desired.version++;publish();
    draw_text_box(0,10,240,&FONT_L,"ORBIT GATE",C_WHITE,1);
    draw_text_box(0,144,240,&FONT_S,"KEY PITCH / K1 MATERIAL",C_WHITE,1);
    draw_text_box(0,180,240,&FONT_S,"SEL PRESET / PLAY GATE",C_WHITE,1);
    draw_text_box(0,210,240,&FONT_S,"HOME PANIC / USB CY1",C_WHITE,1);
    for(;;) {
        companion_service();platform_poll();
        uint32_t released,buttons=fm1_input_edges(&released),keys=fm1_in.notes;
        uint32_t down=(keys&~prior)|fm1_input_note_edges();prior=keys;
        for(unsigned k=0;k<27;k++)if(down&(1u<<k))panel(CYD_SET_PARAMETER,0,(uint8_t)(k*127u/26u));
        int32_t d=fm1_enc_take(ENC_KNOB1);if(d>127)d=127;if(d< -127)d= -127;
        if(d){int32_t y=(int32_t)desired.y+d;panel(CYD_SET_PARAMETER,1,(uint8_t)(y<0?0:y>127?127:y));}
        if(buttons&(1u<<BTN_SEL))panel(CYD_SET_PRESET,(uint8_t)((desired.preset+1u)%3u),0);
        if(buttons&(1u<<BTN_PLAY))panel(CYD_NOTE,desired.gate?desired.note:(uint8_t)(36u+desired.x*23u/127u),desired.gate?0:127);
        if(buttons&(1u<<BTN_HOME))panel(CYD_PANIC,0,0);
        uint32_t display=desired.preset|((uint32_t)desired.gate<<2);
        if(display!=shown) {
            draw_text_box(0,58,240,&FONT_S,desired.preset==0?"AMBER":desired.preset==1?"IRON":"ABYSS",C_WHITE,1);
            draw_text_box(0,100,240,&FONT_S,desired.gate?"PLAYING":"STOPPED",C_WHITE,1);shown=display;
        }
    }
}
