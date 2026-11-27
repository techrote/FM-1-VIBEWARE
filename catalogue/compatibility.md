# Initial compatibility matrix — QA-001

Snapshot of exact instrument candidates, not a declaration of release readiness.

| Instrument | Exact candidate | Creative native CI | Independent host | Target build / emulator | Companion intention / evidence | Physical |
|---|---|---|---|---|---|---|
| Xenoresonator | No PR at inspection | NOT RUN | NOT RUN | NOT RUN | Expected; no verified tier | HOLD |
| Chronomorph | No PR at inspection | NOT RUN | NOT RUN | NOT RUN | Expected; no verified tier | HOLD |
| Ecophon | b5bd9c6be36f0576450bf871581ad4fb5dda9415 (#8) | [PASS](https://github.com/techrote/FM-1-VIBEWARE/actions/runs/46035302089) | NOT RUN | NOT RUN | Expected; no verified tier | HOLD |
| Grimoire Orbit Gate | 03102e8d82148a6dba871024f5944246e0c913e2 (#10) | [PASS](https://github.com/techrote/FM-1-VIBEWARE/actions/runs/46036438577) | Linux real HTTP/PCM PASS, Windows independent CI pending | NOT RUN | Enhanced intended, basic MIDI fallback proposed; local native-core fixture only | HOLD |

Grimoire QA: five exact source blobs independently reconstructed and Git blob hashes compared with candidate tree. GCC/UBSan-built shared library launched by actual host.py in a temporary path containing spaces; HTTP calls from an independent client. Five distinct PCM witnesses, exact reset repeat, 10 rejection cases, release tail, panic, lease expiry, reconnect and stale event rejection PASS. The local run was a rebuilt/staged package, **not** a downloaded artifact extraction or browser session. The QA harness itself awaits separate CI reproduction. See [qualification](../qualification/README.md).

No shared CYDaux firmware, BLE/USB-MIDI transport, device telemetry, ESP32 target build or legacy Melodee/SLOOP/Skiff/X0X regression is independently qualified here. Do not infer support from a profile. No VIBEWARE emulator target available at inspection; consume PLATFORM #2 when ready. No physical release or licensing waiver.
