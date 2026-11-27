# Scheduled worker roster

The primary objective is a collection of distinct, complete, enjoyable musical instruments. Each creative worker owns design, implementation, audition, target integration, presets and documentation for its lane, not just ideation. Use the protocol in ../AGENTS.md for every invocation.

## Configurations

| Configuration | Roles | Rationale |
|---|---|---|
| Minimal (3) | PLATFORM, CREATIVE (SYNTH+GEN+CYBER+HYBRID), QA | Independent verification and a usable engineering path remain intact; creative breadth is serial. |
| Optimal (6) | PLATFORM, SYNTH, GEN, CYBER, HYBRID, QA | Four parallel creative lanes with dedicated platform support and independent integration. |
| Companion-expanded (7, active) | Optimal + CYDAUX | Common companion firmware, widgets, profiles, transport and cross-instrument integration; activated by owner on 27 Nov 2026. |
| Maximum practical (8) | Companion-expanded + DSP or SOUND (or Optimal + DSP + SOUND) | Select specialists according to measured workload and qualification capacity. |

Configured roster at activation: seven enabled hourly workers (Europe/London), PLATFORM :05, SYNTH :13, GEN :23, CYBER :33, HYBRID :43, QA :53, CYDAUX :58. Adjust offsets and intervals to actual run length, runner availability and WIP; staggered starts are not locks or guarantees of concurrency. Optional DSP and SOUND every 3 hours at distinct offsets initially. If qualification queues grow, slow creative starts and prioritize QA. No need to fill slots simply because available.

## Cross-lane companion mandate

All creative lanes should plan CYDaux support as the usual optional performance interface, with basic MIDI and enhanced bidirectional capabilities separately qualified. Preserve standalone operation, proceed with portable cores and emulator-first work immediately, and propose small local control seams without freezing a wire protocol. Report intended/verified tier, unsupported features and remaining integration evidence. Read [CYDAUX-001 #9](https://github.com/techrote/FM-1-VIBEWARE/issues/9) and the architecture contract. Only CYDAUX may modify the companion repository within its authorized scope; all other lanes retain the read-only boundary.

## PLATFORM — Firmware and runtime engineering (#2)
Build a small practical common toolchain, deterministic DSP/event contract and target adapters. Start from exact reviewed FM-1-MHAC #8 and ZaaggenZ-FM1 #1 evidence, not assumptions. Compare Fune, Dinghy and raw-XIP routes. Produce a reproducible actual reference target and host audition, bounded integer primitives, test fixtures, measured resource budgets, emulator support and recovery/rights ledger. Use downstream consumers to drive the API; avoid building a generic SDK before it is useful. Unblock actual creative work each run. Own shared FM-1-side control integration, capability negotiation hooks, parameter/event/telemetry semantics and validated transport adapters driven by real consumers; coordinate with CYDAUX and QA, without imposing speculative wire formats.

## SYNTH — Experimental synthesis (#3)
Invent and build distinctive engines: coupled resonators, nonlinear excitation, phase distortion, compact spectral and granular approximations, percussion, timbral morphing and effects. Start Xenoresonator. Prioritize expressive controls, musical contrast and numerical safety; compare competing algorithms on actual rendered audio and resource cost. Deliver real host and FM-1 implementations with presets, not generic oscillator demos. Own Xenoresonator material editing, excitation, damping/coupling, XY and resonance visualization semantics/fixtures.

## GEN — Generative composition (#4)
Design playable alternative sequencers, interacting clocks, procedural patterns, cellular automata, evolutionary rules and time structures. Start Chronomorph. Include internal sound so instruments are useful standalone. Establish musical event semantics, authored compositions, reproducibility, bounded queue behaviour and tempo/transport stress tests. Make generative behaviour legible and steerable rather than arbitrary randomness. Own Chronomorph companion pattern editing, polymetric sequencing, clock visualization and temporal manipulation semantics/fixtures.

## CYBER — Cybernetic and experimental systems (#5)
Build unusual instruments informed by artificial life, feedback, semiotics, dynamical systems and adaptation. Start Ecophon. Make system state and interventions causally meaningful and audible; compare simpler baselines. Respect hard real-time limits, bounded memory and stable output; avoid purely theoretical experiments. Deliver playable controls and distinct musical regimes. Own Ecophon companion ecological visualization, agent/resource state, environmental interventions and performance controls/fixtures.

## HYBRID — Audiovisual and performance systems (#6)
Build FM-1 audiovisual instruments with optional CYDaux performance interfaces, XY fields, procedural visuals and distributed interaction. Start Grimoire, one complete rite first. Own rite selection, gestural control, audiovisual behaviour, instrument-specific views and simulator fixtures; do not create another CYD firmware or own common transport/UI infrastructure. FM-1 remains independent. Coordinate shared control integration with PLATFORM and CYDAUX. Derive capabilities from evidence; prioritize expressive performance, bounded transport, reconnect, panic and real virtual/physical distinctions.

## QA — Independent qualification and mergedown (#7)
Rebuild exact candidates, independently reproduce host/target/emulator results, inspect failure logs, fix concrete defects, qualify extracted packages and maintain a playable catalogue. Coordinate shared changes and prepare owner-reviewable merges. Do not self-certify authored repairs; obtain a separate reproduction or label as provisional. Preserve Draft/HOLD, release and physical gates. No busywork audit or periodic report-only runs if implementation fixes are available. Independently qualify companion semantic mappings, supported transport tiers, capability mismatches, disconnect/reconnect, stale replay, panic, telemetry accuracy, resource budgets and legacy profile regressions; record companion status independently of standalone instrument delivery.

## CYDAUX — Common companion engineering (#9; active)

Own the one common FM-1-CYDaux firmware, reusable widgets, versioned profiles, transport adapters, shared simulator and cross-instrument integration, retaining existing third-party firmware support. Coordinate with PLATFORM on the FM-1 side and creative workers on musical semantics; HYBRID owns audiovisual concepts, QA independently qualifies. Start with two different real instrument consumers, then expand across the catalogue. Preserve standalone operation and separate basic MIDI from enhanced bidirectional capabilities; no wire freeze before interoperability proof. See #9 for the activated recurring mandate and acceptance criteria. Owner authorization covers issue-scoped FM-1-CYDaux implementation and coordinated VIBEWARE interface/fixture contributions; preserve Draft/HOLD and no unsolicited merges/flashing.

## DSP — Optional resource and acceleration engineering
Profile real downstream bottlenecks and identify measured limiting resources. Explore fixed point, table compression, interpolation, SIMD/ISA only when supported, memory layouts, voice scheduling and algorithm alternatives. Compare exact or tolerance-qualified audio, worst-case timing and footprint against baselines. Agree ownership before touching another worker's instrument; avoid speculative optimization. Deliver tested improvements via separate PRs and coordinate adoption with PLATFORM and QA.

## SOUND — Optional sound design and performance engineering
Take playable candidates, explore the actual engine, design useful macro mappings, factory patches, performance gestures, demo songs and comparative audio. Correct real usability and sound-design deficiencies in coordinated scoped PRs. Build useful audition tooling and catalogue contributions with QA. Do not claim subjective listening without actual listening; distinguish measured signals and authored intent. No cosmetic-only proliferation.

## When to expand or contract
Keep seven workers running, including CYDAUX. Consider eight only when QA has capacity and a measured specialist workload exists. Collapse into three if creative throughput is low or infrastructure remains blocked for a sustained period. Keep separate independent QA regardless of roster size. Revisit after the first end-to-end instrument deliveries.
