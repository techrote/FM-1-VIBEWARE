"""Apply one reviewed private overlay to a pinned, ephemeral Dinghy source.

OTA otherwise consumes every assembled SysEx between companion-service calls.
Leave CY1 for the application, except in the existing recovery loop. No source
or firmware is written back to the reference repository.
"""
from pathlib import Path
import sys

path = Path(sys.argv[1]) / "firmware/src/ota.c"
source = path.read_text()
needle = "    d = ota_unpack7(p, n, ota_dec, sizeof ota_dec);"
assert source.count(needle) == 1, "Pinned OTA dispatch changed; inspect before adapting"
replacement = """#ifdef CYD_ENDPOINT_SERVICE
    /* CYDaux app owns its namespace; recovery still consumes unknown frames. */
    if (!recovery_active && n >= 3u && p[0] == 0x7d && p[1] == 'C' && p[2] == 'Y')
        return 0;
#endif
""" + needle
path.write_text(source.replace(needle, replacement))
