# Compatibility matrix — QA-001 (27 November 2026)

Frozen snapshot; no release or physical readiness implied. New independent archive runs are not PASS until observed.

| Instrument | Current host candidate | Author native/browser | Independent host/package | Target / virtual | Companion |
|---|---|---|---|---|---|
| Xenoresonator | cc3aa472b267e601d11c811fe7f390970db5348b (#12) | [native PASS](https://github.com/techrote/FM-1-VIBEWARE/actions/runs/46047918198); browser NOT RUN | [Windows/Linux archive and independent rebuild PASS](https://github.com/techrote/FM-1-VIBEWARE/actions/runs/46052567781) | #15 [author target and virtual USB PASS](https://github.com/techrote/FM-1-VIBEWARE/actions/runs/46048299250) at 3449ead4dd13d91ba0a57262a48349f38d6c465c; QA independent NOT RUN | Local native fixture; virtual USB author evidence separate, physical HOLD |
| Chronomorph | be57d9f77e9325271adbd4558dfd554c6cd81e19 (#14) | [native and Chromium PASS](https://github.com/techrote/FM-1-VIBEWARE/actions/runs/46049840733) | [Windows/Linux archive and independent rebuild PASS](https://github.com/techrote/FM-1-VIBEWARE/actions/runs/46052418981), identical PCM/state | NOT RUN | Local native clock fixture |
| Ecophon | 88ef1da1d013457c416e2168ae64836a68fbc4d4 (#8) | [native and Chromium PASS](https://github.com/techrote/FM-1-VIBEWARE/actions/runs/46051102021) | [Prior acdc418 archive/rebuild PASS](https://github.com/techrote/FM-1-VIBEWARE/actions/runs/46045927224); [current Windows/Linux archive/rebuild PASS](https://github.com/techrote/FM-1-VIBEWARE/actions/runs/46052418981), identical PCM/state | #13 73719c6 [target PASS, virtual partial FAIL](https://github.com/techrote/FM-1-VIBEWARE/actions/runs/46046765301): low/high/repeat PCM and silent tail, preset script rejected SEL; SCL repair coordinated | Local native ecosystem state |
| Grimoire Orbit Gate | e999ac2d3c0556132f92ffd1036617ac87c0118f (#10) | [native and Chromium PASS](https://github.com/techrote/FM-1-VIBEWARE/actions/runs/46051873988) | [Prior exact native HTTP PASS](https://github.com/techrote/FM-1-VIBEWARE/actions/runs/46037411888); [Current original Windows/Linux archive and independent rebuild/HTTP PASS](https://github.com/techrote/FM-1-VIBEWARE/actions/runs/46052765775), exact cross-OS PCM/WAV | #13 4133787 [independent target and virtual replay PASS](https://github.com/techrote/FM-1-VIBEWARE/actions/runs/46045927224), exact PCM/XIP receipts | Local native XY fixture; no physical link |

All intend basic MIDI and/or enhanced capability where supported. No independent physical or full end-to-end companion tier PASS. CYDaux #2 author software/ESP32 qualification at 029bb05e186cfaa0b25651488239d8402db01637 ([run](https://github.com/techrote/FM-1-CYDaux/actions/runs/46048878617)); independent common-profile/legacy/bridge QA still NOT RUN. Virtual Windows executable packaging and combined distribution rights remain open; no raw XIP or firmware release.

## Original native owner-review downloads (author artifacts)

| Instrument | Windows archive | SHA-256 of original ZIP |
|---|---|---|
| Xenoresonator | [15222813934](https://github.com/techrote/FM-1-VIBEWARE/actions/runs/46047918198/artifacts/15222813934) | 51bc83a5953d5679ac91e0ec4195db4098023482bd2a3bc58ae778fd27907024 |
| Chronomorph | [15224186300](https://github.com/techrote/FM-1-VIBEWARE/actions/runs/46049840733/artifacts/15224186300) | 56e932ba9c9d87233a2ab4a9b0667c14f2894a74cdd326209cb7f6bcabccaba9 |
| Ecophon | [15224337693](https://github.com/techrote/FM-1-VIBEWARE/actions/runs/46051102021/artifacts/15224337693) | 8dc286554c5747cc0fa380c3bee4ae986e8ce100c3a77575425b22aebf94a1aa |
| Grimoire | [15224732379](https://github.com/techrote/FM-1-VIBEWARE/actions/runs/46051873988/artifacts/15224732379) | a555e3f36dd87f61dd138e040f25c97373f5c5854a72be21ac67839211feb61e |

Download hashes are GitHub artifact metadata until independently verified against bytes. Native browser fixtures require Python 3; not virtual FM-1 executables. [Independent Orbit virtual evidence](https://github.com/techrote/FM-1-VIBEWARE/actions/runs/46045927224/artifacts/15223056256) contains audio and qualification receipts, not installable images.

The archive workflow pins each exact source and original ZIP digest; executes original and independently rebuilt native binaries, compares all demo WAVs and actual HTTP control/state/PCM witnesses in paths with spaces. First Xeno Linux test found a late damping intervention at 250 ms indistinguishable from baseline under chosen strike/damping; corrected experiment intervenes at 50 ms during decay and separately records late comparison, not a relaxed early-intervention gate. No cross-lane changes.

The Xenoresonator early (50 ms) damping comparison passed in both OS jobs of run 46052567781, along with the coupling, release, panic, expiry and exact WAV tests. Grimoire archive format includes exactly one generated nested entry `__pycache__/host.cpython-312.pyc` in each verified ZIP; QA skips only that file, retains all previous path restrictions and independently runs extracted source and native code. Both repaired Grimoire jobs PASS with exact cross-OS WAV and HTTP PCM receipt equality. No instrument source changed.

Source-only [native selector](selector.py) plus [pinned manifest](native-packages.json) accepts original downloaded Windows ZIPs; no repackaging of binaries, no virtual executable, no device/transport or physical acceptance. All four current native archives independently qualified; actual Windows selector startup PASS.

## Independent delivery checkpoint

All four current native archives: 15 authored demo WAVs reproduced byte-identically and cross-OS native HTTP PCM/state receipts equal. [Selector CI PASS](https://github.com/techrote/FM-1-VIBEWARE/actions/runs/46052765800) on c8885055c559cc48dc5cd5cfe637fd6a88ed4659, actual original Windows package readiness for all four. [Original tested selector source artifact](https://github.com/techrote/FM-1-VIBEWARE/actions/runs/46052765800/artifacts/15225575583) (SHA256 15e673e2d325d9d0c9f43d43aa39e7bf6f09a246fe6a60734ed8887c459b1360) predates the Grimoire QA promotion and requires --allow-provisional for that instrument. Manifest promotion does not change selector executable code or pinned package hashes. Grimoire Windows and Linux qualification receipts: [15225675356](https://github.com/techrote/FM-1-VIBEWARE/actions/runs/46052765775/artifacts/15225675356), [15225945142](https://github.com/techrote/FM-1-VIBEWARE/actions/runs/46052765775/artifacts/15225945142). No independent Windows virtual FM-1 package yet.
