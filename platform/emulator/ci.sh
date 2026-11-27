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
  local dir="$TMP/run-$name"
  mkdir -p "$dir/work"
  (
    cd "$dir"
    FM1_LCD_TIMED=1 timeout 300 "$EXE" --bin "$image" --entry 0x02000120 --ms 4500 --keys "600-700:N$note,900-1000:PLAY,3600-3700:HOME" --flash-chip "$part" --wav "$RES/$name.wav" --quiet
  ) > "$RES/$name.log" 2>&1
  python3 "$TMP/mhac/emulator-qualification-001/analyze_wav.py" "$RES/$name.wav" --require-audio --silent-tail-ms 500 | tee "$RES/$name.json"
  # Ensure a substantial capture, not a truncated file that happens to end in silence.
  python3 -c 'import sys,wave; w=wave.open(sys.argv[1]); assert w.getnframes() >= 44100*4' "$RES/$name.wav"
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
