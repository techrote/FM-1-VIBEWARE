# Sourced from ci.sh only in the isolated rate-eco stage.
(
  set -euo pipefail
  PROBE="$RES/rate-ecophon"
  mkdir "$PROBE"
  checkout https://github.com/techrote/FM-1-VIBEWARE.git "$TMP/eco-core" "$ECO"
  ENGINE="$TMP/eco-core/instruments/ecophon"
  printf 'ecophon_core=%s\n' "$ECO" >> "$RES/pins.txt"
  "$TC/clang" -target pi32v2 -mcpu=ac791n -Os -ffreestanding -fno-builtin -ffunction-sections -I"$HERE/include" -Wall -Wextra -Werror -c "$ENGINE/ecophon.c" -o "$TMP/eco-rate-core.o"
  for mode in baseline hold linear; do
    variant="$TMP/eco-rate-$mode"
    if [[ "$mode" == baseline ]]; then
      mkdir "$variant"
      cp "$HERE/ecophon_app.c" "$variant/dinghy.c"
      cp "$HERE/ecophon_runtime.h" "$variant/ecophon_runtime.h"
    else
      python3 "$HERE/rate_ecophon.py" prepare "$HERE/ecophon_app.c" "$HERE/ecophon_runtime.h" "$variant" "$mode"
    fi
    cp "$HERE/test_ecophon_runtime.c" "$variant/test_ecophon_runtime.c"
    for cc in gcc clang; do
      "$cc" -std=c11 -Wall -Wextra -Werror -O2 -fsanitize=undefined -fno-sanitize-recover=all -I"$variant" -I"$ENGINE" -I"$HERE" "$variant/test_ecophon_runtime.c" "$ENGINE/ecophon.c" -o "$TMP/eco-rate-test" 2>&1 | tee "$PROBE/$mode-$cc-build.txt"
      "$TMP/eco-rate-test" | tee "$PROBE/$mode-$cc.txt"
    done
    cp "$variant/dinghy.c" firmware/src/dinghy.c
    "$TC/clang" -target pi32v2 -mcpu=ac791n -Os -ffunction-sections -fno-builtin -Wall -Wno-unused-function -Ifirmware/hal -Ifirmware/src -Ifirmware/gen -I"$variant" -I"$ENGINE" -I"$HERE" -DAPP_VER='"dev"' -DFELUCCA_ID='"FM-1_990"' -c firmware/src/dinghy.c -o "$TMP/eco-rate-$mode.o"
    "$TC/ld.lld" --gc-sections -e _start -T firmware/app.ld -Map="$PROBE/$mode.map" "$TMP/crt0.o" "$TMP/fm1_vec.o" "$TMP/fm1_isr.o" "$TMP/eco-rate-$mode.o" "$TMP/eco-rate-core.o" -o "$TMP/eco-rate-$mode.elf"
    test -z "$("$TC/llvm-nm" -u "$TMP/eco-rate-$mode.elf")"
    "$TC/llvm-size" -A "$TMP/eco-rate-$mode.elf" > "$PROBE/$mode-size.txt"
    "$TC/llvm-objdump" -d "$TMP/eco-rate-$mode.o" > "$PROBE/$mode-disassembly.txt"
    python3 "$HERE/elf_xip.py" "$TMP/eco-rate-$mode.elf" "$TMP/eco-rate-$mode.xip.bin" > "$PROBE/$mode-xip.json"
    dump=()
    if [[ "$mode" != baseline ]]; then
      "$TC/llvm-nm" "$TMP/eco-rate-$mode.elf" > "$PROBE/$mode-symbols.txt"
      addr=$(awk '$3=="vw_probe_metrics"{print $1}' "$PROBE/$mode-symbols.txt")
      [[ "$addr" =~ ^[0-9a-fA-F]{8}$ ]]
      printf '0x%s\n' "$addr" > "$PROBE/$mode-address.txt"
      dump=(--dump "0x$addr" 5)
    fi
    for case in lifecycle-control lifecycle-switch lifecycle-repeat; do
      if [[ "$mode" == baseline && "$case" == lifecycle-repeat ]]; then continue; fi
      keys="600-700:N3,900-1000:PLAY,2700-2800:HOME,3900-4000:PLAY,5200-5300:HOME"
      if [[ "$case" != lifecycle-control ]]; then
        keys="600-700:N3,900-1000:PLAY,1700-1900:SCL,2700-2800:HOME,3900-4000:PLAY,5200-5300:HOME"
      fi
      mkdir "$TMP/eco-rate-$mode-$case"
      (cd "$TMP/eco-rate-$mode-$case"; FM1_LCD_TIMED=1 timeout 300 "$EXE" --bin "$TMP/eco-rate-$mode.xip.bin" --entry 0x02000120 --ms 6200 --keys "$keys" --flash-chip p25q80 --wav "$PROBE/$mode-$case.wav" "${dump[@]}" --quiet) > "$PROBE/$mode-$case.log" 2>&1
    done
  done
  python3 "$HERE/rate_ecophon.py" "$PROBE" | tee "$PROBE/summary.json"
)
