# Shared stage selection for the exact pinned platform qualification runner.
vw_ci_mode() {
  if (( $# > 1 )); then
    echo 'usage: ci.sh [all|baseline|rate|rate-eco|rate-chrono]' >&2
    return 2
  fi
  case "${1-all}" in
    all|baseline|rate|rate-eco|rate-chrono) printf '%s\n' "${1-all}" ;;
    *) echo 'usage: ci.sh [all|baseline|rate|rate-eco|rate-chrono]' >&2; return 2 ;;
  esac
}

# Run only the baseline notes required by rate_quality.py, then all rate gates.
# Called directly in strict mode, never as a condition (which disables errexit).
vw_ci_rate_only() {
  run_case "$TMP/grimoire.xip.bin" orbit-n3 p25q80 3
  run_case "$TMP/grimoire.xip.bin" orbit-n9 p25q80 9
  source "$HERE/rate_target_probe.sh"
}
