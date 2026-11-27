# Xenoresonator — SYNTH-001 (#3)

Original C11 six-mode (two bodies, three modes each) virtual material instrument, 24 kHz mono prototype. No upstream code copied; tables and core authored for this experiment. No repository-wide distribution license asserted. One voice, pitched percussion; excitation is a deterministic nonlinear contact burst into body A, coupled to body B by symmetric convex mixing. Damped Q15 complex rotation, explicit state bounds, no render-time allocation. Four materials: Ceramic, Woodglass, Alien metal and Membrane. Coupling zero is a causal comparator; the second body remains unexcited after reset in that case. This is a simplified modal instrument, not a calibrated physical material simulation.

## Host
From this directory: `gcc -std=c11 -O2 -Wall -Wextra -Werror xeno.c render.c -o render` (Windows: render.exe); `gcc -std=c11 -O2 -Wall -Wextra -Werror xeno.c test.c -o test`; run test. Launch `python audition.py ./render` (Windows: `python audition.py render.exe`), open localhost:8765. Select material, set excitation, damping, coupling, pitch and velocity, click Strike or Play phrase. Controls affect the next strike, not continuous streaming; Stop cancels browser playback. Python 3 required. HTTP integration test: `python test_http.py ./render`. The browser itself and real audio playback have not been tested. CLI: `./render output.wav 2 76 12 90 48 110 phrase` (optional phrase gives six seconds rather than two). Preset material parameters are in xeno.c; authored phrase notes 0,7,12,3,10,0 semitones. Audition intentionally sets damping 12 and coupling 90; core reset defaults are 38 and 48.

## Local semantic handoff
xeno_reset(seed,material), xeno_material, xeno_controls(excitation,damping,coupling), xeno_strike(note,velocity), xeno_release, xeno_panic, xeno_render, xeno_mode_level. Suggested panel: note/velocity, encoder material, macro excitation/damping, coupling page, HOME panic. Proposed only, actual panel capabilities must be verified by PLATFORM #2. The provisional profile is not a wire protocol. XY excitation/damping and six local modal level proxies are intended companion semantics; no CYD firmware or verified MIDI/telemetry. Standalone local core is independent. Actual FM-1 adapter awaits the shared pinned emulator contract; 24k rate is a host choice, not asserted target capability.

## Local evidence (27 Nov 2026)
GCC and Clang C11 -O2 -Wall -Wextra -Werror with UBSan passed four presets, whole vs partitioned PCM and state identity, uncoupled body-B zero witness versus coupled nonzero, release and exact panic silence, 1,280,000 stress samples (peak 8011/32768, 88 bytes state on host). HTTP localhost actual-core tests pass repeatable WAV, coupling intervention and four invalid queries. Five six-second actual-core renders (24k mono PCM16) are distinct; peaks 5922–5937. No subjective listening claim. PCM SHA-256 for material 0/1/2/3 and uncoupled material 2 respectively:
- 96860d46e628c97077e3637be1a45e960947f1107ca4477adeda97753409c536
- 2e1595db10fe3cb56e369b3cc8cbcdce6bc25abc1dea45446f902c3eb66688b7
- 48320d653747340e5d06679f0779bef6bf6710c3de018b9b6da1ffdf1433f179
- 29a165af6d00103a7cb3159116eb2fee8f288aff4a410c3afbfba17e9755b200
- bb1f35b94efb048f748a40f61c03926f95ed05a4618d812ea3cbe58dd6bfb132

Host evidence only. No target build, emulator, hardware, transport, extracted package or independent QA PASS claimed. No raw XIP, flash image or installation package. Next: shared PLATFORM adapter, live controls and local resonance visualization, independent QA. Physical HOLD.
