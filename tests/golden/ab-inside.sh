#!/usr/bin/env bash
# One conversion through two engines, recorded the same way as the reference
# cases, side by side: <result>/a and <result>/b. tests/golden.sh ab runs it,
# in the tools image or (with --local) on this host.
#
#   ab-inside.sh <engine-a> <engine-b> <result-dir> -- <flags and files>
set -uo pipefail

A="$1" B="$2" RESULT="$3"; shift 3
[[ "${1:-}" == "--" ]] && shift
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO_ROOT="$(cd "$HERE/../.." && pwd -P)"

export SOURCE_DATE_EPOCH=1767225600 FORCE_SOURCE_DATE=1 TZ=UTC
export PATH="$HERE/bin:$PATH"

# Inputs are the caller's own files, named by path; the working folder only
# holds what each engine writes (.fcc/, output/).
inputs=()
for a in "$@"; do [[ -f "$a" ]] && inputs+=("$(basename "$a")"); done

for side in a b; do
    engine="$A"; [[ "$side" == b ]] && engine="$B"
    work="$(mktemp -d)"; work="$(cd "$work" && pwd -P)"
    res="$RESULT/$side"; mkdir -p "$res/calls"
    export GOLDEN_CAPTURE="$res/calls" GOLDEN_WORK="$work" GOLDEN_ENGINE_DIR="$REPO_ROOT"
    (cd "$work" && HOLO_CONVERT_ENGINE=local bash "$engine" "$@") > "$res/log" 2>&1
    echo "$?" > "$res/exit-code"
    rm -f "$res/calls/.count"
    python3 "$HERE/collect.py" "$work" "$res" "$REPO_ROOT" ${inputs[@]+"${inputs[@]}"}
    printf '%-2s exit %s  (%s)\n' "$side" "$(cat "$res/exit-code")" "${engine#"$REPO_ROOT"/}"
    rm -rf "$work"
done
