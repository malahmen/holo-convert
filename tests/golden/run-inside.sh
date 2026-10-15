#!/usr/bin/env bash
# Runs inside the tools image (tests/golden.sh starts it): every case in
# cases.txt through the engine under test, recorded by the pandoc wrapper and
# collected by collect.py into <result-dir>/<case>/.
#
#   run-inside.sh <engine-script> <result-dir> [case-name-filter]
set -uo pipefail

ENGINE="$1" RESULT="$2" FILTER="${3:-}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
# The repository root, whichever engine runs (the bash one, or a port under
# wip/): the canonical .fcc/ lives there, and its path is normalised away.
REPO_ROOT="$(cd "$HERE/../.." && pwd -P)"
CASES="$HERE/cases"

# Fixed time for everything that would otherwise stamp the clock in (pandoc's
# DOCX core properties, TeX's PDF dates): 2026-01-01T00:00:00Z.
export SOURCE_DATE_EPOCH=1767225600 FORCE_SOURCE_DATE=1 TZ=UTC LC_ALL=C.UTF-8
export PATH="$HERE/bin:$PATH"

STAGE="$(mktemp -d)"
# The binary inputs are made here, not kept in the repository: a 16x16 PNG,
# and a DOCX built by plain pandoc (not the engine) from the feature document.
python3 - "$STAGE/pixel.png" <<'PY'
import struct, sys, zlib
w = h = 16
raw = b"".join(b"\x00" + bytes([200, 60, 40]) * w for _ in range(h))
def chunk(t, d): return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) \
      + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")
open(sys.argv[1], "wb").write(png)
PY
cp "$CASES"/* "$STAGE/"
(cd "$STAGE" && /usr/bin/pandoc features.md -o generated.docx)

failed=0
while IFS='|' read -r name inputs flags; do
    name="$(echo "$name" | xargs)"
    [[ -z "$name" || "$name" == \#* ]] && continue
    [[ -n "$FILTER" && "$name" != *"$FILTER"* ]] && continue
    # xargs strips the padding and splits on spaces, honouring double quotes.
    read -r -a input_list <<< "$(echo "$inputs" | xargs)"
    # eval, so a quoted value ("DejaVu Sans") stays one argument. cases.txt is
    # this repository's own file, not input from anywhere else.
    flag_list=()
    eval "flag_list=($flags)"

    work="$(mktemp -d)"
    cp "$STAGE"/* "$work/"
    res="$RESULT/$name"; mkdir -p "$res/calls"
    export GOLDEN_CAPTURE="$res/calls" GOLDEN_WORK="$work" GOLDEN_ENGINE_DIR="$REPO_ROOT"
    (cd "$work" && HOLO_CONVERT_ENGINE=local bash "$ENGINE" "${flag_list[@]}" "${input_list[@]}") \
        > "$res/log" 2>&1
    echo "$?" > "$res/exit-code"
    rm -f "$res/calls/.count"
    python3 "$HERE/collect.py" "$work" "$res" "$REPO_ROOT"
    printf '%-18s exit %s\n' "$name" "$(cat "$res/exit-code")"
    rm -rf "$work"
done < "$HERE/cases.txt"
rm -rf "$STAGE"
exit "$failed"
