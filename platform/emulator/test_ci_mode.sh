#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
source "$HERE/ci_mode.sh"
[[ $(vw_ci_mode) == all ]]
for mode in all baseline rate rate-eco rate-chrono; do [[ $(vw_ci_mode "$mode") == "$mode" ]]; done
for invalid in '' typo; do
  if vw_ci_mode "$invalid"; then exit 1; fi
done
if vw_ci_mode rate extra; then exit 1; fi
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
# Use a synthetic driver only: no emulator or target result is claimed.
cat >"$TMP/rate_target_probe.sh" <<'PROBE'
printf 'probe\n' >> "$TRACE"
[[ ${FAIL_PROBE:-0} == 0 ]]
PROBE
cat >"$TMP/driver.sh" <<'DRIVER'
#!/usr/bin/env bash
set -euo pipefail
source "$HELPER"
run_case() {
  [[ $1 == "$TMP/grimoire.xip.bin" && $3 == p25q80 ]]
  printf '%s:%s\n' "$2" "$4" >> "$TRACE"
  [[ ${FAIL_CASE:-} != "$2" ]]
}
vw_ci_rate_only
printf 'done\n' >> "$TRACE"
DRIVER
export HELPER="$HERE/ci_mode.sh" TMP TRACE="$TMP/trace"
HERE="$TMP"; export HERE
bash "$TMP/driver.sh"
printf 'orbit-n3:3\norbit-n9:9\nprobe\ndone\n' | cmp - "$TRACE"
for FAIL_CASE in orbit-n3 orbit-n9; do
  export FAIL_CASE
  : > "$TRACE"
  if bash "$TMP/driver.sh"; then exit 1; fi
  if grep -qE 'probe|done' "$TRACE"; then exit 1; fi
done
unset FAIL_CASE
: > "$TRACE"
if FAIL_PROBE=1 bash "$TMP/driver.sh"; then exit 1; fi
printf 'orbit-n3:3\norbit-n9:9\nprobe\n' | cmp - "$TRACE"
echo 'CI mode dispatch and failure propagation PASS (synthetic shell only)'
