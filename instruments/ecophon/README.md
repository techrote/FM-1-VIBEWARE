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

## Remaining gates

- Host interactive performance: implement live ecology controls, telemetry and audition; CLI alone is not the interactive milestone.
- Extend same-seed intervention and long-run transition tests, musical articulation and anti-aliasing; current triangle/pulse sound is preliminary.
- PLATFORM #2 owns shared target/emulator integration. Ecophon exports reset, clamped environmental controls, exact mute and block rendering for a thin instrument-specific adapter. Match target sample rate or deliberately resample; validate actual FM-1 controls, ABI, ELF/map, XIP execution and PCM against the pinned emulator. No alternative shared harness, flash image or physical claim.
- QA #7 independently reproduces actual builds and packages. Source/rights and owner review remain outstanding.
