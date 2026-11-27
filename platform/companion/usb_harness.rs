// SPDX-License-Identifier: MIT
// Drives the actual CPU/SoC/USB model; no native Xeno DSP runs in this process.
use fm1_core::Bus;
use fm1_soc::machine::{Machine, Options};
use std::fs;
use std::path::Path;
use std::time::Instant;
const STACK_CANARY:u32=0xa55ac33c;
const STACKS:[(u32,u32);2]=[(0x01c74100,0x01c7a000),(0x01c7a100,0x01c7c000)]; // pinned app.ld

fn frame(op:u8,session:u32,sequence:u16,payload:&[u8])->Vec<u8>{
    let mut v=vec![0xf0,0x7d,b'C',b'Y',1,0,op];
    for i in 0..4{v.push(((session>>(i*7))&127) as u8);}
    v.push((sequence&127) as u8);v.push((sequence>>7) as u8);v.push(payload.len() as u8);
    v.extend_from_slice(payload);v.push(0xf7);v
}
fn run_to(m:&mut Machine,ms:u64){
    while m.soc.periph.ms()<ms {m.run(8192).expect("actual target CPU/SoC execution");}
}
fn request(m:&mut Machine,op:u8,session:u32,sequence:u16,payload:&[u8],expected:u8)->Vec<u8>{
    assert!(m.soc.usb.midi_take().is_empty(),"unsolicited stale USB reply");
    let sent_ms=m.soc.periph.ms();
    m.soc.usb.midi_send(&frame(op,session,sequence,payload));
    let deadline=m.soc.periph.ms()+350;
    while m.soc.periph.ms()<deadline{
        m.run(8192).expect("target while processing USB request");
        for reply in m.soc.usb.midi_take(){
            assert!(reply.len()>=15 && reply[0..4]==[0xf0,0x7d,b'C',b'Y'] && reply[reply.len()-1]==0xf7);
            assert_eq!(reply.len(),15+reply[13] as usize);
            assert_eq!(reply[6],expected,"USB operation response: {reply:02x?}");
            let id=(0..4).fold(0u32,|v,i|v|((reply[7+i] as u32)<<(7*i)));
            assert_eq!(id,session);assert_eq!(reply[11] as u16|((reply[12] as u16)<<7),sequence);
            println!("usb_reply ms={} rtt_ms={} op={} seq={} bytes={:02x?}",m.soc.periph.ms(),m.soc.periph.ms()-sent_ms,expected,sequence,reply);
            return reply;
        }
    }
    panic!("no actual USB reply for op={op} sequence={sequence}; product={:?} pending={}",m.soc.usb.product(),m.soc.usb.midi_pending());
}
fn wav(path:&Path,pcm:&[i16]){
    let bytes=(pcm.len()*2) as u32;let mut v=Vec::with_capacity(bytes as usize+44);
    v.extend(b"RIFF");v.extend((bytes+36).to_le_bytes());v.extend(b"WAVEfmt ");v.extend(16u32.to_le_bytes());
    v.extend(1u16.to_le_bytes());v.extend(2u16.to_le_bytes());v.extend(44100u32.to_le_bytes());
    v.extend(176400u32.to_le_bytes());v.extend(4u16.to_le_bytes());v.extend(16u16.to_le_bytes());
    v.extend(b"data");v.extend(bytes.to_le_bytes());for s in pcm{v.extend(s.to_le_bytes());}
    fs::write(path,v).expect("write actual target PCM");
}
fn strike(m:&mut Machine,seq:&mut u16,coupling:u8)->Vec<i16>{
    *seq+=1;request(m,6,42,*seq,&[0],4); // reset same real engine/seed
    *seq+=1;request(m,5,42,*seq,&[2,coupling],4);
    let begin=m.soc.periph.audio.len();
    *seq+=1;let state=request(m,7,42,*seq,&[48,110],4);assert_eq!(state[26]&1,1);
    assert!(state[34]>0 && state[28..34].iter().any(|v|*v>0),"actual peak/modal telemetry missed the strike");
    let until=m.soc.periph.ms()+180;run_to(m,until);
    let pcm=m.soc.periph.audio[begin..].to_vec();
    *seq+=1;request(m,7,42,*seq,&[48,0],4);
    let nonzero=pcm.iter().filter(|s|**s!=0).count();
    assert!(nonzero>128,"actual target strike is silent/truncated, nonzero={nonzero}");
    pcm
}
fn audible_prefix(pcm:&[i16])->Vec<i16>{
    let first=pcm.iter().position(|s|*s!=0).expect("audible onset")&!1usize;
    assert!(pcm.len()>=first+4096);pcm[first..first+4096].to_vec()
}
fn stack_used(m:&mut Machine,lo:u32,hi:u32)->u32{
    for addr in (lo..hi).step_by(4){if m.soc.read32(addr)!=STACK_CANARY{return hi-addr;}}
    0
}
fn main(){
    let args:Vec<String>=std::env::args().collect();assert!(args.len()==5,"xip output-dir symbols strict|instruction");
    let strict=args[4]=="strict";let start=Instant::now();
    let opts=Options{strict,jit:!strict,lcd_timed:true,..Options::default()};
    let image=fs::read(&args[1]).expect("pinned raw-XIP image");
    let mut machine=Machine::from_image(image,0x02000120,&opts);
    for (lo,hi) in STACKS {for addr in (lo..hi).step_by(4){machine.soc.write32(addr,STACK_CANARY);}}
    machine.soc.usb_plug(); // schedules host USB frame events as well as the cable
    machine.soc.usb.audio_record(44100);
    run_to(&mut machine,1200);
    assert!(machine.soc.usb.product().is_some(),"actual USB enumeration failed");
    let identity=request(&mut machine,1,42,0,&[2],2);
    assert_eq!(&identity[14..20],&[2,1,0,31,0,2]);
    let mut sequence=1u16;
    let initial=request(&mut machine,3,42,sequence,&[],4);
    assert_eq!(&initial[16..19],&[76,38,48]);
    let dry=strike(&mut machine,&mut sequence,0);
    let repeat=strike(&mut machine,&mut sequence,0);
    let coupled=strike(&mut machine,&mut sequence,127);
    assert_eq!(audible_prefix(&dry),audible_prefix(&repeat),"same-reset actual CPU PCM must repeat");
    assert_ne!(audible_prefix(&dry),audible_prefix(&coupled),"coupling mutation must change actual CPU PCM");
    sequence+=1;let stale=request(&mut machine,5,41,sequence,&[0,1],9);assert_eq!(stale[14],3);
    sequence+=1;let range=request(&mut machine,5,42,sequence,&[7,1],9);assert_eq!(range[14],5);
    sequence+=1;request(&mut machine,7,42,sequence,&[60,120],4);
    sequence+=1;request(&mut machine,8,42,sequence,&[],4);
    let until=machine.soc.periph.ms()+150;run_to(&mut machine,until);
    let audio=&machine.soc.periph.audio;
    assert!(audio.len()>4410 && audio[audio.len()-4410..].iter().all(|v|*v==0),"panic audio tail");
    sequence+=1;request(&mut machine,7,42,sequence,&[64,110],4);
    let until=machine.soc.periph.ms()+1650;run_to(&mut machine,until);
    sequence+=1;let expired=request(&mut machine,3,42,sequence,&[],9);assert_eq!(expired[14],3);
    request(&mut machine,1,43,0,&[2],2);
    let after=request(&mut machine,3,43,1,&[],4);assert_eq!(after[26]&1,0,"lease releases gate");
    let out=Path::new(&args[2]);fs::create_dir_all(out).unwrap();
    fm1_soc::write_bmp(out.join("actual-fm1-lcd.bmp").to_str().unwrap(),&machine.soc.lcd.fb,machine.soc.lcd.inverted).unwrap();
    wav(&out.join("xeno-uncoupled.wav"),&dry);wav(&out.join("xeno-repeat.wav"),&repeat);
    wav(&out.join("xeno-coupled.wav"),&coupled);wav(&out.join("xeno-full-session.wav"),&machine.soc.periph.audio);
    let mut metrics=String::new();
    for line in fs::read_to_string(&args[3]).unwrap().lines(){
        let mut fields=line.split_whitespace();let name=fields.next().unwrap();let addr=u32::from_str_radix(fields.next().unwrap(),16).unwrap();
        let value=machine.soc.read32(addr);metrics.push_str(&format!("{name}={value}\n"));
        if name=="target_audio_blocks"{assert!(value>100);}
        if name=="target_audio_max_ticks"{assert!((value as u64)<256u64*24_000_000/44_100,"modeled audio callback exceeded its 256-frame block deadline");}
    }
    let main_stack=stack_used(&mut machine,STACKS[0].0,STACKS[0].1);
    let supervisor_stack=stack_used(&mut machine,STACKS[1].0,STACKS[1].1);
    assert!(main_stack+1024<STACKS[0].1-STACKS[0].0 && supervisor_stack+1024<STACKS[1].1-STACKS[1].0,"emulated stack reserve");
    metrics.push_str(&format!("emulated_main_stack_used={main_stack}\nemulated_supervisor_stack_used={supervisor_stack}\n"));
    fs::write(out.join("target-metrics.txt"),&metrics).unwrap();
    let report=format!("{{\"status\":\"PASS\",\"mode\":\"{}\",\"source\":\"actual pi32v2 firmware in fm1-emu USB model\",\"elapsed_host_seconds\":{},\"emulated_ms\":{},\"i2s_frames\":{},\"usb_audio_frames\":{},\"usb_audio_underruns\":{},\"emulated_main_stack_used\":{},\"emulated_supervisor_stack_used\":{},\"checks\":[\"USB discovery\",\"actual readback\",\"parameter and preset\",\"PCM repeat\",\"coupling contrast\",\"actual interval peaks\",\"stale session\",\"invalid range\",\"panic tail\",\"lease expiry\",\"new session recovery\",\"modeled callback deadline\",\"emulated stack reserve\"]}}\n",
        args[4],start.elapsed().as_secs_f64(),machine.soc.periph.ms(),machine.soc.periph.audio.len()/2,machine.soc.usb.audio.len()/2,machine.soc.usb.audio_underruns,main_stack,supervisor_stack);
    fs::write(out.join("qualification.json"),&report).unwrap();println!("{metrics}{report}");
}
