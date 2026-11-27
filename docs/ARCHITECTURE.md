# Architecture and development routes

VIBEWARE is a collection of independent instruments, not a mandatory monolithic firmware. The initial architecture is a hypothesis to validate against the real hardware/toolchain and reference implementations.

## Implementation routes

- **Portable engine + Fune plugin**: preferred for self-contained sound engines when Fune's actual supported ABI, lifecycle and distribution requirements fit.
- **Portable engine + custom firmware/host adapter**: choose for novel sequencing, interaction or scheduling that a plugin cannot express. Audit the actual target and toolchain; raw emulator XIP is not a flashable firmware format.
- **FM-1 + optional CYDaux companion**: cross-cutting expectation for most instruments on either FM-1 route, not a distinct requirement to use a hybrid firmware. Extend performance controls, visualization and distributed interaction; standalone FM-1 operation is required. MIDI/serial/BLE/Wi-Fi capabilities are per firmware/device and must be verified.
- **Desktop/virtual audition**: a complement to every route. Drive the actual portable engine and test the target separately; no unrelated sound generator posing as a firmware demo.

## Intended layout (created by implementing workers as needed)

    platform/             reviewed target adapters, portable primitives and build tooling
    instruments/<id>/     self-contained source, presets, tests and instrument-specific adapters
    companion/<id>/       instrument-specific profile sketches, UI concepts and test/simulator fixtures; no separate CYD firmware
    qualification/        independent runners, fixtures and evidence
    catalogue/            playable catalogue and package manifests
    docs/                 contracts and short reference notes

An instrument should have an isolated state, explicit lifecycle/reset, bounded allocation/event storage, control mapping and render/update separation. Avoid allocation, blocking I/O, unbounded work and unsafe arithmetic in real-time paths. Use a shared sample/event contract only after PLATFORM demonstrates it on a real engine; no unverified constants (sample rate, RAM, flash, voice count, CPU budget) should be prescribed as hardware facts. Measure from target build/map, actual emulator execution and physical tests separately.

Prefer deterministic seedable behaviour, fixed-width types, explicit saturation/overflow handling, headroom and stable feedback. Test block partition, MIDI release/panic, parameter transitions, invalid inputs, persistence where used, and long-run state. Define what may intentionally differ across routes.

## Common companion contract (COMPANION-MANDATE-001)

[FM-1-CYDaux](https://github.com/techrote/FM-1-CYDaux) is the common companion firmware home. [CYDaux #1](https://github.com/techrote/FM-1-CYDaux/pull/1) provides a draft reference for existing Melodee, SLOOP, Skiff and X0X profiles, direct BLE-MIDI where supported and an authenticated Wi-Fi-to-USB-MIDI bridge; richer SLOOP feedback is profile-specific. Software tests are not physical transport qualification. [cyd-diviner](https://github.com/techrote/cyd-diviner) supplies touch, rendering and procedural visual design references. Reuse reviewed capabilities and maintain third-party compatibility; no assumption of identical FM-1 connectivity or permission to copy source.

**Semantic seam, not frozen wire format.** For each applicable instrument expose a minimal versioned profile/capability description: instrument and profile identity/version; parameter IDs, ranges, units, defaults, access direction; preset selection, performance events, modulation/XY, clock/transport and read-only telemetry as appropriate. Explicitly mark unsupported/unknown features. Keep updates bounded, validated, nonblocking and separated from audio rendering; rate-limit/coalesce telemetry, reject incompatible versions and stale sessions, preserve release/panic and avoid replay after reconnect. Prefer existing MIDI and CYDaux mechanisms; select transport after real consumer and interoperability evidence, not a speculative universal protocol.

| Capability tier | Meaning |
|---|---|
| Standalone | FM-1 internal controls/sound remain usable with no CYD; required for every instrument. |
| Basic MIDI | Verified note/CC/clock or other mapped performance messages as supported; feedback not implied. |
| Enhanced | Verified negotiated bidirectional controls and/or telemetry, per route and profile; not mandatory where infeasible. |

Expose local/model/demo visual state as such; never present it as device telemetry. Aim for basic or enhanced compatibility for most instruments, report the intended tier and actual independent qualification separately, and justify exceptions by actual constraints. Keep the portable engine productive with a small local semantic interface and deterministic fixtures even if transport is blocked.

| Instrument | Companion expectations |
|---|---|
| Xenoresonator (#3) | Material/preset editor, excitation, damping/coupling, expressive XY; resonance visualization using verified telemetry or explicitly labelled local model. |
| Chronomorph (#4) | Pattern editing, polymetric sequencer/clock visualization, start/stop/reset, temporal warping and modulation. |
| Ecophon (#5) | Ecological/agent/resource visualization, environmental interventions, regime/preset and performance controls; distinguish actual from model state. |
| Grimoire (#6) | Rite selection, gestural XY, procedural visualizations and meaningful audiovisual interaction; optional companion, not a unique CYD runtime. |

PLATFORM owns shared FM-1-side adapters and semantics integration; creative lanes own instrument-specific behaviour and mappings; HYBRID owns audiovisual experiments; proposed CYDAUX #9 owns common firmware, reusable widgets, profiles and transports when authorized; QA independently qualifies end-to-end interoperability. VIBEWARE may contain instrument-side mappings, provisional profile descriptions and simulator fixtures, not duplicated companion firmware. No new CYD wire protocol is frozen by this charter. The emulator-first delivery handoff in #1/#2 remains in force.

## Collaboration

One issue-scoped branch/PR per substantive instrument or platform change. Main is the accepted reference; pin any stacked dependency explicitly and reconcile before qualification. Shared-interface changes must have a consumer and independent review. Favor small local adapters over blocking every creative stream on a platform abstraction. Use actual build/run outputs to decide the route, not ideological commitment.

## References and provenance

The README identifies four owner repositories and upstream discovery pointers. PLATFORM must record exact commit/tree, compiler revision, build instructions, licenses/notices, source modifications and artifact hashes. No automatic copying or upstream writes. Treat unmerged reference PRs as candidates. Owner authorization and rights compatibility are independent of technical feasibility.
