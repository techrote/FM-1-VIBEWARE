#!/usr/bin/env bash
set -euo pipefail
export LC_ALL=C
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HERE="$ROOT/platform/companion"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
RES="$ROOT/companion-results"
mkdir -p "$RES"
DINGHY=92f17b28f2d05f2f78fd1b160b58475d518902c8
XENO=fa27a317bb116f2afb62a710876f96314756f814
EMU=736aded65c8e2e9d652cf595fca248734483a877
TC_SHA=cb896562418a2be93edb9bac26af4bc81a106a32974002a78e6b9fc203c93990
: "${CYDAUX_REF:?Set exact FM-1-CYDaux source SHA containing companion.cpp}"
[[ "$CYDAUX_REF" =~ ^[0-9a-f]{40}$ ]]
checkout() {
    git init -q "$2"
    git -C "$2" remote add origin "$1"
    git -C "$2" fetch --depth=1 origin "$3"
    git -C "$2" checkout --detach FETCH_HEAD
    test "$(git -C "$2" rev-parse HEAD)" = "$3"
}
checkout https://github.com/techrote/FM-1-CYDaux.git "$TMP/cydaux" "$CYDAUX_REF"
checkout https://github.com/techrote/FM-1-VIBEWARE.git "$TMP/xeno" "$XENO"
checkout https://github.com/zvenson/dinghy.git "$TMP/dinghy" "$DINGHY"
checkout https://github.com/joakimeriksson/fm1-emu.git "$TMP/emu" "$EMU"
ENGINE="$TMP/xeno/instruments/xenoresonator"
printf 'integration=%s\ncydaux=%s\nxeno=%s\ndinghy=%s\nemulator=%s\ntoolchain_archive=%s\n' \
    "$(git -C "$ROOT" rev-parse HEAD)" "$CYDAUX_REF" "$XENO" "$DINGHY" "$EMU" "$TC_SHA" > "$RES/pins.txt"
for CC in gcc clang; do
    "$CC" -std=c11 -O2 -Wall -Wextra -Werror -fsanitize=address,undefined -fno-sanitize-recover=all -I"$ENGINE" -c "$ENGINE/xeno.c" -o "$TMP/xeno.o"
    "$CC" -std=c11 -O2 -Wall -Wextra -Werror -fsanitize=address,undefined -fno-sanitize-recover=all -c "$HERE/cyd_endpoint.c" -o "$TMP/endpoint.o"
    if [ "$CC" = gcc ]; then CXX=g++; else CXX=clang++; fi
    "$CXX" -std=c++17 -O2 -Wall -Wextra -Werror -fsanitize=address,undefined -fno-sanitize-recover=all \
        -I"$ENGINE" -I"$HERE" -I"$TMP/cydaux/include" "$TMP/cydaux/src/companion.cpp" "$HERE/test_contract.cpp" \
        "$TMP/xeno.o" "$TMP/endpoint.o" -o "$TMP/contract"
    "$TMP/contract" | tee "$RES/contract-$CC.txt"
    "$CC" -std=c11 -O2 -Wall -Wextra -Werror -fsanitize=undefined -fno-sanitize-recover=all \
        "$HERE/arithmetic.c" "$HERE/test_arithmetic.c" -o "$TMP/arithmetic"
    "$TMP/arithmetic" | tee "$RES/arithmetic-$CC.txt"
done
curl -fL --retry 2 --max-time 240 -o "$TMP/tc.tar.xz" https://github.com/jvitkauskas/pi32v2-llvm/releases/download/pi32v2-23.1.5-2/pi32v2-llvm-23.1.5-2-linux-x64.tar.xz
printf '%s  %s\n' "$TC_SHA" "$TMP/tc.tar.xz" | sha256sum -c -
mkdir "$TMP/tc" "$TMP/platform"
tar -xJf "$TMP/tc.tar.xz" -C "$TMP/tc" --strip-components=1
TC="$TMP/tc/bin"
"$TC/clang" --version > "$RES/compiler.txt"
git -C "$TMP/dinghy" archive "$DINGHY" | tar -x -C "$TMP/platform"
python3 "$HERE/prepare_platform.py" "$TMP/platform"
cp "$HERE/xeno_app.c" "$TMP/platform/firmware/src/dinghy.c"
cd "$TMP/platform"
"$TC/clang" -target pi32v2 -mcpu=ac791n -Os -ffunction-sections -fno-builtin -Wall -Wno-unused-function \
    -Ifirmware/hal -Ifirmware/src -Ifirmware/gen -I"$ENGINE" -I"$HERE" -I"$ROOT/platform/emulator" \
    -DAPP_VER='"dev"' -DFELUCCA_ID='"FM-1_990"' -c firmware/src/dinghy.c -o "$TMP/app.o"
for source in "$ENGINE/xeno.c" "$HERE/cyd_endpoint.c" "$HERE/arithmetic.c"; do
    "$TC/clang" -target pi32v2 -mcpu=ac791n -Os -ffreestanding -fno-builtin -ffunction-sections \
        -I"$ROOT/platform/emulator/include" -I"$HERE" -Wall -Wextra -Werror -c "$source" -o "$TMP/$(basename "$source" .c).o"
done
for source in firmware/crt0.S firmware/hal/fm1_vec.S firmware/hal/fm1_isr.S; do
    "$TC/clang" -target pi32v2 -mcpu=ac791n -c "$source" -o "$TMP/$(basename "$source" .S).o"
done
"$TC/ld.lld" --gc-sections -e _start -T firmware/app.ld -Map="$RES/xeno.map" \
    "$TMP/crt0.o" "$TMP/fm1_vec.o" "$TMP/fm1_isr.o" "$TMP/app.o" "$TMP/xeno.o" "$TMP/cyd_endpoint.o" "$TMP/arithmetic.o" -o "$TMP/xeno.elf"
test -z "$("$TC/llvm-nm" -u "$TMP/xeno.elf")"
"$TC/llvm-size" -A "$TMP/xeno.elf" | tee "$RES/target-size.txt"
"$TC/llvm-readelf" -h -l "$TMP/xeno.elf" > "$RES/target-elf.txt"
"$TC/llvm-nm" "$TMP/xeno.elf" > "$RES/target-symbols.txt"
awk '/ target_audio_blocks$| target_audio_max_ticks$| target_reply_deferrals$/ {print $3" "$1}' "$RES/target-symbols.txt" > "$TMP/metrics.txt"
test "$(wc -l < "$TMP/metrics.txt")" = 3
python3 "$ROOT/platform/emulator/elf_xip.py" "$TMP/xeno.elf" "$TMP/xeno.xip.bin" | tee "$RES/xip.json"
mkdir -p "$TMP/harness/src"
cp "$HERE/usb_harness.rs" "$TMP/harness/src/main.rs"
cat > "$TMP/harness/Cargo.toml" <<EOF
[package]
name = "cydaux-usb-qualification"
version = "0.1.0"
edition = "2021"
[dependencies]
fm1-soc = { path = "$TMP/emu/crates/fm1-soc" }
fm1-core = { path = "$TMP/emu/crates/fm1-core" }
[profile.release]
opt-level = 3
EOF
cargo build --release --offline --manifest-path "$TMP/harness/Cargo.toml"
EXE="$TMP/harness/target/release/cydaux-usb-qualification"
timeout 600 "$EXE" "$TMP/xeno.xip.bin" "$RES/instruction" "$TMP/metrics.txt" instruction | tee "$RES/instruction-usb.log"
timeout 900 "$EXE" "$TMP/xeno.xip.bin" "$RES/strict" "$TMP/metrics.txt" strict | tee "$RES/strict-usb.log"
python3 - "$RES" <<'PY'
import hashlib,json,sys
from pathlib import Path
root=Path(sys.argv[1])
files={str(path.relative_to(root)):hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(root.rglob('*')) if path.is_file()}
(root/'sha256.json').write_text(json.dumps(files,indent=2)+'\n')
PY
# Deliberately no ELF/XIP/emulator executable upload: original distribution gates remain.
