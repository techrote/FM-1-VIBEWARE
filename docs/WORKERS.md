# Scheduled worker roster

The primary objective is a collection of distinct, complete, enjoyable musical instruments. Each creative worker owns design, implementation, audition, target integration, presets and documentation for its lane, not just ideation. Use the protocol in ../AGENTS.md for every invocation.

## Configurations

| Configuration | Roles | Rationale |
|---|---|---|
| Minimal (3) | PLATFORM, CREATIVE (SYNTH+GEN+CYBER+HYBRID), QA | Independent verification and a usable engineering path remain intact; creative breadth is serial. |
| Optimal (6) | PLATFORM, SYNTH, GEN, CYBER, HYBRID, QA | Four parallel creative lanes with dedicated platform support and independent integration. |
| Maximum practical (8) | Optimal + DSP + SOUND | Adds specialist acceleration and musical refinement once there are real workloads and sufficiently mature candidates. |

Suggested launch cadence (local clock, staggered; illustrative, not activated): PLATFORM every 3 hours at :05; SYNTH every 2 hours at :13; GEN every 2 hours at :23; CYBER every 2 hours at :33; HYBRID every 2 hours at :43; QA every 2 hours at :53. Adjust offsets and intervals to actual run length, runner availability and WIP; staggered starts are not locks or guarantees of concurrency. Optional DSP and SOUND every 3 hours at distinct offsets initially. If qualification queues grow, slow creative starts and prioritize QA. No need to fill slots simply because available.

## PLATFORM — Firmware and runtime engineering (#2)
Build a small practical common toolchain, deterministic DSP/event contract and target adapters. Start from exact reviewed FM-1-MHAC #8 and ZaaggenZ-FM1 #1 evidence, not assumptions. Compare Fune, Dinghy and raw-XIP routes. Produce a reproducible actual reference target and host audition, bounded integer primitives, test fixtures, measured resource budgets, emulator support and recovery/rights ledger. Use downstream consumers to drive the API; avoid building a generic SDK before it is useful. Unblock actual creative work each run.

## SYNTH — Experimental synthesis (#3)
Invent and build distinctive engines: coupled resonators, nonlinear excitation, phase distortion, compact spectral and granular approximations, percussion, timbral morphing and effects. Start Xenoresonator. Prioritize expressive controls, musical contrast and numerical safety; compare competing algorithms on actual rendered audio and resource cost. Deliver real host and FM-1 implementations with presets, not generic oscillator demos.

## GEN — Generative composition (#4)
Design playable alternative sequencers, interacting clocks, procedural patterns, cellular automata, evolutionary rules and time structures. Start Chronomorph. Include internal sound so instruments are useful standalone. Establish musical event semantics, authored compositions, reproducibility, bounded queue behaviour and tempo/transport stress tests. Make generative behaviour legible and steerable rather than arbitrary randomness.

## CYBER — Cybernetic and experimental systems (#5)
Build unusual instruments informed by artificial life, feedback, semiotics, dynamical systems and adaptation. Start Ecophon. Make system state and interventions causally meaningful and audible; compare simpler baselines. Respect hard real-time limits, bounded memory and stable output; avoid purely theoretical experiments. Deliver playable controls and distinct musical regimes.

## HYBRID — Audiovisual and performance systems (#6)
Build FM-1 instruments with optional CYD performance interfaces, XY fields, procedural visuals and distributed interaction. Start Grimoire, one complete rite first. FM-1 remains the sound engine and operates independently of CYD. Derive transport/profile capabilities from tested evidence; no assumed radio support. Prioritize expressive performance, bounded transport, reconnect, panic and real virtual/physical distinctions.

## QA — Independent qualification and mergedown (#7)
Rebuild exact candidates, independently reproduce host/target/emulator results, inspect failure logs, fix concrete defects, qualify extracted packages and maintain a playable catalogue. Coordinate shared changes and prepare owner-reviewable merges. Do not self-certify authored repairs; obtain a separate reproduction or label as provisional. Preserve Draft/HOLD, release and physical gates. No busywork audit or periodic report-only runs if implementation fixes are available.

## DSP — Optional resource and acceleration engineering
Profile real downstream bottlenecks and identify measured limiting resources. Explore fixed point, table compression, interpolation, SIMD/ISA only when supported, memory layouts, voice scheduling and algorithm alternatives. Compare exact or tolerance-qualified audio, worst-case timing and footprint against baselines. Agree ownership before touching another worker's instrument; avoid speculative optimization. Deliver tested improvements via separate PRs and coordinate adoption with PLATFORM and QA.

## SOUND — Optional sound design and performance engineering
Take playable candidates, explore the actual engine, design useful macro mappings, factory patches, performance gestures, demo songs and comparative audio. Correct real usability and sound-design deficiencies in coordinated scoped PRs. Build useful audition tooling and catalogue contributions with QA. Do not claim subjective listening without actual listening; distinguish measured signals and authored intent. No cosmetic-only proliferation.

## When to expand or contract
Start with six if resources permit. Eight only when shared interfaces are working, QA has capacity, and real performance or musical refinement queues exist. Collapse into three if creative throughput is low or infrastructure remains blocked for a sustained period. Keep separate independent QA regardless of roster size. Revisit after the first end-to-end instrument deliveries.
