# Ecophon — first portable acoustic ecosystem

Original C11 implementation, no upstream code copied. Draft/HOLD; no physical or virtual FM-1 qualification.

Eight bounded agents inhabit four replenishing resource patches. They forage, compete for finite stocks, transfer energy to weaker neighbors, migrate toward richer patches, reproduce with inherited/mutated pitch traits, die of starvation and fade out. An extinction seed bank consumes stored resources. Rotating iteration order reduces fixed slot preference; offspring can participate in their birth tick. Agent energy determines amplitude, species selects waveform, and resource abundance changes oscillator pitch. Three authored environmental regimes and a frozen-ecology comparator are provided. The sound engine uses integer phase accumulators, bounded envelopes, no allocation and a fixed 100 Hz simulation at the prototype's 24 kHz mono sample rate (not a verified FM-1 hardware rate).

| Preset | Ecology | Fertility / sharing / pressure |
|---|---|---|
| 0 — Mutualism | Cooperative relatively rich patches | 180 / 200 / 40 |
| 1 — Scarcity | Competition and migration | 100 / 20 / 150 |
| 2 — Seasonal bloom | Rotating resource pulse | 230 / 90 / 85 |
| 3 — Frozen | Matched initial agents, ecology disabled | 180 / 200 / 40 |

Build in this directory:
```sh
cc -std=c11 -O2 -Wall -Wextra -Werror ecophon.c host.c -o ecophon
cc -std=c11 -O2 -Wall -Wextra -Werror ecophon.c test.c -o test
./test
./ecophon mutualism.wav 0 42 30
./ecophon scarcity.wav 1 42 30
./ecophon bloom.wav 2 42 30
./ecophon frozen.wav 3 42 30
./ecophon intervention.wav 0 42 30 30 0 220
```
The final three optional arguments change environmental interventions before rendering. All actual audio comes from eco_render; the current CLI renders WAV, not real-time interactive playback.

## Evidence (local Linux, original source)

GCC and Clang -O2 UBSan both passed the 12,000-tick / 120-second deterministic block-partition, reset, mute, bounds, pressure death and ablation test. State sizeof(Eco)=204 bytes on these hosts (not target ABI). Seed 42 regime 0: 159 births, 156 deaths, 4490 gifts, 87 migrations, 2456000 resource units consumed; 2879407 of 2880000 samples differ from frozen comparator. These are algorithmic measurements, not listening impressions.

30-second actual-core WAV SHA-256:
- mutualism: 6971486e4a5736a93cc1dda9ed4dc5675edf79f828de1e14a1fad70f2fc9ac88
- scarcity: e6c974d5988449d7880838223cc11a835ffba764ba67854e46558e2f12618b74
- bloom: 155158bdf0d51a2bed10948d9f1bf226d9f6c57e9b8f272c5c6ddcfb99e8bc7b
- frozen: 73e1093fb5103213af9f3ddccf52bce37ad1fbbb9aa5b3a1375c5c2cbcf3a41f

## Live local audition (candidate)

The original core is unchanged. Build the local fixture in this directory:

```sh
gcc -std=c11 -O2 -Wall -Wextra -Werror -shared -fPIC ecophon.c fixture.c -o libecof.so
python live.py
# Windows (MinGW GCC): gcc -std=c11 -O2 -Wall -Wextra -Werror -shared ecophon.c fixture.c -o ecof.dll
# Then python live.py
```

Open the printed loopback URL. Start/reset with a seed and regime, intervene with fertility/sharing/pressure, compare frozen interactions and inspect the four resource patches and living agents. Panic immediately disconnects the local playback gain and invalidates the server session. One native model serves one local performer; restarting invalidates other tabs. The model advances on demand in fixed 100 ms chunks, not wall time when idle. Actual browser audio continuity depends on host scheduling. The UI displays local native state, never FM-1 telemetry. The environmental XY pad maps horizontal position to fertility and vertical position to survival pressure. Regime selection takes effect on reset, not by silently modifying the current regime. A bounded eight-snapshot buffer draws only completed audio blocks on the audio clock; panic clears queued snapshots and disconnects gain. No wire protocol or CYD firmware is implemented. The provisional profile supplies semantics to PLATFORM and CYDAUX.

`python test_live.py libecof.so` (Windows: `python test_live.py ecof.dll`) exercises real HTTP, persistent native PCM, causal interventions, reset, invalid/stale rejection and panic. Browser playback is a separate gate, not established by this HTTP test. The Chromium job runs test_browser.py against the native library: actual Web Audio graph RMS, XY controls, regime reset, panic, failed request and reconnect. It is not a physical audio-output or listening test.

## Remaining gates

- Host interactive performance: candidate browser/HTTP local fixture now provided; independently qualify extracted Windows execution and actual browser playback.
- Extend same-seed intervention and long-run transition tests, musical articulation and anti-aliasing; current triangle/pulse sound is preliminary.
- PLATFORM #2 owns shared target/emulator integration. Ecophon exports reset, clamped environmental controls, exact mute and block rendering for a thin instrument-specific adapter. Match target sample rate or deliberately resample; validate actual FM-1 controls, ABI, ELF/map, XIP execution and PCM against the pinned emulator. No alternative shared harness, flash image or physical claim.
- QA #7 independently reproduces actual builds and packages. Source/rights and owner review remain outstanding.

## Habitat Arc — authored native performance

Run `python performance.py libecof.so performances` (Windows: `python performance.py ecof.dll performances`) against the built local fixture. Three 24-second mono WAVs and a 10 Hz control/ecology timeline with hashes are generated; the native package includes these under `performances/` without replacing the original four demos. The actual same-seed core begins with four seconds of common mutualism, ramps toward drought over four seconds, holds four seconds, ramps to recovery over four seconds, and sustains eight seconds. Steady and frozen-interaction controls share the exact first four seconds of PCM and snapshots. Frozen interactions stop birth/death/gift/migration/consumption, not patch replenishment. This is an authored environmental composition, not a recording of device telemetry.

Local GCC/UBSan result (seed 42): living agent counts at 4/8/12/16/24 seconds were 8/0/1/2/8 for Habitat Arc; 8/7/7/8/6 for steady control; 8/8/8/8/8 for frozen interactions. Exact repeat of all three WAVs and timelines, matched pre-intervention state, distinct PCM, bounded peak and native panic silence passed. Hosted Windows/Linux exact SHA-256 checks added; independent QA pending. No FM-1 target or transport qualification is implied.

## Companion replay fixture (offline, not a wire protocol)

Run `python companion_fixture.py libecof.so audition/performances/companion-replay.json` (use `ecof.dll` on Windows). The 230,137-byte deterministic JSON contains three Habitat Arc arms, each 240 snapshots at 10 Hz, with four finite resources, eight fixed agent slots, control echoes, cumulative counters and SHA-256 of the corresponding 100 ms little-endian PCM block. Frames mark block ends. Slot indices are stable storage locations, not persistent individual identities. This is local native core state, not device telemetry; consumers may replay it to test common widgets, not transmit it as a device protocol. The runner checks population accounting, range/headroom, frozen agents, exact reset/repeat, invalid control rejection without advancing, and panic silence. GCC/Clang UBSan local rebuilds matched replay SHA-256 `0e5ec4eded3a2145005bf50a8a9abb8bbbf979d693f09d0dfc50f48baefa5adc`; Windows/Linux CI checks the same digest. Original core and fixture ABI unchanged.

FM-1 standalone: PLATFORM #13 at `94a2ffe7673ca2e21cd2bddfb879d42eb78e456b` [run 46061074556](https://github.com/techrote/FM-1-VIBEWARE/actions/runs/46061074556) passed actual target compilation and strict virtual PCM repeat, pressure and live SCL preset contrast (39,679/39,690 post-intervention stereo frames differ after matched prefix), HOME 500 ms zero tail. [Evidence](https://github.com/techrote/FM-1-VIBEWARE/actions/runs/46061074556/artifacts/15229850685). Author virtual qualification only; independent QA, Windows virtual package, basic MIDI, enhanced transport, device telemetry and physical qualification remain outstanding.

## Population Tide — closed-loop performance experiment

Run `python feedback.py libecof.so feedback` (Windows: `ecof.dll`). After a common four-second prefix, a bounded 10 Hz controller uses the last completed native population count to steer fertility, sharing and pressure toward authored population targets 5, 3 and 6. One-agent dead band, maximum 12 control units per block; no core/ABI changes. Two 32-second actual-core WAVs and aligned traces for seed 42, plus five-seed metrics. Three comparison arms: feedback, steady baseline, and seed-42 feedback controls replayed open-loop on every seed (yoked reference). GCC and Clang UBSan runs were byte-identical across all five output files. Aggregate absolute population error over 1400 post-prefix snapshots: 2755 feedback, 3156 steady, 3126 yoked; feedback improved 4/5 seeds versus steady, not all seeds. Empty population snapshots: 4 feedback, 0 steady, 9 yoked. This is a musical feedback experiment, not a proven stabilizing regulator. Browser manual controls unchanged; not live device telemetry, MIDI or a shared wire protocol. Hosted CI regenerates exact digests. Physical HOLD.

Independent frozen standalone virtual QA: [run 46066974168](https://github.com/techrote/FM-1-VIBEWARE/actions/runs/46066974168) PASS; [evidence](https://github.com/techrote/FM-1-VIBEWARE/actions/runs/46066974168/artifacts/15231867345). Previous replay-inclusive native/browser [run 46064523437](https://github.com/techrote/FM-1-VIBEWARE/actions/runs/46064523437) PASS; [Windows package](https://github.com/techrote/FM-1-VIBEWARE/actions/runs/46064523437/artifacts/15230686178). These do not qualify the new feedback experiment on target or companion hardware.

## Live Habitat Arc cues

The native audition now includes Mutualism, Drought and Recovery cue buttons using the same endpoint controls as the authored Habitat Arc score. A cue interpolates from the current controls over 40 native 100 ms requests without resetting the habitat or seed. Manual slider/XY, freeze, feedback activation, reset and panic cancel the active cue; cues are disabled while stopped/frozen. Escape provides emergency local mute even when editing the seed. No device protocol or target/core ABI change. The browser regression verifies native control echoes, generation and tick continuity, endpoint arrival and manual/feedback takeover. These controls represent local native state, not FM-1 device telemetry.

### Whole Habitat Arc live performance

The optional **Play whole Habitat Arc (24 s)** button runs a 240-block local score without resetting the seed, regime, agents or clock. The first 40 blocks blend from the current environment into Mutualism; the remaining blocks match the authored offline Habitat Arc controls exactly (40 drought transition, 40 drought hold, 40 recovery transition, 80 recovery hold). The terminal environment remains at Recovery; the score does not loop. Manual sliders/XY, individual cues, freeze, feedback, reset and panic take over immediately for subsequent requests. Progress is native request/model time, not a physical or wall-clock guarantee. A full browser integration regression records every native control echo and checks exact segment boundaries, tick and generation continuity, cancellation, and panic silence. The provisional profile describes these local semantics for companion widget design, not a transport or device telemetry format.

### Live Arc companion replay and manual takeover

Run `python live_arc_fixture.py libecof.so audition/live-arc` (Windows: `ecof.dll`). Nine 28-second WAVs and a single bounded replay JSON cover Mutualism, Scarcity and Seasonal Bloom, each with a three-second common prelude, a 24-second live Arc or matched steady environment or explicit manual takeover after 100 score blocks, and a one-second native panic tail. The takeover holds fertility/sharing/pressure at 150/240/70 for the remainder. The fixture provides 2,520 block-end snapshots, actual PCM hashes, eight agent slots, four resources, control and clock echoes, counters and mute flags. It models the local semantic intervention, not actual companion transport or device telemetry.

GCC and Clang UBSan native builds reproduced all nine WAVs and replay byte-for-byte, including exact prelude and takeover prefixes, population accounting, bounded headroom and silent panic. Final pre-mute population (Arc/steady/takeover): Mutualism 8/7/4, Scarcity 8/1/4, Seasonal Bloom 8/8/1. Replay SHA-256: `3ea099d0a352e56398f9bd0583103f0971dfa6cbca145be4637a72204411c8f3`. CI regenerates the exact fixture on both operating systems and packages source plus outputs. This is an offline native witness, not a new browser or device qualification.

The preceding whole-score browser/native [author CI](https://github.com/techrote/FM-1-VIBEWARE/actions/runs/46093613745) and [independent Windows/Linux successor QA](https://github.com/techrote/FM-1-VIBEWARE/actions/runs/46095359490) passed at b45da66cbe49328d7c9da53269ad050171ffcf60; [accepted Windows evaluator](https://github.com/techrote/FM-1-VIBEWARE/actions/runs/46093613745/artifacts/15242455667). Retain that accepted package until successor qualification. Standalone virtual evidence is separate; basic MIDI/enhanced/device telemetry and physical gates remain unverified/HOLD.

### Environment memories

Two local session slots (A/B) capture current fertility/sharing/pressure slider intent, not habitat state. Recall ramps from the current controls to a detached target over 40 native blocks, retaining the current seed, agent state and clock. Capture during an active cue does not interrupt it or mutate its target. Recall overrides feedback or previous cue; manual sliders/XY, freeze, other cues, reset and panic take over. Slots survive habitat resets but not page reloads. No wire command or device telemetry is implied. The actual Chromium regression exercises both slots, exact native control/tick/generation continuity during recall, capture during recall and freeze/panic cancellation.

Previous exact feda1327 author [46098655740](https://github.com/techrote/FM-1-VIBEWARE/actions/runs/46098655740) 3/3 and [independent 46100339386](https://github.com/techrote/FM-1-VIBEWARE/actions/runs/46100339386) both Ecophon operating systems passed. [Accepted Windows evaluator](https://github.com/techrote/FM-1-VIBEWARE/actions/runs/46098655740/artifacts/15243929322) SHA-256 460a50113c35d263755a9d6a04941cc4119c397a6d48739086a732727aeb95b6. Retain this pin pending successor browser/native and independent QA.

### Environment memory comparative performance

Run `python memory_fixture.py libecof.so memory-evidence` (Windows: `ecof.dll`). Three regimes × four policies yield twelve 19-second native WAVs (3 s matched prelude, 15 s score, 1 s exact mute). Each score recalls drought A, captures the current requested controls back into A after 20 blocks, recalls recovery B, then recalls the overwritten A. Smooth recall snapshots the original target, so capture cannot change the running transition. The step policy instead applies targets immediately and therefore captures a different A; this compares complete recall policies, not an isolated interpolation effect in the final cue. The steady policy ignores recall; manual takeover shares the first 70 score blocks with smooth then cancels B and holds explicit controls. No core reset between cues.

The replay JSON contains 2,280 block-end actual native snapshots, slot intents, events, controls, counters, resources, agent slots and PCM block hashes. Local exact core/header/fixture blobs verified; GCC UBSan and Clang UBSan trap builds produced byte-identical WAVs and JSON, repeat, bounds, tick continuity, detached capture, manual takeover and mute checks PASS. Final pre-mute populations smooth/step/steady/takeover: Mutualism 1/0/5/6, Scarcity 1/0/1/5, Seasonal Bloom 3/0/8/6. These are algorithmic results for seed 42, not subjective listening or a general claim of superiority. Replay SHA-256 `8102e696b1f32805492faf1b31bfc63d20093f5489dd807aab109958933a4df1`. CI regenerates a separate memory-replay artifact with exact source revision; the native evaluator archive inventory is unchanged.

Predecessor environment memory browser/native [author 46103844336](https://github.com/techrote/FM-1-VIBEWARE/actions/runs/46103844336) 3/3 and [independent 46105003795](https://github.com/techrote/FM-1-VIBEWARE/actions/runs/46105003795) Ecophon Windows/Linux passed at c886271d838963aa5a4ff27ab2a934522cf178b7. [Accepted Windows evaluator](https://github.com/techrote/FM-1-VIBEWARE/actions/runs/46103844336/artifacts/15245883800), SHA-256 `a5a3e78a09c116201e0c8b9f5a381e8f169de768e8cc6abd89ac507061b68fba`. New memory fixture is local native evidence; no device telemetry, transport, wire protocol, target build or physical claim. Independent successor QA pending.
