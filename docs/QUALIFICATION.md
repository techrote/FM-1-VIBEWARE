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

## Owner delivery

Provide a source-linked downloadable host/virtual evaluator and WAV gallery; include controls, presets, demo compositions where appropriate, artifact checksums, exact revisions, CI links and known limitations. Use an installable firmware/plugin package only when target identity, supported format, recovery and rights are established and owner authorization permits it. No unattended flashing, updater experiments on a device, or physical success claims.

Record source provenance, notices, licenses, toolchain identity, dependency hashes and required corresponding source where applicable. No repository-wide license decision has been made. Keep implementation PRs Draft/HOLD until independent qualification and owner review; only owner-authorized integration. QA should repair concrete failures rather than produce repeated reports.
