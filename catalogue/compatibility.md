# Compatibility matrix — QA-001 (27 November 2026)

Frozen candidate snapshot; no release or physical readiness implied.

| Instrument | Exact host candidate | Author CI | Independent host/package | Target / virtual | Companion |
|---|---|---|---|---|---|
| Xenoresonator | fa27a317bb116f2afb62a710876f96314756f814 (#12) | [PASS](https://github.com/techrote/FM-1-VIBEWARE/actions/runs/46039808732) | NOT RUN | NOT RUN | Local profile/preview only |
| Chronomorph | 697f1bb74b98e761477795166be2dc9f2c5058ae (#14) | [PASS](https://github.com/techrote/FM-1-VIBEWARE/actions/runs/46041919275) | NOT RUN | NOT RUN | Local pattern/clock preview only |
| Ecophon | acdc41839665271372cd69df1d09f5550556c87e (#8) | [PASS](https://github.com/techrote/FM-1-VIBEWARE/actions/runs/46042452403) | Archive/rebuild QA submitted, NOT RUN until observed | NOT RUN | Local native state and intervention fixture only |
| Grimoire Orbit Gate | 03102e8d82148a6dba871024f5944246e0c913e2 (#10, qualified predecessor) | [PASS](https://github.com/techrote/FM-1-VIBEWARE/actions/runs/46036438577) | [Independent Linux and Windows native HTTP PASS](https://github.com/techrote/FM-1-VIBEWARE/actions/runs/46037411888); original archive not yet exercised | [PLATFORM target and Linux virtual PASS](https://github.com/techrote/FM-1-VIBEWARE/actions/runs/46039864752) at 4133787e51010581c9ed594db7e57b9506894c84; independent rebuild submitted | Local native-core fixture only |
| Grimoire current companion | f58e73ddf74c061473b5f14c79b73cfaf2618fe4 (#10) | [FAIL](https://github.com/techrote/FM-1-VIBEWARE/actions/runs/46044975162): unsupported Chromium runner OS; Windows cancelled | NOT RUN | Predecessor target core only | Browser gate remains open |

All four intend basic MIDI and/or enhanced capability where supported. **Neither tier is independently verified on a device or shared companion route.** Physical HOLD for all. No shared CYDaux firmware, BLE/USB-MIDI transport, actual device telemetry, ESP32 target build or legacy Melodee/SLOOP/Skiff/X0X regression independently qualified here.

## Original owner-review native downloads

| Instrument | Windows archive | SHA-256 of original ZIP |
|---|---|---|
| Ecophon | [15221151301](https://github.com/techrote/FM-1-VIBEWARE/actions/runs/46042452403/artifacts/15221151301) | a3b71964bab66df8eff0b537b5171706ea0baf57171435f2b367717a2f356974 |
| Xenoresonator | [15220105065](https://github.com/techrote/FM-1-VIBEWARE/actions/runs/46039808732/artifacts/15220105065) | c14cd015382109fd143c2438322221c16128c90644ea6d8bdf502083a6229fa1 |
| Chronomorph | [15221415407](https://github.com/techrote/FM-1-VIBEWARE/actions/runs/46041919275/artifacts/15221415407) | 211bab7f57b894c7c0bd1936263c670a81fe15e4917d0eb847fc07fb68a39cfe |

These are author artifacts, not independently released packages. Download digests are GitHub artifact metadata until verified against actual ZIP bytes. The virtual evidence [15218964969](https://github.com/techrote/FM-1-VIBEWARE/actions/runs/46039864752/artifacts/15218964969) contains actual emulator PCM, logs/map and hashes, not an executable or raw XIP deliverable. Combined distribution rights are unresolved. No installation images.

Grimoire predecessor QA rebuilt exact source and tested real HTTP and control PCM in a path containing spaces; not downloaded archive or actual browser. Current browser CI failure occurs during Playwright installation before browser test execution: Ubuntu 26.04 unsupported by Playwright 1.57.0; communicated to HYBRID for scoped fix.

New independent job consumes the original Ecophon ZIP by exact ID/hash, executes its native CLI and live endpoint from a path with spaces, rebuilds and compares independent control trajectories. Virtual job consumes the original PLATFORM evidence by archive digest, checks exact PCM and XIP hash and performs fresh shared pinned target compilation and emulator execution. Status remains pending until actual CI is observed. No parallel emulator harness or licensing waiver.
