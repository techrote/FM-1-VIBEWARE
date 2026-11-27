# Grimoire — Orbit Gate (first rite)

Original portable fixed-point 24 kHz monophonic gesture instrument. Three phase-coupled triangular oscillators, satellite phase modulation, a bounded low-pass stage and gate envelope give three distinct material regimes (Amber, Iron, Abyss). X selects one of 24 chromatic carrier pitches; Y changes phase perturbation and filter response. Standalone core API requires no companion. The native virtual companion renders actual core PCM and displays actual oscillator phase/energy, not simulated telemetry. Pointer release decays the gate; Panic silences immediately. Local session rejects stale generations and invalid version/events. This is not a wire protocol; no actual CYD firmware or FM-1 target exists yet.

## Build and audition

From repo root (Linux gcc; Windows MinGW gcc, use orbit.dll instead of orbit.so and omit -fPIC):

    gcc -std=c11 -O2 -Wall -Wextra -Werror -fPIC -shared instruments/grimoire/orbit.c companion/grimoire/session.c -o orbit.so
    python companion/grimoire/host.py orbit.so

Open http://127.0.0.1:8765 in a browser, click Start audio, then drag in the pad. The host is local-only and one current session is supported. Browser PCM scheduling is a virtual demonstration; no latency guarantees or hardware claim. CI builds three six-second actual-core WAV demos and tests extracted companion files. The local API has no asynchronous device queue; no production transport claim. The instrument-local fixture coalesces adjacent XY events, preserves gate edges, caps pending events at 16, panics on overflow and cancels scheduled browser audio on panic/blur. The local host expires inactive sessions after 1.5 s, rejects stale generations, and does not refresh the lease on invalid events. A blocked HTTP handler can delay expiry (1 s socket timeout); these are simulator safeguards, not physical real-time guarantees. See companion/grimoire/profile.json for the provisional semantic profile (intended enhanced or basic MIDI fallback; neither device route verified). No common CYD firmware or wire format is implemented.

## Qualification boundary

Host CI and hashes: see exact PR run. Target build, actual FM-1 emulator execution, CYD target build, physical link and independent package review are pending. Consume PLATFORM #2's shared emulator pathway; no competing harness. Proposed panel mapping: note/press gate, pitch keys or encoder X, knob Y, preset selection, HOME panic; actual adapter must use verified host controls. Companion profile is provisional and local only, not a frozen device protocol. FM-1-CYDaux #1 (6540bac817c78618f2d3a666e70d684b7f6216a9) and cyd-diviner main (7b1b37eec6ac126f334a0b008d91135071ea60fa) are architectural inspiration, not imported code. MHAC #8 cc132a43b27c1d9f23bf50bca224567af49e208e and fm1-emu 736aded65c8e2e9d652cf595fca248734483a877 are shared platform references only. No third-party source copied, no flash artifacts or physical claims.
