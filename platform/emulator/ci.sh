#!/usr/bin/env bash
set -euo pipefail
export LC_ALL=C
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HERE="$ROOT/platform/emulator"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
RES="$ROOT/platform-results"
mkdir "$RES"
DINGHY=92f17b28f2d05f2f78fd1b160b58475d518902c8
MHAC=cc132a43b27c1d9f23bf50bca224567af49e208e
EMU=736aded65c8e2e9d652cf595fca248734483a877
CORE=03102e8d82148a6dba871024f5944246e0c913e2
ECO=acdc41839665271372cd69df1d09f5550556c87e
TC_SHA=cb896562418a2be93edb9bac26af4bc81a106a32974002a78e6b9fc203c93990
checkout() {
  git init -q "$2"
  git -C "$2" remote add origin "$1"
  git -C "$2" fetch --depth=1 origin "$3"
  git -C "$2" checkout --detach FETCH_HEAD
  test "$(git -C "$2" rev-parse HEAD)" = "$3"
}
for cc in gcc clang; do
  "$cc" -std=c11 -Wall -Wextra -Werror -fsanitize=undefined -fno-sanitize-recover=all -O2 "$HERE/test_rate.c" -o "$TMP/rate"
  "$TMP/rate" | tee "$RES/rate-$cc.txt"
done
python3 "$HERE/test_elf.py" 2>&1 | tee "$RES/elf-tests.txt"
checkout https://github.com/zvenson/dinghy.git "$TMP/dinghy" "$DINGHY"
checkout https://github.com/techrote/FM-1-MHAC.git "$TMP/mhac" "$MHAC"
checkout https://github.com/techrote/FM-1-VIBEWARE.git "$TMP/core" "$CORE"
checkout https://github.com/joakimeriksson/fm1-emu.git "$TMP/emu" "$EMU"
printf 'platform=%s\ndinghy=%s\nmhac=%s\nemu=%s\ncore=%s\ntoolchain_archive_sha256=%s\n' "$(git -C "$ROOT" rev-parse HEAD)" "$DINGHY" "$MHAC" "$EMU" "$CORE" "$TC_SHA" > "$RES/pins.txt"
curl -fL --retry 2 --max-time 180 -o "$TMP/tc.tar.xz" https://github.com/jvitkauskas/pi32v2-llvm/releases/download/pi32v2-23.1.5-2/pi32v2-llvm-23.1.5-2-linux-x64.tar.xz
printf '%s  %s\n' "$TC_SHA" "$TMP/tc.tar.xz" | sha256sum -c -
mkdir "$TMP/tc" "$TMP/source"
tar -xJf "$TMP/tc.tar.xz" -C "$TMP/tc" --strip-components=1
TC="$TMP/tc/bin"
"$TC/clang" --version | tee "$RES/compiler.txt"
# Reproduce reference in its own checkout with its existing tools. No copying into VIBEWARE.
(
 cd "$TMP/mhac/experiments/scope-weave-005"
 sh qualify_target.sh "$TMP/dinghy" "$TMP/tc.tar.xz" "$TMP/scope"
 sh qualify_link.sh "$TMP/dinghy" "$TMP/tc.tar.xz" "$TMP/scope"
) > "$RES/reference-build.txt" 2>&1
python3 "$TMP/mhac/emulator-qualification-001/elf_to_xip.py" "$TMP/scope/candidate.elf" "$TMP/reference.xip.bin" | tee "$RES/reference-xip.json"
python3 "$HERE/elf_xip.py" "$TMP/scope/candidate.elf" "$TMP/reference-new.xip.bin" | tee "$RES/reference-converter.json"
cmp "$TMP/reference.xip.bin" "$TMP/reference-new.xip.bin"
# Original instrument is fetched at its exact candidate head, not vendored or changed.
git -C "$TMP/dinghy" archive "$DINGHY" | tar -x -C "$TMP/source"
cd "$TMP/source"
ORBIT="$TMP/core/instruments/grimoire"
cp "$HERE/grimoire_app.c" firmware/src/dinghy.c
"$TC/clang" -target pi32v2 -mcpu=ac791n -Os -ffunction-sections -fno-builtin -Wall -Wno-unused-function -Ifirmware/hal -Ifirmware/src -Ifirmware/gen -I"$ORBIT" -I"$HERE" -DAPP_VER='"dev"' -DFELUCCA_ID='"FM-1_990"' -c firmware/src/dinghy.c -o "$TMP/app.o"
"$TC/clang" -target pi32v2 -mcpu=ac791n -Os -ffreestanding -fno-builtin -ffunction-sections -I"$HERE/include" -Wall -Wextra -Werror -c "$ORBIT/orbit.c" -o "$TMP/orbit.o"
for src in firmware/crt0.S firmware/hal/fm1_vec.S firmware/hal/fm1_isr.S; do
  "$TC/clang" -target pi32v2 -mcpu=ac791n -c "$src" -o "$TMP/$(basename "$src" .S).o"
done
"$TC/ld.lld" --gc-sections -e _start -T firmware/app.ld -Map="$RES/grimoire.map" "$TMP/crt0.o" "$TMP/fm1_vec.o" "$TMP/fm1_isr.o" "$TMP/app.o" "$TMP/orbit.o" -o "$TMP/grimoire.elf"
"$TC/llvm-readelf" -h -l "$TMP/grimoire.elf" | tee "$RES/grimoire-elf.txt"
"$TC/llvm-size" -A "$TMP/grimoire.elf" | tee "$RES/grimoire-size.txt"
test -z "$("$TC/llvm-nm" -u "$TMP/grimoire.elf")"
python3 "$HERE/elf_xip.py" "$TMP/grimoire.elf" "$TMP/grimoire.xip.bin" | tee "$RES/grimoire-xip.json"
rustup toolchain install 1.95.0 --profile minimal
rustup run 1.95.0 cargo build --release --locked -p fm1-emu --manifest-path "$TMP/emu/Cargo.toml"
EXE="$TMP/emu/target/release/fm1-emu"
run_case() {
  local image="$1" name="$2" part="$3" note="$4"
  local keys="${5:-600-700:N$note,900-1000:PLAY,3600-3700:HOME}"
  local dir="$TMP/run-$name"
  local -a snapshots=()
  case "$name" in
    eco-*|chrono-*) snapshots=(--snap 1200,2400) ;;
  esac
  mkdir -p "$dir/work"
  (
    cd "$dir"
    FM1_LCD_TIMED=1 timeout 300 "$EXE" --bin "$image" --entry 0x02000120 --ms 4500 --keys "$keys" --flash-chip "$part" --wav "$RES/$name.wav" "${snapshots[@]}" --quiet
  ) > "$RES/$name.log" 2>&1
  python3 "$TMP/mhac/emulator-qualification-001/analyze_wav.py" "$RES/$name.wav" --require-audio --silent-tail-ms 500 | tee "$RES/$name.json"
  # Ensure a substantial capture, not a truncated file that happens to end in silence.
  python3 -c 'import sys,wave; w=wave.open(sys.argv[1]); assert w.getnframes() >= 44100*4' "$RES/$name.wav"
  if (( ${#snapshots[@]} )); then
    for ms in 1200 2400; do
      test -s "$dir/work/lcd_$ms.bmp"
      cp "$dir/work/lcd_$ms.bmp" "$RES/$name-lcd-$ms.bmp"
    done
  fi
}
# Interventions occur at 1700ms emulator time, during active playback. The
# capture starts after initialization; these deliberately separated windows
# use the measured prior ~0.42s capture offset, not wall-clock time.
live_contrast() {
  python3 - "$RES/$1.wav" "$RES/$2.wav" <<'PY'
import json, sys, wave
with wave.open(sys.argv[1], 'rb') as a, wave.open(sys.argv[2], 'rb') as b:
    assert (a.getnchannels(),a.getsampwidth(),a.getframerate(),a.getnframes()) == (b.getnchannels(),b.getsampwidth(),b.getframerate(),b.getnframes())
    assert a.getnchannels()==2 and a.getsampwidth()==2 and a.getframerate()==44100
    prefix_a,prefix_b=a.readframes(44100),b.readframes(44100)
    assert prefix_a==prefix_b and any(prefix_a), 'pre-intervention active PCM mismatch or silence'
    a.setpos(92610); b.setpos(92610)
    post_a,post_b=a.readframes(39690),b.readframes(39690)
    assert len(post_a)==len(post_b)==39690*4 and post_a!=post_b, 'post-intervention PCM aliased'
    print(json.dumps(dict(baseline=sys.argv[1], intervention=sys.argv[2], prefix_frames=44100, post_start_frame=92610, post_frames=39690, changed_stereo_frames=sum(post_a[i:i+4]!=post_b[i:i+4] for i in range(0,len(post_a),4)))))
PY
}
run_case "$TMP/reference.xip.bin" scope-reference p25q80 3
printf '%s  %s\n' 7bc82e8e554a31635f830358ac01539fad08796b7636af85521fbdfe5437104b "$RES/scope-reference.wav" | sha256sum -c -
run_case "$TMP/grimoire.xip.bin" orbit-n3 p25q80 3
run_case "$TMP/grimoire.xip.bin" orbit-n3-repeat p25q80 3
run_case "$TMP/grimoire.xip.bin" orbit-n9 p25q80 9
run_case "$TMP/grimoire.xip.bin" orbit-n3-uc25 uc25hq80 3
cmp "$RES/orbit-n3.wav" "$RES/orbit-n3-repeat.wav"
cmp "$RES/orbit-n3.wav" "$RES/orbit-n3-uc25.wav"
if cmp -s "$RES/orbit-n3.wav" "$RES/orbit-n9.wav"; then
  echo "FAIL: distinct panel pitch commands aliased" >&2; exit 1
fi
echo "actual reference control + Grimoire PCM repeat, alternate flash model, pitch contrast and HOME tail PASS" | tee "$RES/result.txt"
# No executable or raw XIP uploads until combined distribution rights are resolved.
# Isolated #16 experiment; existing uninstrumented target evidence remains unchanged.
source "$HERE/rate_target_probe.sh"


# Each downstream target runs in a strict subshell; a failure cannot suppress
# the other target's evidence. The parent still fails if either fails.
run_ecophon() (
trap - EXIT
set -e
# Second consumer; retain all first-consumer and reference gates above.
checkout https://github.com/techrote/FM-1-VIBEWARE.git "$TMP/eco-core" "$ECO"
ENGINE="$TMP/eco-core/instruments/ecophon"
printf 'ecophon_core=%s\n' "$ECO" >> "$RES/pins.txt"
for cc in gcc clang; do
  "$cc" -std=c11 -Wall -Wextra -Werror -fsanitize=undefined -fno-sanitize-recover=all -O2 -I"$ENGINE" "$HERE/test_ecophon_runtime.c" "$ENGINE/ecophon.c" -o "$TMP/test-eco"
  "$TMP/test-eco" | tee "$RES/ecophon-adapter-$cc.txt"
done
cp "$HERE/ecophon_app.c" firmware/src/dinghy.c
"$TC/clang" -target pi32v2 -mcpu=ac791n -Os -ffunction-sections -fno-builtin -Wall -Wno-unused-function -Ifirmware/hal -Ifirmware/src -Ifirmware/gen -I"$ENGINE" -I"$HERE" -DAPP_VER='"dev"' -DFELUCCA_ID='"FM-1_990"' -c firmware/src/dinghy.c -o "$TMP/eco-app.o"
"$TC/clang" -target pi32v2 -mcpu=ac791n -Os -ffreestanding -fno-builtin -ffunction-sections -I"$HERE/include" -Wall -Wextra -Werror -c "$ENGINE/ecophon.c" -o "$TMP/eco.o"
"$TC/ld.lld" --gc-sections -e _start -T firmware/app.ld -Map="$RES/ecophon.map" "$TMP/crt0.o" "$TMP/fm1_vec.o" "$TMP/fm1_isr.o" "$TMP/eco-app.o" "$TMP/eco.o" -o "$TMP/ecophon.elf"
"$TC/llvm-readelf" -h -l "$TMP/ecophon.elf" | tee "$RES/ecophon-elf.txt"
"$TC/llvm-size" -A "$TMP/ecophon.elf" | tee "$RES/ecophon-size.txt"
test -z "$("$TC/llvm-nm" -u "$TMP/ecophon.elf")"
python3 "$HERE/elf_xip.py" "$TMP/ecophon.elf" "$TMP/ecophon.xip.bin" | tee "$RES/ecophon-xip.json"
run_case "$TMP/ecophon.xip.bin" eco-low p25q80 3
run_case "$TMP/ecophon.xip.bin" eco-low-repeat p25q80 3
run_case "$TMP/ecophon.xip.bin" eco-high p25q80 24
run_case "$TMP/ecophon.xip.bin" eco-scarcity p25q80 3 "600-700:N3,900-1000:PLAY,1700-1900:SCL,3600-3700:HOME"
run_case "$TMP/ecophon.xip.bin" eco-scarcity-repeat p25q80 3 "600-700:N3,900-1000:PLAY,1700-1900:SCL,3600-3700:HOME"
cmp "$RES/eco-scarcity.wav" "$RES/eco-scarcity-repeat.wav"
live_contrast eco-low eco-scarcity | tee "$RES/eco-preset-intervention.json"
cmp "$RES/eco-low.wav" "$RES/eco-low-repeat.wav"
for other in eco-high eco-scarcity; do
  if cmp -s "$RES/eco-low.wav" "$RES/$other.wav"; then
    echo "FAIL: Ecophon panel control aliased: $other" >&2; exit 1
  fi
done
echo "Ecophon actual target PCM repeat, pressure and preset contrast, HOME tail PASS" | tee "$RES/ecophon-result.txt"

)

run_chronomorph() (
trap - EXIT
set -e
# Third consumer. Preserve all gates while collecting independent evidence.
CHRONO=be57d9f77e9325271adbd4558dfd554c6cd81e19
checkout https://github.com/techrote/FM-1-VIBEWARE.git "$TMP/chrono-core" "$CHRONO"
ENGINE="$TMP/chrono-core/instruments/chronomorph"
printf 'chronomorph_core=%s\n' "$CHRONO" >> "$RES/pins.txt"
for cc in gcc clang; do
  "$cc" -std=c11 -Wall -Wextra -Werror -fsanitize=undefined -fno-sanitize-recover=all -O2 -I"$ENGINE" "$HERE/test_chrono_runtime.c" "$ENGINE/chrono.c" -o "$TMP/test-chrono"
  "$TMP/test-chrono" | tee "$RES/chronomorph-adapter-$cc.txt"
done
cp "$HERE/chrono_app.c" firmware/src/dinghy.c
"$TC/clang" -target pi32v2 -mcpu=ac791n -Os -ffunction-sections -fno-builtin -Wall -Wno-unused-function -Ifirmware/hal -Ifirmware/src -Ifirmware/gen -I"$ENGINE" -I"$HERE" -DAPP_VER='"dev"' -DFELUCCA_ID='"FM-1_990"' -c firmware/src/dinghy.c -o "$TMP/chrono-app.o"
"$TC/clang" -target pi32v2 -mcpu=ac791n -Os -ffreestanding -fno-builtin -ffunction-sections -I"$HERE/include" -Wall -Wextra -Werror -c "$ENGINE/chrono.c" -o "$TMP/chrono.o"
"$TC/ld.lld" --gc-sections -e _start -T firmware/app.ld -Map="$RES/chronomorph.map" "$TMP/crt0.o" "$TMP/fm1_vec.o" "$TMP/fm1_isr.o" "$TMP/chrono-app.o" "$TMP/chrono.o" -o "$TMP/chronomorph.elf"
"$TC/llvm-readelf" -h -l "$TMP/chronomorph.elf" | tee "$RES/chronomorph-elf.txt"
"$TC/llvm-size" -A "$TMP/chronomorph.elf" | tee "$RES/chronomorph-size.txt"
test -z "$("$TC/llvm-nm" -u "$TMP/chronomorph.elf")"
python3 "$HERE/elf_xip.py" "$TMP/chronomorph.elf" "$TMP/chronomorph.xip.bin" | tee "$RES/chronomorph-xip.json"
run_case "$TMP/chronomorph.xip.bin" chrono-low p25q80 3
run_case "$TMP/chronomorph.xip.bin" chrono-low-repeat p25q80 3
run_case "$TMP/chronomorph.xip.bin" chrono-warp p25q80 24
run_case "$TMP/chronomorph.xip.bin" chrono-preset p25q80 3 "600-700:N3,900-1000:PLAY,1700-1900:SCL,3600-3700:HOME"
run_case "$TMP/chronomorph.xip.bin" chrono-preset-repeat p25q80 3 "600-700:N3,900-1000:PLAY,1700-1900:SCL,3600-3700:HOME"
cmp "$RES/chrono-preset.wav" "$RES/chrono-preset-repeat.wav"
live_contrast chrono-low chrono-preset | tee "$RES/chrono-preset-intervention.json"
run_case "$TMP/chronomorph.xip.bin" chrono-tempo p25q80 3 "600-700:N3,900-1000:PLAY,1700:K1:+12,3600-3700:HOME"
live_contrast chrono-low chrono-tempo | tee "$RES/chrono-tempo-intervention.json"
cmp "$RES/chrono-low.wav" "$RES/chrono-low-repeat.wav"
for other in chrono-warp chrono-preset chrono-tempo; do
  if cmp -s "$RES/chrono-low.wav" "$RES/$other.wav"; then
    echo "FAIL: Chronomorph panel control aliased: $other" >&2; exit 1
  fi
done
echo "Chronomorph actual target PCM repeat, warp, preset, live tempo contrast and HOME tail PASS" | tee "$RES/chronomorph-result.txt"

)

# Do not invoke the functions in an if/|| context: Bash would suppress
# errexit inside them. Capture statuses explicitly and aggregate at the end.
set +e
run_ecophon
eco_status=$?
run_chronomorph
chrono_status=$?
set -e
printf 'Ecophon exit=%s\nChronomorph exit=%s\n' "$eco_status" "$chrono_status" | tee "$RES/downstream-status.txt"
if (( eco_status != 0 || chrono_status != 0 )); then exit 1; fi
