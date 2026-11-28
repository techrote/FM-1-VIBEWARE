#!/usr/bin/env bash
set -euo pipefail
export LC_ALL=C
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HERE="$ROOT/platform/companion"
if ! git -C "$ROOT" diff --quiet HEAD -- platform/companion platform/emulator .github/workflows/cydaux-endpoint.yml; then
    echo 'Qualification requires committed adapter, harness and build sources.' >&2
    exit 1
fi
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
RES="$ROOT/companion-results"
mkdir -p "$RES"
DINGHY=92f17b28f2d05f2f78fd1b160b58475d518902c8
XENO=fa27a317bb116f2afb62a710876f96314756f814
GRIMOIRE=ca1b83a5f6c8f1e87dea671f93f7e2a6d3bc432f
INSTRUMENT="${VIBEWARE_USB_INSTRUMENT:-xeno}"
case "$INSTRUMENT" in
    xeno) ENGINE_REF="$XENO"; ENGINE_DIR=xenoresonator; CORE=xeno ;;
    grimoire) ENGINE_REF="$GRIMOIRE"; ENGINE_DIR=grimoire; CORE=orbit ;;
    *) echo 'Unsupported instrument' >&2; exit 2 ;;
esac
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
checkout https://github.com/techrote/FM-1-VIBEWARE.git "$TMP/engine" "$ENGINE_REF"
checkout https://github.com/zvenson/dinghy.git "$TMP/dinghy" "$DINGHY"
checkout https://github.com/joakimeriksson/fm1-emu.git "$TMP/emu" "$EMU"
ENGINE="$TMP/engine/instruments/$ENGINE_DIR"
printf 'integration=%s\nintegration_tree=%s\ncydaux=%s\n%s=%s\ndinghy=%s\nemulator=%s\ntoolchain_archive=%s\n' \
    "$(git -C "$ROOT" rev-parse HEAD)" "$(git -C "$ROOT" rev-parse 'HEAD^{tree}')" "$CYDAUX_REF" "$INSTRUMENT" "$ENGINE_REF" "$DINGHY" "$EMU" "$TC_SHA" > "$RES/pins.txt"
for CC in gcc clang; do
    "$CC" -std=c11 -O2 -Wall -Wextra -Werror -fsanitize=address,undefined -fno-sanitize-recover=all -I"$ENGINE" -c "$ENGINE/$CORE.c" -o "$TMP/engine.o"
    "$CC" -std=c11 -O2 -Wall -Wextra -Werror -fsanitize=address,undefined -fno-sanitize-recover=all -c "$HERE/cyd_endpoint.c" -o "$TMP/endpoint.o"
    if [ "$CC" = gcc ]; then CXX=g++; else CXX=clang++; fi
    if [ "$INSTRUMENT" = grimoire ]; then
        "$CC" -std=c11 -O2 -Wall -Wextra -Werror -fsanitize=address,undefined -fno-sanitize-recover=all \
            -I"$ENGINE" -I"$HERE" "$HERE/test_grimoire_endpoint.c" "$TMP/engine.o" "$TMP/endpoint.o" -o "$TMP/grimoire-host"
        "$TMP/grimoire-host" | tee "$RES/grimoire-host-$CC.txt"
        CONTRACT="$HERE/test_grimoire_codec.cpp"
    else
        CONTRACT="$HERE/test_contract.cpp"
    fi
    "$CXX" -std=c++17 -O2 -Wall -Wextra -Werror -fsanitize=address,undefined -fno-sanitize-recover=all \
        -I"$ENGINE" -I"$HERE" -I"$TMP/cydaux/include" "$TMP/cydaux/src/companion.cpp" "$CONTRACT" \
        "$TMP/engine.o" "$TMP/endpoint.o" -o "$TMP/contract"
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
cp "$HERE/${INSTRUMENT}_app.c" "$TMP/platform/firmware/src/dinghy.c"
cd "$TMP/platform"
"$TC/clang" -target pi32v2 -mcpu=ac791n -Os -ffunction-sections -fno-builtin -Wall -Wno-unused-function \
    -Ifirmware/hal -Ifirmware/src -Ifirmware/gen -I"$ENGINE" -I"$HERE" -I"$ROOT/platform/emulator" \
    -DAPP_VER='"dev"' -DFELUCCA_ID='"FM-1_990"' -c firmware/src/dinghy.c -o "$TMP/app.o"
for source in "$ENGINE/$CORE.c" "$HERE/cyd_endpoint.c" "$HERE/arithmetic.c"; do
    "$TC/clang" -target pi32v2 -mcpu=ac791n -Os -ffreestanding -fno-builtin -ffunction-sections \
        -I"$ROOT/platform/emulator/include" -I"$HERE" -Wall -Wextra -Werror -c "$source" -o "$TMP/$(basename "$source" .c).o"
done
for source in firmware/crt0.S firmware/hal/fm1_vec.S firmware/hal/fm1_isr.S; do
    "$TC/clang" -target pi32v2 -mcpu=ac791n -c "$source" -o "$TMP/$(basename "$source" .S).o"
done
"$TC/ld.lld" --gc-sections -e _start -T firmware/app.ld -Map="$RES/$INSTRUMENT.map" \
    "$TMP/crt0.o" "$TMP/fm1_vec.o" "$TMP/fm1_isr.o" "$TMP/app.o" "$TMP/$CORE.o" "$TMP/cyd_endpoint.o" "$TMP/arithmetic.o" -o "$TMP/$INSTRUMENT.elf"
test -z "$("$TC/llvm-nm" -u "$TMP/$INSTRUMENT.elf")"
"$TC/llvm-size" -A "$TMP/$INSTRUMENT.elf" | tee "$RES/target-size.txt"
"$TC/llvm-readelf" -h -l "$TMP/$INSTRUMENT.elf" > "$RES/target-elf.txt"
"$TC/llvm-nm" "$TMP/$INSTRUMENT.elf" > "$RES/target-symbols.txt"
awk '/ target_audio_blocks$| target_audio_max_ticks$| target_reply_deferrals$/ {print $3" "$1}' "$RES/target-symbols.txt" > "$TMP/metrics.txt"
test "$(wc -l < "$TMP/metrics.txt")" = 3
python3 "$ROOT/platform/emulator/elf_xip.py" "$TMP/$INSTRUMENT.elf" "$TMP/$INSTRUMENT.xip.bin" | tee "$RES/xip.json"
mkdir -p "$TMP/harness/src"
cp "$HERE/usb_harness.rs" "$TMP/harness/src/main.rs"
mkdir -p "$TMP/harness/src/bin"
cp "$HERE/bridge_usb_stdio.rs" "$TMP/harness/src/bin/bridge_usb_stdio.rs"
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
ARGS=()
if [ "$INSTRUMENT" = grimoire ]; then ARGS=(grimoire); fi
timeout 600 "$EXE" "$TMP/$INSTRUMENT.xip.bin" "$RES/instruction" "$TMP/metrics.txt" instruction "${ARGS[@]}" | tee "$RES/instruction-usb.log"
timeout 900 "$EXE" "$TMP/$INSTRUMENT.xip.bin" "$RES/strict" "$TMP/metrics.txt" strict "${ARGS[@]}" | tee "$RES/strict-usb.log"
cmake -S "$TMP/cydaux" -B "$TMP/cyd-build" -DCMAKE_BUILD_TYPE=Release
cmake --build "$TMP/cyd-build" --target fm1-simulator -j 2
timeout 600 python3 "$HERE/test_bridge_usb.py" "$TMP/cydaux" "$TMP/cyd-build/fm1-simulator" "$TMP/harness/target/release/bridge_usb_stdio" "$TMP/$INSTRUMENT.xip.bin" "$RES/bridge-usb.json" "$INSTRUMENT" | tee "$RES/bridge-usb.log"
python3 - "$RES" <<'PY'
import hashlib,json,sys
from pathlib import Path
root=Path(sys.argv[1])
files={str(path.relative_to(root)):hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(root.rglob('*')) if path.is_file()}
(root/'sha256.json').write_text(json.dumps(files,indent=2)+'\n')
PY
# Deliberately no ELF/XIP/emulator executable upload: original distribution gates remain.
