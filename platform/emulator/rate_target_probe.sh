# Source only from ci.sh after the baseline reference/Grimoire gate.
# Reuse the already verified toolchain, Dinghy, Orbit core and pinned emulator.
(
  set -euo pipefail
  PROBE="$RES/rate-probe"
  mkdir "$PROBE"
  python3 "$HERE/rate_probe.py" --test | tee "$PROBE/host-parser.txt"
  for cc in gcc clang; do
    "$cc" -std=c11 -Wall -Wextra -Werror -O2 -fsanitize=undefined -fno-sanitize-recover=all "$HERE/test_rate_linear.c" -o "$TMP/rate-linear-$cc"
    "$TMP/rate-linear-$cc" | tee "$PROBE/host-$cc.txt"
  done
  for mode in hold linear; do
    python3 "$HERE/rate_probe.py" prepare "$HERE/grimoire_app.c" "$mode" firmware/src/dinghy.c
    "$TC/clang" -target pi32v2 -mcpu=ac791n -Os -ffunction-sections -fno-builtin -Wall -Wno-unused-function -Ifirmware/hal -Ifirmware/src -Ifirmware/gen -I"$ORBIT" -I"$HERE" -DAPP_VER='"dev"' -DFELUCCA_ID='"FM-1_990"' -c firmware/src/dinghy.c -o "$TMP/probe-$mode.o"
    "$TC/ld.lld" --gc-sections -e _start -T firmware/app.ld -Map="$PROBE/$mode.map" "$TMP/crt0.o" "$TMP/fm1_vec.o" "$TMP/fm1_isr.o" "$TMP/probe-$mode.o" "$TMP/orbit.o" -o "$TMP/probe-$mode.elf"
    test -z "$("$TC/llvm-nm" -u "$TMP/probe-$mode.elf")"
    "$TC/llvm-size" -A "$TMP/probe-$mode.elf" > "$PROBE/$mode-size.txt"
    "$TC/llvm-objdump" -d "$TMP/probe-$mode.o" > "$PROBE/$mode-disassembly.txt"
    "$TC/llvm-nm" "$TMP/probe-$mode.elf" > "$PROBE/$mode-symbols.txt"
    addr=$(awk '$3=="vw_probe_metrics"{print $1}' "$PROBE/$mode-symbols.txt")
    [[ "$addr" =~ ^[0-9a-fA-F]{8}$ ]]
    printf '0x%s\n' "$addr" > "$PROBE/$mode-address.txt"
    python3 "$HERE/elf_xip.py" "$TMP/probe-$mode.elf" "$TMP/probe-$mode.xip.bin" > "$PROBE/$mode-xip.json"
    for case in n3 n3-repeat n9; do
      note=3; [[ "$case" != n9 ]] || note=9
      mkdir "$TMP/probe-$mode-$case"
      (cd "$TMP/probe-$mode-$case"; FM1_LCD_TIMED=1 timeout 300 "$EXE" --bin "$TMP/probe-$mode.xip.bin" --entry 0x02000120 --ms 4500 --keys "600-700:N$note,900-1000:PLAY,3600-3700:HOME" --flash-chip p25q80 --wav "$PROBE/$mode-$case.wav" --dump "0x$addr" 5 --quiet) > "$PROBE/$mode-$case.log" 2>&1
    done
  done
  python3 "$HERE/rate_probe.py" compare "$PROBE" | tee "$PROBE/summary.json"
  python3 "$HERE/rate_quality.py" --test | tee "$PROBE/quality-test.txt"
  python3 "$HERE/rate_quality.py" "$RES" | tee "$PROBE/quality.json"
)
