# FM-1 VIBEWARE

**An experimental musical instrument and firmware laboratory for the M-VAVE FM-1.**

VIBEWARE develops distinct playable instruments: alternative synthesis engines, generative composition systems, cybernetic instruments, experimental firmware and hybrid FM-1/CYD performance systems. Musical identity and working delivery take precedence over accumulating prototypes or speculative architecture.

## Start here

- [Project architecture and implementation routes](docs/ARCHITECTURE.md)
- [Worker roster and operating protocol](AGENTS.md)
- [Specialist worker mandates and schedule configurations](docs/WORKERS.md)
- [Qualification and delivery contract](docs/QUALIFICATION.md)
- [Instrument catalogue and initial backlog](docs/CATALOGUE.md)
- [GitHub issues](https://github.com/techrote/FM-1-VIBEWARE/issues)

## Reference lineage (read-only)

| Reference | Use |
|---|---|
| [FM-1-MHAC](https://github.com/techrote/FM-1-MHAC) | Portable integer DSP, alternative firmware/toolchain integration and [emulator qualification #8](https://github.com/techrote/FM-1-MHAC/pull/8). |
| [ZaaggenZ-FM1](https://github.com/techrote/ZaaggenZ-FM1) | [Fune plugin, portable engine, audition and packaging #1](https://github.com/techrote/ZaaggenZ-FM1/pull/1). |
| [FM-1-CYDaux](https://github.com/techrote/FM-1-CYDaux) | [Touch controls, profile negotiation, MIDI and transport architecture #1](https://github.com/techrote/FM-1-CYDaux/pull/1). |
| [cyd-diviner](https://github.com/techrote/cyd-diviner) | Modular rites, synthesis, procedural visual design, embedded memory discipline and [CYD integration #6](https://github.com/techrote/cyd-diviner/pull/6). |
| [fm1-emu](https://github.com/joakimeriksson/fm1-emu) | Virtual FM-1 execution and debugging; exact supported execution paths must be independently verified. |
| [Fune](https://github.com/hugelton/Fune), [FM-1-RE](https://github.com/AL-255/FM-1-RE) | Plugin/firmware architecture and hardware research; inspect actual versions and reuse terms before adoption. |

These projects remain independent. No writes to their repositories are authorized by a VIBEWARE worker. Reference PRs are discovery pointers, not automatically accepted dependencies; pin reviewed source revisions and retain provenance and notices before using code.

## Delivery model

Develop portable, bounded audio engines; select the appropriate FM-1 plugin, custom firmware or hybrid adapter; provide real audio renders and interactive audition; independently qualify exact builds; package for owner review. The FM-1 is the primary musical target. CYD and desktop hosts complement it, not substitute for FM-1 execution.

**Current state: programme bootstrap only.** No synthesis engine, target binary, emulator run or hardware qualification has yet been produced in this repository. No firmware is approved for installation. Physical board identity, supported recovery, format/rights and owner acceptance are separate gates; no automated flashing.

No project-wide license is asserted yet. Owner must decide licensing for new work and any combined distribution. Independently verify all third-party terms, including source and notices obligations, before incorporating or distributing third-party material.
