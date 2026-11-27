# Architecture and development routes

VIBEWARE is a collection of independent instruments, not a mandatory monolithic firmware. The initial architecture is a hypothesis to validate against the real hardware/toolchain and reference implementations.

## Implementation routes

- **Portable engine + Fune plugin**: preferred for self-contained sound engines when Fune's actual supported ABI, lifecycle and distribution requirements fit.
- **Portable engine + custom firmware/host adapter**: choose for novel sequencing, interaction or scheduling that a plugin cannot express. Audit the actual target and toolchain; raw emulator XIP is not a flashable firmware format.
- **FM-1 + optional CYD companion**: use for expressive XY controls, visualization and distributed interaction. Standalone FM-1 fallback is required. MIDI/serial/BLE/Wi-Fi capabilities are per firmware/device and must be verified.
- **Desktop/virtual audition**: a complement to every route. Drive the actual portable engine and test the target separately; no unrelated sound generator posing as a firmware demo.

## Intended layout (created by implementing workers as needed)

    platform/             reviewed target adapters, portable primitives and build tooling
    instruments/<id>/     self-contained source, presets, tests and instrument-specific adapters
    companion/<id>/       optional CYD software and simulator
    qualification/        independent runners, fixtures and evidence
    catalogue/            playable catalogue and package manifests
    docs/                 contracts and short reference notes

An instrument should have an isolated state, explicit lifecycle/reset, bounded allocation/event storage, control mapping and render/update separation. Avoid allocation, blocking I/O, unbounded work and unsafe arithmetic in real-time paths. Use a shared sample/event contract only after PLATFORM demonstrates it on a real engine; no unverified constants (sample rate, RAM, flash, voice count, CPU budget) should be prescribed as hardware facts. Measure from target build/map, actual emulator execution and physical tests separately.

Prefer deterministic seedable behaviour, fixed-width types, explicit saturation/overflow handling, headroom and stable feedback. Test block partition, MIDI release/panic, parameter transitions, invalid inputs, persistence where used, and long-run state. Define what may intentionally differ across routes.

## Collaboration

One issue-scoped branch/PR per substantive instrument or platform change. Main is the accepted reference; pin any stacked dependency explicitly and reconcile before qualification. Shared-interface changes must have a consumer and independent review. Favor small local adapters over blocking every creative stream on a platform abstraction. Use actual build/run outputs to decide the route, not ideological commitment.

## References and provenance

The README identifies four owner repositories and upstream discovery pointers. PLATFORM must record exact commit/tree, compiler revision, build instructions, licenses/notices, source modifications and artifact hashes. No automatic copying or upstream writes. Treat unmerged reference PRs as candidates. Owner authorization and rights compatibility are independent of technical feasibility.
