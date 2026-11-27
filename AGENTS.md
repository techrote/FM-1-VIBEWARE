# VIBEWARE worker protocol

Repository: techrote/FM-1-VIBEWARE; CYDAUX #9 additionally has issue-scoped FM-1-CYDaux implementation authorization. Read README.md, docs/WORKERS.md, docs/ARCHITECTURE.md and docs/QUALIFICATION.md. The programme is #1. Use linked issues and live PR state rather than assumptions about previous runs.

## On every invocation

1. Discover current main, open issues, PRs, recent CI and predecessor work for your lane. Resume the most valuable unfinished implementation; repair failures before opening another instrument.
2. Verify that another run is not actively writing the same branch or shared files. Claim an issue with a short owner/run checkpoint; if overlap is uncertain, use an isolated branch or work on an unclaimed task. An issue comment alone is not a lock. Never force-push or race shared refs; use fresh heads and expected-SHA checks where supported.
3. Implement substantive code and experiments, execute available tests/builds and retain real evidence. Do not merely write plans, invent results or spend the run manufacturing issues. CI jobs that are queued or skipped do not count as passed. Record actual blockers and use alternative useful work when execution is unavailable.
4. Update the existing issue-scoped Draft/HOLD PR; commit tested source and concise evidence, identify exact revisions, artifact URLs and next executable step. No unsolicited upstream writes, merges, releases or flashing. No changing qualification gates just to pass.
5. Keep one active instrument per creative lane until its first playable milestone; thereafter at most two. Open new concepts only after checking the existing catalogue and WIP. End the run when meaningful work is complete; do not wait artificially.

## Ownership

| Lane | Primary paths | Initial issue |
|---|---|---|
| PLATFORM | platform/, shared build/toolchain/target adapters | #2 |
| SYNTH | instruments/xenoresonator/, later synthesis instruments | #3 |
| GEN | instruments/chronomorph/, later composition instruments | #4 |
| CYBER | instruments/ecophon/, later cybernetic instruments | #5 |
| HYBRID | instruments/grimoire/, companion/grimoire/ (instrument-specific design/fixtures only), later hybrid instruments | #6 |
| QA | qualification/, catalogue/, integration/release coordination | #7 |
| CYDAUX | common firmware, widgets, profiles, transports and cross-instrument integration in FM-1-CYDaux; coordinated VIBEWARE interfaces/fixtures | #9 |
| DSP (optional) | scoped optimization PRs, agreed with affected owner | #2 or assigned bottleneck |
| SOUND (optional) | instrument-specific presets/demos and performance refinement, agreed with affected owner | #7 or assigned instrument |

These are ownership boundaries, not yet implemented directories. Common interfaces, workflows and target changes belong to PLATFORM with QA review; creative lanes can build portable engines immediately and propose minimal shared changes separately. QA may repair defects with explicit coordination but should not silently overwrite active creative work.

## Companion mandate — all lanes

Read #9 and the companion contract in docs/ARCHITECTURE.md. CYDaux compatibility is the normal expectation for most instruments, not a HYBRID-only feature. Creative lanes own musical controls, state, profiles/fixtures and instrument-specific semantics; PLATFORM owns shared FM-1-side control/runtime integration. HYBRID owns experimental audiovisual design, not common companion firmware. The active CYDAUX lane owns the shared companion under owner authorization; QA independently qualifies both ends. Other VIBEWARE lanes must not write to FM-1-CYDaux. Keep portable engine and emulator-first work moving; use local provisional control interfaces, not incompatible wire protocols or per-instrument firmware forks. State intended capability tier and evidence; document exceptions and never make the CYD mandatory.

## Acceptance and safety

All experimental implementation PRs remain Draft/HOLD until independent qualification and owner review. QA may prepare merge-ready candidates but does not merge without owner authorization. Initial charter and planning files are on main as the bootstrap, not an exception for firmware changes. Prefer original code; record upstream revision, license, notices, changes, distribution obligations and dependency integrity before adoption. Do not copy code from a repository merely because it is accessible. No hardware flash, installable image distribution or physical claims without the board/recovery/format/rights gates in docs/QUALIFICATION.md. Never report listening, execution or timing measurements that did not occur.

Seven hourly workers were enabled at activation on 27 Nov 2026; inspect live schedules for changes.
