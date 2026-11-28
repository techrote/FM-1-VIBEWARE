// SPDX-License-Identifier: MIT
// Qualification-only stdio adapter to the pinned emulator USB model.
// No host DSP, no physical USB, no installable image distribution.
use fm1_soc::machine::{Machine, Options};
use std::io::{self, BufRead, Write};
use std::fs;

fn advance(m: &mut Machine, ms: u64) {
    let deadline = m.soc.periph.ms() + ms;
    let mut steps = 0u64;
    while m.soc.periph.ms() < deadline {
        m.run(8192).expect("actual CPU/SoC execution");
        steps += 1;
        assert!(steps < 2_000_000, "emulator clock stopped");
    }
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    assert_eq!(args.len(), 2, "internal raw XIP path required");
    let opts = Options { strict: false, jit: true, lcd_timed: true, ..Options::default() };
    let mut m = Machine::from_image(fs::read(&args[1]).unwrap(), 0x02000120, &opts);
    m.soc.usb_plug();
    m.soc.usb.audio_record(44100);
    advance(&mut m, 1200);
    assert!(m.soc.usb.product().is_some(), "actual USB enumeration failed");
    println!("ready");
    io::stdout().flush().unwrap();
    for line in io::stdin().lock().lines() {
        let line = line.unwrap();
        assert!(line.len() <= 800);
        let mut fields = line.split_whitespace();
        match fields.next() {
            Some("send") => {
                let data: Vec<u8> = fields.map(|v| u8::from_str_radix(v, 16).unwrap()).collect();
                assert!((2..=256).contains(&data.len()));
                assert!(m.soc.usb.midi_take().is_empty(), "unexpected previous reply");
                m.soc.usb.midi_send(&data);
                let deadline = m.soc.periph.ms() + 350;
                let mut replies = Vec::new();
                while m.soc.periph.ms() < deadline {
                    m.run(8192).expect("CPU while processing USB message");
                    replies = m.soc.usb.midi_take();
                    if !replies.is_empty() { break; }
                }
                assert_eq!(replies.len(), 1, "expected one actual USB response");
                print!("midi");
                for v in &replies[0] { print!(" {:02x}", v); }
                println!();
            }
            Some("advance") => {
                let ms: u64 = fields.next().unwrap().parse().unwrap();
                assert!((1..=2000).contains(&ms) && fields.next().is_none());
                let begin = m.soc.periph.audio.len();
                advance(&mut m, ms);
                let pcm = &m.soc.periph.audio[begin..];
                let nonzero = pcm.iter().filter(|v| **v != 0).count();
                let hash = pcm.iter().fold(14695981039346656037u64, |h, s|
                    (h ^ (*s as u16 as u64)).wrapping_mul(1099511628211));
                println!("pcm {} {} {:016x}", pcm.len(), nonzero, hash);
                assert!(m.soc.periph.audio.len() < 4_000_000, "fixture capture bound");
            }
            Some("quit") => break,
            _ => panic!("unknown fixture command"),
        }
        io::stdout().flush().unwrap();
    }
}
