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

## Persistent host performance fixture (27 Nov 2026)
The original render/phrase audition and all core APIs remain unchanged. Build `gcc -std=c11 -O2 -Wall -Wextra -Werror -shared -fPIC xeno.c live_bridge.c -o live.dll` and launch `python live.py ./live.dll` (Windows: `python live.py live.dll`). Open the printed 127.0.0.1 URL, start audio, hold/release Strike, use the XY surface and material/coupling controls, and use Panic to stop. 50 ms actual-core PCM blocks with six sampled modal magnitude peaks; the visualization is local, not device telemetry. Eight-event browser queue, local audio cancellation, session token, strict sequence, 1.5 s inactivity lease, range/profile checks. Python 3 required. Run `python test_live.py ./live.dll` for the actual HTTP and direct bridge tests. Local GCC/UBSan PASS: deterministic persistent PCM, mid-decay damping, body B zero for uncoupled and nonzero for coupled, release, exact direct panic PCM and modal silence, stale sequence/token, profile mismatch, lease expiry. Browser JS syntax checked with Node; browser playback not executed. Author predecessor CI 46039808732 passed Windows/Linux; new hosted results pending. The pinned core used by companion #15 is unchanged; its target compile is separate from failed USB virtual enumeration. No physical/transport qualification or flash distribution.

## Factory performance patches (native audition)
Six factory patches supplement the four core material models: Ceramic chime/click, Woodglass pluck, Alien bell/scrape and Membrane pulse. The local browser applies the four macro controls together on the next audio block, preserves pitch/velocity and does not synthesize a new strike/reset. Normal focus-loss release remains active; manual material/XY/coupling edits mark the patch Custom. Patch definitions are embedded in live.html and read directly by the offline native gallery, not a new wire format. From a built live library run `python patch_gallery.py ./live.dll "patch gallery"` (Linux .so also supported). Six matched four-note phrases and two single-strike causal comparison WAVs, each 4s at 24kHz, plus 50ms native state and PCM receipts. Local GCC UBSan and Clang fresh native builds generated byte-identical gallery/receipt, SHA-256 aa676b6c7996913728bb0859713a96b56f61c3f7a17159460fb11d8fff12f66c. This is native evidence only; new hosted Chromium/Windows runs pending, not physical/MIDI/device telemetry. Previous keyboard hosted CI 46075255510 passed all three jobs including Chromium 15 pitch/PCM witnesses. No core/ABI or transport changes.

## Hands-on performance keys (native audition)
With Hold to strike focused and audio active, use the top-row 1–6 to recall the six patches while a chromatic note is held; left/right changes excitation, down/up changes damping, and [ / ] changes coupling in bounded steps of four. Arrow/bracket auto-repeat is allowed; patch auto-repeat is ignored. No added note events, reset, session changes or device protocol; existing focus-loss and panic behavior remains. Previous exact 5804ebb6 author CI 46081547516 and independent QA successor matrix 46085052942 passed; new keyboard controls require their own browser regression.

## User material exchange (native audition)
Capture the current material/excitation/damping/coupling into a single local slot or import a `xenoresonator.material/1` JSON document (maximum 256 characters; exactly schema, p, e, d, c; integer ranges 0–3 for p and 0–127 for macros). Import does not change sounding controls. Explicit Recall or top-row 7 while Hold to strike is focused applies the slot without retriggering, resetting, changing pitch/velocity or introducing a device message. Invalid input preserves the existing slot. Copy the document externally for reuse; the slot is page-local and not persistent across reloads. Panic and reconnect never recall it automatically. This is a provisional local authoring document, not a wire format. Factory patches and the core remain unchanged.

## Held material recall score (native offline companion fixture)
Run `python user_material_replay.py ./live.dll "user material replay"`. Three matched 7-second PCM recordings compare fixed Alien metal, recalled macros only, and full user material recall across four authored slots; each arm has 16 strikes, 12 releases, 12 recall cues, 12 manual XY cues and four active-sound panic commands. The score drives the actual native bridge, not the browser or a device. Held recall generates no strike. The same-material slot is a negative control for material identity; the other three isolate the effect of material changes from macros. Each of 420 block receipts contains controls, authored held state, sampled native modal peaks, PCM peak/RMS and SHA256. The final second is exactly silent; all four active panic commands are checked. Local exact-source GCC and Clang UBSan builds reproduced all three WAVs and the receipt byte-for-byte (receipt SHA256 c974de400e78af12aeef9dd511f890e3fb5cc28bdebcd4ae1d2a6bda126dbb1d; peak 6621). The preceding user slot evaluator c5df5924 passed author CI 46097348622 (including Chromium) and independent matrix 46100339386 on Windows/Linux. New replay host CI and independent rebuild pending. No new target, physical, MIDI or enhanced transport evidence; local authoring documents and native modal observations only.

## A/B material performance morph (native audition)
The existing user material slot is endpoint A. Capture or import an independent endpoint B using the same bounded local material document. Neither action applies sounding controls. With both endpoints present, the explicit 0–127 morph slider (or 8/9 keys in steps of eight while Hold to strike is focused) interpolates excitation, damping and coupling using integer nearest rounding; material A is selected below 64, B at 64 and above. This is a control-space morph, not continuous interpolation of resonator coefficients. It never emits note events or modifies pitch/velocity, seed, session or native core. The displayed position is the last request, not observed device state; manual edits may supersede it. Panic/reconnect do not automatically recall either endpoint. Both endpoints are page-local, documents can be copied externally. No new wire protocol or transport claim. Actual Chromium/native regression covers independent imports, invalid B rejection, 56/64 midpoint transitions with held note, and no extra note events; new hosted execution pending.

## A/B morph performance score (offline native witness)
Run `python material_morph_replay.py ./live.dll "material morph replay"` with Python 3 and Node available; Linux .so also supported. Three two-second phrases use separately reset seeds, matched notes and forward/reverse morphs; each arm adds one second of silence. Four arms: fixed A, macro interpolation with material A fixed, full control-space morph, and abrupt endpoint switch. The third pair uses the same material for both endpoints (negative control). The exact page applyMorph function is executed with minimal DOM stubs for all 384 pair/position combinations; actual native PCM is driven by the matched integer controls. Each of 560 block receipts carries position, controls, authored held state, six native sampled modal levels, peak/RMS and PCM hash. Six non-silent held midpoint comparisons, pre-midpoint identity, same-material control, 18 strikes and 15 releases per arm, three nonvacuous panics per arm and exact tail silence. Local GCC UBSan and Clang UBSan trap builds reproduced all four WAVs and receipt byte-for-byte; receipt SHA256 2418c5fc5b6c940d87d2f8964ad63463c452c3fded5094eb17fde72b78ff53b7. Predecessor author 46106395544 (Chromium included) and QA 46109623584 independently passed; new hosted replay pending. Local source/score only, no device telemetry, transport, core or target ABI changes.

### Optional native A/B material memory

`material_memory.h` exposes a caller-owned C11 local semantic controller: initialize,
store/capture slots A and B, recall, or morph using positions 0–127. Both slots
must be valid for morph. Macro rounding matches the browser, while material
selection changes discretely at 64. Capture and import do not alter sounding
state. Recall/morph preserve gate, note, RNG, burst and resonator history;
the caller controls actual note/panic/reset and committed-block scheduling.
Slots persist across an engine reset until the caller initializes the controller.
Only the validated public operations are intended for callers; internal mix/apply
helpers require valid arguments. No allocation, session or transport ABI is
introduced. Use in a C11 translation unit with a single owner at audio-block
boundaries; shared endpoint/companion integration remains separately owned.

Local verification: compile `gcc -std=c11 -O2 -Wall -Wextra -Werror -fsanitize=undefined -fno-sanitize-recover=all xeno.c test_material_memory.c -o memory-test`
then execute `./memory-test`. Tests compare every 7-bit endpoint/position
combination with an independent signed-delta formula, exercise all sixteen
ordered material pairs and compare actual core PCM and state with direct controls.
Invalid requests are rejected without mutation. This is a host semantic fixture,
not target execution, negotiated MIDI support or device telemetry.

### Native local material-memory HTTP controls

The same `live.py` loopback session now exposes native A/B memory to local
controllers. Open with `POST /open` and `{ "version": 1 }`; use the returned
`token` and the same monotonically increasing `seq` as `/block` (starting at
zero). Send JSON to `/memory` with `op` equal to `inspect`, `clear`,
`capture` (integer `slot` 0 or 1), or `store` (`slot`, `p`, `e`, `d`, `c`).
These commands return actual native `slots` (null for empty) and current
`patch`, without rendering or applying a stored patch. Send `/memory-block`
with `op: recall` and `slot`, or `op: morph` and integer `position` 0–127.
These commands render exactly one 50 ms block and return `pcm`, `levels`,
`patch` and `seq`; no implicit strike or release. For note events use the
existing `/block` with the returned current patch and desired note/velocity.
All successful memory commands consume one sequence number; failed requests
consume none. Serialize them with audio blocks. Panic/expiry invalidate the
session; stored patches survive reset/reopen, but are never automatically
applied. This is an explicitly local, single-owner fixture, not a shared
transport or device telemetry. The existing browser still uses its page-local
memory; migration to these native operations is a separate follow-up.

`test_live.py` covers all sixteen ordered material pairs, actual PCM/modal
identity against direct controls, slot readback, invalid/stale commands and
silent reconnects. This is host-only qualification; target and physical gates
are unchanged.
