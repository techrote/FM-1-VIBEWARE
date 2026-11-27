# Independent native qualification

QA #7. Rebuild exact frozen instrument candidates without modifying their active branches. The initial harness operates the real Grimoire HTTP server and native C core, from an independently rebuilt staged package in a path containing spaces.

Run: python qualification/orbit_http.py /path/to/exact/grimoire/checkout

Expected exact candidate: 03102e8d82148a6dba871024f5944246e0c913e2. Source blob IDs verified locally:
- instruments/grimoire/orbit.c: 191827b6b08ef718758e84ffd4c35b492cbdc5a3
- instruments/grimoire/orbit.h: 9cd23e73a6bd6903c2c712fef86110875c148de4
- companion/grimoire/session.c: 72025b143a71a4c1787867f9cbf22e2710c3dcc8
- companion/grimoire/session.h: 5751c33e0d4ce3109f52dd68d90346b9cd878055
- companion/grimoire/host.py: 485d53575d66a513a8504c1cc855682357db5a12

Local Linux GCC/UBSan baseline recorded in orbit-http-baseline.json. The CI matrix checks exact checkout and compares real HTTP receipt byte-derived hashes to baseline on Windows/Linux. This is independent **host** qualification only: not a browser run, published ZIP extraction, target compile, virtual FM-1 or physical transport. No device feedback claim; actual local native core state is labeled. Do not change baseline on failure without diagnosis and explicit revision update. Future runs should explicitly pin newer candidate heads and keep old receipts.

See [compatibility matrix](../catalogue/compatibility.md). Shared emulator tests await PLATFORM #2; no second emulator harness. No firmware packages or redistribution here.
