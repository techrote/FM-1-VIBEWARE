# Qualification and delivery

Each instrument carries explicit, independently verifiable status. A green host build is not a target run, and a successful emulator run is not physical hardware qualification.

| Gate | Required evidence |
|---|---|
| Concept | Distinct musical behaviour, controls and an executable plan. |
| Host executable | Actual implementation builds and runs, deterministic fixtures, representative audio, interactive audition where practical. |
| Target build | Exact toolchain/adapter, successful compile/link and map/size evidence, ABI and format review. |
| Virtual target | Actual supported fm1-emu execution, control/audio witnesses, pinned emulator and configuration; otherwise a precise reproducible blocker. |
| Independent package | Clean reproduction, exact revision, extracted artifact execution, manifests, hashes, source/rights checks and known limits. |
| Physical owner evaluation | Exact board revision, safe documented recovery, supported install format, authorization, physical controls/audio/timing and owner acceptance. |

Use PASS/FAIL/BLOCKED/NOT RUN/NOT APPLICABLE with evidence at each gate. Never substitute one gate for another, silently omit failures or report hardware performance from host timings.

## Core test cases

- Reset and lifecycle, parameter changes, zero/maximum controls, deterministic seeds, numerical/overflow safety, sustained runs.
- Real-time work bounds, memory and target map/size, clipping/headroom, stable feedback, mute, MIDI release/panic and transport/reconnect as applicable.
- Actual-core PCM, meaningful comparison against baselines, at least several distinct authored presets and demo patterns when relevant. Listening claims require actual listening; waveform/feature measurements are not subjective audition.
- Clean host reproduction, Windows package extraction including paths with spaces, actual target or emulator witness, reproducibility and artifact hashes.

## Companion qualification (separate from standalone gates)

For most instruments, record intended and demonstrated companion capability tier (standalone, basic MIDI, enhanced bidirectional), exact instrument/profile and companion revisions, transport/route, directions and unsupported/unknown capabilities. Document any exception to companion support. Do not block portable engine or emulator delivery on a companion; never infer physical support from a simulator or host build.

- Prove FM-1 remains playable with CYD absent, disconnected, incompatible or overloaded. Exercise actual mapped parameter limits/defaults, presets, XY/modulation, transport and performance events; compare real audio/state responses where applicable.
- For basic MIDI verify actual mapped messages and note release/panic, without claiming feedback. For enhanced paths verify negotiation/version mismatch, real bidirectional read/write and telemetry freshness/accuracy. Distinguish local/model/demo from observed device state; test malformed/unsupported messages, bounded queues, rate limiting, reconnect generations, no stale replay, timeout and safe fallback.
- Use the shared CYDaux controller/simulator and exact target build when available. Independently test actual end-to-end routes, display/update latency, memory/CPU, legacy Melodee/SLOOP/Skiff/X0X profile regressions and owner hardware steps. Maintain separate software/simulator, target build, virtual/bridge and physical evidence; unavailable tests are BLOCKED/NOT RUN, not PASS.

QA owns independent receipts and catalogue compatibility matrix; PLATFORM and creative lanes supply FM-1-side witnesses. CYDAUX #9 is active with issue-scoped companion implementation authorization; companion support is still not a prerequisite to standalone delivery. Existing emulator-first and physical/rights gates are unchanged.

## Owner delivery

Provide a source-linked downloadable host/virtual evaluator and WAV gallery; include controls, presets, demo compositions where appropriate, artifact checksums, exact revisions, CI links and known limitations. Use an installable firmware/plugin package only when target identity, supported format, recovery and rights are established and owner authorization permits it. No unattended flashing, updater experiments on a device, or physical success claims.

Record source provenance, notices, licenses, toolchain identity, dependency hashes and required corresponding source where applicable. No repository-wide license decision has been made. Keep implementation PRs Draft/HOLD until independent qualification and owner review; only owner-authorized integration. QA should repair concrete failures rather than produce repeated reports.
