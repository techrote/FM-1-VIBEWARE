# CYDaux instrument-side USB endpoint — Draft / HOLD

This coordinated PLATFORM/CYDAUX integration extends the existing #13 raw-XIP
experiment, without changing the active creative branches. It connects the real
Xenoresonator core from #12, exact `fa27a317bb116f2afb62a710876f96314756f814`,
to the shared FM-1-CYDaux CY1 protocol. The endpoint retains standalone note keys,
material selection, damping and HOME panic. It requires no CYD to make sound.

The target links successfully, and actual USB control and audio have passed
local instruction-clock and strict timing-model emulation. The reproducible
local receipt is [qualification.json](qualification.json); it identifies the
tested source contents and distinguishes the complete manual qualification
from the locally incomplete workflow (system Clang was unavailable). Fresh
hosted workflow results, exact pins, logs, WAVs and hashes belong in its artifact.
Do not infer hosted PASS from a submitted job. Physical FM-1 and CYD execution
have not been performed. This is not an installable firmware release.

## Implemented path

`cyd_endpoint.c` is bounded freestanding C with no allocator or I/O. It accepts
the same version 1.0, 28-bit-session, 14-bit-sequence SysEx frames as the common
CYD controller. Identity 2 is Xenoresonator. Parameter controls are excitation,
damping, coupling and material; presets reset the actual engine; notes strike
and release; panic mutes. State snapshots expose actual applied parameters,
gate, six mode magnitude proxies, and a separate PCM peak. Material values use
the shared normalized 0..127 domain. The default native/profile semantics are
checked through the independently authored C++ `CompanionSession` codec, not
by writing a second mock client that only agrees with its own implementation.

The endpoint rejects wrong version, identity, session, sequence, length, byte
range, parameter and note range. One session remains fixed until disconnect or
the 1.5-second receive lease expires. Expiry publishes panic and retires the
session. Every accepted fresh command refreshes the lease; unknown, malformed
or replayed discovery traffic does not. A repeated discovery can resend a lost
identity without advancing the mutation sequence. Reads/telemetry coalesce to the newest accepted command;
mutations are never automatically replayed. Refused mutations consume their
sequence, matching the native endpoint.

`xeno_app.c` links the unchanged core to pinned Dinghy. The main loop owns USB,
protocol and desired control state. The audio ISR alone owns the engine and
24 kHz → 44.1 kHz 80/147 rate bridge inherited from PLATFORM. Main publishes
one bounded command copy; the ISR publishes one bounded observed-state copy.
Snapshots wait through later main-loop iterations until the ISR has actually
applied the requested version. There is no waiting, USB call, allocation or
message parsing in the audio ISR. Actual PCM and sampled modal peaks are held
since the previous successfully constructed state snapshot, and kept separate.
The PCM meter measures the instrument callback before the platform MASTER
attenuation and I2S packing; it is not an analog output measurement.
The audio ISR alone owns these accumulators; a main-loop acknowledgement marks
the next interval. No artificial decay or inferred envelope is reported. The
LCD redraws only when its displayed material changes. Panic has its own monotonic
counter so a subsequent note cannot erase its mute before the next audio block.
Desired controls and note state are applied at the 256-frame block boundary;
updates arriving within one block can coalesce. This adapter does not claim
sample-accurate note scheduling. Its supported touchscreen sequencer timing is
much slower than a block; a future event FIFO belongs in a separate, qualified
instrument-host change.
Instrument-side callbacks and fixed compiler runtime
division overhead must be assessed from target/emulator measurements; host
execution timing does not establish physical audio deadline headroom.

USB replies use a capacity preflight and one fixed pending reply. They never
call the platform's potentially blocking 500 ms `ota_wire_send`. The existing
OTA parser otherwise consumes every assembled SysEx; `prepare_platform.py`
applies a reviewed four-line namespace deferral in a temporary pinned checkout,
only outside recovery mode. No upstream repository is changed. Rescue/update
messages retain their existing handling. The TRS MIDI parser drops SysEx and
is **not** advertised as an enhanced-control route. Unmodified Fune also drops
SysEx and does not acquire these capabilities by installing a profile.

## Reproduce

On an Ubuntu build host with C/C++, Python, Rust/Cargo, curl, git and xz:

```sh
CYDAUX_REF=7a8ce4be817ccc85ae22f982df98baa701b8176a bash platform/companion/ci.sh
```

The workflow checks out exact original engine, companion codec, Dinghy and
fm1-emu revisions; hash-checks the pi32v2 compiler archive; runs C/C++
interoperability plus original 64-bit arithmetic tests under sanitizers;
compiles and links the actual target; checks undefined symbols and the ELF/XIP
mapping; and runs the firmware under an independent Rust harness using the
unmodified emulator's CPU, SoC and USB host model.

The harness injects USB-MIDI into the emulated USB controller. It obtains real
identity/state replies from firmware instructions, then checks control and
preset semantics, PCM repeatability, coupling contrast, session/range rejection,
panic silence, lease expiry and reconnect. Both instruction-clock/JIT and
strict timing-model executions are requested. The strict clock models selected
hardware costs; it remains emulation, not physical timing evidence.

Artifacts contain source pins and tree, compiler version, map/size/symbols, USB logs,
actual emulated PCM and LCD framebuffer, target counters, stack canary high-water
measurements and SHA-256 hashes. The stack probe initializes only the two pinned
linker stack areas before emulated boot; it is an emulation measurement. No ELF, raw XIP,
installer, loader or emulator executable is uploaded. Distribution and physical
installation remain under the existing board, format, rights and recovery gates.

## Ownership and next integration

Common CYD firmware, UI, simulator and protocol belong in FM-1-CYDaux. This
directory is a concrete instrument-side PLATFORM seam, coordinated through #2
and #9. The original Xenoresonator author continues owning its engine and musical
semantics. Future consumers should first adapt callbacks and exercise the common
codec, before assigning a new numeric identity or claiming route support. This
does not replace Grimoire's existing standalone raw-XIP target or claim completed
Chronomorph/Ecophon/MHAC integrations.

New adapter/test/runtime-helper code declares MIT in its files. Dinghy remains
GPL-3.0-only, fm1-emu MIT, and the original VIBEWARE project-wide licensing
decision remains as recorded by PLATFORM. Temporary linking for the authorized
experiment is not a grant to distribute an installation package.
