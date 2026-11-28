# Sourced from ci.sh only in the isolated rate-chrono stage.
(
  set -euo pipefail
  PROBE="$RES/rate-chronophon"
  mkdir "$PROBE"
  CHRONO=be57d9f77e9325271adbd4558dfd554c6cd81e19
  checkout https://github.com/techrote/FM-1-VIBEWARE.git "$TMP/chrono-core" "$CHRONO"
  ENGINE="$TMP/chrono-core/instruments/chronomorph"
  printf 'chronomorph_core=%s\n' "$CHRONO" >> "$RES/pins.txt"
  python3 "$HERE/rate_chronomorph.py" --test "$HERE/chrono_app.c" "$HERE/chrono_runtime.h" | tee "$PROBE/generator-test.txt"
  "$TC/clang" -target pi32v2 -mcpu=ac791n -Os -ffreestanding -fno-builtin -ffunction-sections -I"$HERE/include" -Wall -Wextra -Werror -c "$ENGINE/chrono.c" -o "$TMP/chrono-rate-core.o"
  for mode in baseline hold linear; do
    variant="$TMP/chrono-rate-$mode"
    if [[ "$mode" == baseline ]]; then
      mkdir "$variant"
      cp "$HERE/chrono_app.c" "$variant/dinghy.c"
      cp "$HERE/chrono_runtime.h" "$variant/chrono_runtime.h"
    else
      python3 "$HERE/rate_chronomorph.py" prepare "$HERE/chrono_app.c" "$HERE/chrono_runtime.h" "$variant" "$mode"
    fi
    cp "$HERE/test_chronomorph_runtime.c" "$variant/test_chronomorph_runtime.c"
    for cc in gcc clang; do
      "$cc" -std=c11 -Wall -Wextra -Werror -O2 -fsanitize=undefined -fno-sanitize-recover=all -I"$variant" -I"$ENGINE" -I"$HERE" "$variant/test_chronomorph_runtime.c" "$ENGINE/chrono.c" -o "$TMP/chrono-rate-test" 2>&1 | tee "$PROBE/$mode-$cc-build.txt"
      "$TMP/chrono-rate-test" | tee "$PROBE/$mode-$cc.txt"
    done
    cp "$variant/dinghy.c" firmware/src/dinghy.c
    "$TC/clang" -target pi32v2 -mcpu=ac791n -Os -ffunction-sections -fno-builtin -Wall -Wno-unused-function -Ifirmware/hal -Ifirmware/src -Ifirmware/gen -I"$variant" -I"$ENGINE" -I"$HERE" -DAPP_VER='"dev"' -DFELUCCA_ID='"FM-1_990"' -c firmware/src/dinghy.c -o "$TMP/chrono-rate-$mode.o"
    "$TC/ld.lld" --gc-sections -e _start -T firmware/app.ld -Map="$PROBE/$mode.map" "$TMP/crt0.o" "$TMP/fm1_vec.o" "$TMP/fm1_isr.o" "$TMP/chrono-rate-$mode.o" "$TMP/chrono-rate-core.o" -o "$TMP/chrono-rate-$mode.elf"
    test -z "$("$TC/llvm-nm" -u "$TMP/chrono-rate-$mode.elf")"
    "$TC/llvm-size" -A "$TMP/chrono-rate-$mode.elf" > "$PROBE/$mode-size.txt"
    "$TC/llvm-objdump" -d "$TMP/chrono-rate-$mode.o" > "$PROBE/$mode-disassembly.txt"
    python3 "$HERE/elf_xip.py" "$TMP/chrono-rate-$mode.elf" "$TMP/chrono-rate-$mode.xip.bin" > "$PROBE/$mode-xip.json"
    dump=()
    if [[ "$mode" != baseline ]]; then
      "$TC/llvm-nm" "$TMP/chrono-rate-$mode.elf" > "$PROBE/$mode-symbols.txt"
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
      mkdir "$TMP/chrono-rate-$mode-$case"
      (cd "$TMP/chrono-rate-$mode-$case"; FM1_LCD_TIMED=1 timeout 300 "$EXE" --bin "$TMP/chrono-rate-$mode.xip.bin" --entry 0x02000120 --ms 6200 --keys "$keys" --flash-chip p25q80 --wav "$PROBE/$mode-$case.wav" "${dump[@]}" --quiet) > "$PROBE/$mode-$case.log" 2>&1
    done
  done
  python3 "$HERE/rate_chronomorph.py" "$PROBE" | tee "$PROBE/summary.json"
)
