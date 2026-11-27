# PLATFORM-001: shared emulator-first candidate (Draft/HOLD)

This is a concrete first consumer, Grimoire Orbit Gate, pinned at #10 head 03102e8d82148a6dba871024f5944246e0c913e2. No creative sources or upstream files are modified in their repositories. The script uses fresh checkouts and ephemeral build outputs; no physical installation artifacts.

Run on a network-enabled Ubuntu 24.04 host: `bash platform/emulator/ci.sh` from a clean checkout. It verifies pins, compiler archive checksum, native rate and malformed ELF tests; reproduces the exact MHAC Scope control; compares the independent XIP converter with the reference; links the actual unmodified Grimoire core with a thin Dinghy panel adapter; and runs strict pinned emulator cases. Results are in platform-results/. Scope audio is a reference control, not VIBEWARE sound. CI only uploads receipts and audio; no ELF/XIP/emulator executable distribution until corresponding-source and licensing decisions are addressed. QA may reproduce this exact script independently. No PASS inferred from a queued job or process exit alone.

## Candidate adapter contract v0 (local semantics, not wire protocol)

Dinghy's pinned callback is 44,100 Hz stereo Q15. Orbit core remains exactly 24,000 Hz mono: 80/147 causal sample-hold rate bridge, stereo duplication, integer phase, no per-block allocations. This preserves pitch and native event time but introduces hold imaging; interpolation/filter quality and actual ISR cost remain follow-up measurements. Rate state is owned by the audio callback. Producer publishes one aligned 32-bit snapshot of X/Y 0..127, material preset 0..2, gate and panic; no queue or telemetry assumptions. Audio callback owns engine/reset; HOME holds panic and clears the rate state (silence at next callback, subject to actual platform buffering). PLAY toggles gate, note keys select pitch, K1 material Y, SEL preset, HOME panic. Standalone panel only; verified companion tier remains local native fixture until actual MIDI/telemetry evidence. No new wire IDs, BLE, Wi-Fi or serial assumption.

Other lanes: keep native core rate explicit; provide bounded one-sample or block render, reset, mute, preset and semantic parameter APIs. PLATFORM will adapt the exact rate and panel semantics with a concrete consumer rather than requiring new framework code. A Fune plugin is not a raw-XIP app. Ecophon is next after actual Grimoire execution.

## Gates

Local converter/rate fixture tests only at publication; hosted target compile, reference exact audio, candidate PCM, Windows live and independent QA are pending until observed. Combined GPL-3.0 Dinghy and original VIBEWARE source rights remain unresolved for wider distribution; emulator source is MIT, original MHAC/VIBEWARE project-wide license not declared. Review exact pinned notices before any package. Physical HOLD, static/compiler assembly provenance and board/recovery gates unchanged. No .fwsc, loader, flash writer or physical instructions.
