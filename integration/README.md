# Private standalone audition collection — Draft/HOLD

Integration #34, QA #7/#30. This is **native Windows host audition only**, not virtual FM-1, flashable firmware, or a new independent qualification claim. The QA-owned selector and catalogue are consumed at exact revision `e6a3a79461c7f2672b266685c1ed3081f384c17c`; their Git blob identities are enforced before execution. No shared catalogue or original candidate branch is modified.

Download the exact original GitHub Actions ZIPs (GitHub authentication may be required). Save them under these names in one local directory. Do not unzip or repackage the original archives:

| Filename | Original artifact | Independent QA evidence |
|---|---|---|
| chronomorph.zip | [15257079145](https://github.com/techrote/FM-1-VIBEWARE/actions/runs/46130204509/artifacts/15257079145) | [46137407993](https://github.com/techrote/FM-1-VIBEWARE/actions/runs/46137407993) |
| ecophon.zip | [15256006594](https://github.com/techrote/FM-1-VIBEWARE/actions/runs/46126318152/artifacts/15256006594) | [46137407993](https://github.com/techrote/FM-1-VIBEWARE/actions/runs/46137407993) |
| xenoresonator.zip | [15246065654](https://github.com/techrote/FM-1-VIBEWARE/actions/runs/46101786743/artifacts/15246065654) | [46105003795](https://github.com/techrote/FM-1-VIBEWARE/actions/runs/46105003795) |
| grimoire.zip | [15245854227](https://github.com/techrote/FM-1-VIBEWARE/actions/runs/46104126354/artifacts/15245854227) | [46105003795](https://github.com/techrote/FM-1-VIBEWARE/actions/runs/46105003795) |

Use Python 3.10+; no pip dependencies. Extract the source-only integration delivery (after successful CI) so that collection.py and qa-selector/ are adjacent. Alternatively retrieve the three original files selector.py, native-packages.json and SELECTOR.md from catalogue/ at the frozen QA revision, preserving original file bytes. Windows launch:

```text
python collection.py prepare "original archives" --out "Owner audition"
python collection.py check "Owner audition"
python collection.py launch "Owner audition" --instrument xenoresonator
```

Select chronomorph, ecophon or grimoire in the same way. Close the local server with Ctrl+C before launching another. The selector retains its original verified extraction and readiness safeguards. The integration wrapper verifies all four original archives on each invocation; use a single local invocation at a time. No automatic downloads, no driver changes, no hardware access. The source-only hosted artifact does not contain any native instrument archives or binaries. Assemble your private local copy from the original artifacts; rights review is still required for redistribution.

## Integration author evidence

28 November 2026: all four actual downloaded ZIP digests matched the independently qualified QA pins; 106 ZIP entries total passed CRC validation; all four exact entrypoint/DLL pairs present. Two separate assemblies produced byte-identical collection.json receipts. Existing destination, corrupt archive, missing archive and missing QA selector were refused. Local script Git blob e38ca9490d70a0e78d0f30213a5c406487c910aa, SHA-256 e2b5dd5d72e97db31663ddfff57fcb633176d28cafc2c180e1b339f48bda. Direct Git checkout blocked by DNS; artifact retrieval succeeded through repository connector. No Windows runtime/selector launch or native audio executed locally. New hosted workflow exercises all four exact original archives using pinned QA selector and paths with spaces; results pending until actually observed. Independent QA remains separate. Newer author revisions are not substituted for independently qualified originals. No new target, companion, firmware or physical claim.
