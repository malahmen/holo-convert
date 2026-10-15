#!/usr/bin/env bash
# The golden harness: reference documents through the engine, in the pinned
# tools image, compared exactly with what the bash engine (v1.0.0) produced.
#
#   tests/golden.sh                    check the engine against tests/golden/expected/
#   tests/golden.sh record             re-record expected/ (after a deliberate change)
#   tests/golden.sh check --engine PATH  check another engine (inside this repository)
#   tests/golden.sh check --case docx  only the cases whose name contains "docx"
#   tests/golden.sh ab --engine-b PATH [--local] [--] <flags> <files>
#                                     one real conversion through this engine and
#                                     another (e.g. v1.0.0 in a worktree), compared;
#                                     --local uses this host's tools, not the image
#
# What is compared, per case (tests/golden/cases.txt):
#   - the exit code and the engine's messages;
#   - every pandoc call: its arguments, and the files the engine produced for
#     it (the Markdown after the pre-passes, generated LaTeX headers);
#   - for a PDF, the LaTeX pandoc generates (the PDF itself carries a date);
#   - every output: DOCX as pretty-printed XML parts, Markdown as text;
#   - the sources after the run (--fix-links rewrites them).
# Paths and today's date are normalised away; time is fixed with
# SOURCE_DATE_EPOCH. Everything runs in the image `--engine container` uses,
# so the tool versions are the same on every machine.
#
# Needs podman or docker and the image (holo-convert.sh --setup --engine
# container). Without them it prints SKIP and exits 0, so tests/run-all.sh and
# CI stay usable on hosts that cannot run it.
set -uo pipefail

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
REPO="$(cd "$TEST_DIR/.." && pwd -P)"
MODE="check" ENGINE="$REPO/holo-convert.sh" FILTER="" RT="${HOLO_CONVERT_RUNTIME:-}" LOCAL=false
AB_ARGS=() B_ENGINE=""

# The image --engine container uses: its tag is the Containerfile's content
# hash (holo/container.py), so a changed toolchain is a different image.
golden_image() {
    if [[ -n "${HOLO_CONVERT_IMAGE:-}" ]]; then printf '%s' "$HOLO_CONVERT_IMAGE"; return; fi
    local sum
    sum="$( { sha256sum "$REPO/container/Containerfile" 2>/dev/null || shasum -a 256 "$REPO/container/Containerfile"; } | cut -c1-12)"
    printf 'localhost/holo-convert-tools:%s' "$sum"
}
while [[ $# -gt 0 ]]; do
    case "$1" in
        check|record|ab) MODE="$1"; shift ;;
        --local)   LOCAL=true; shift ;;
        --engine-b) B_ENGINE="$(cd "$(dirname "$2")" && pwd -P)/$(basename "$2")"; shift 2 ;;
        --)        shift; AB_ARGS=("$@"); break ;;
        --engine)  ENGINE="$(cd "$(dirname "$2")" && pwd -P)/$(basename "$2")"; shift 2 ;;
        --case)    FILTER="$2"; shift 2 ;;
        --runtime) RT="$2"; shift 2 ;;
        -h|--help) sed -n '2,25p' "$0"; exit 0 ;;
        # In ab mode the first argument the harness does not know starts the
        # conversion, so `ab --local --from md ...` needs no `--`. (The
        # harness's own --engine/--runtime/--case come first; put a `--`
        # before the conversion to hand those to holo-convert instead.)
        *) if [[ "$MODE" == ab ]]; then AB_ARGS=("$@"); break; fi
           echo "golden: unknown argument $1" >&2; exit 2 ;;
    esac
done
[[ -f "$ENGINE" ]] || { echo "golden: no engine at $ENGINE" >&2; exit 2; }

# --- ab: one real conversion, two engines --------------------------------------
if [[ "$MODE" == ab ]]; then
    (( ${#AB_ARGS[@]} )) || { echo "golden ab: give the conversion after --  (e.g. ab -- --from md --to docx doc.md)" >&2; exit 2; }
    if [[ -z "$B_ENGINE" ]]; then
        echo "golden ab: name the engine to compare with, inside this repository, e.g. the last bash release:" >&2
        echo "  git worktree add .golden-v1 v1.0.0 && tests/golden.sh ab --engine-b .golden-v1/holo-convert.sh --local --from md ..." >&2
        exit 2
    fi
    [[ -f "$B_ENGINE" ]] || { echo "golden ab: no engine at $B_ENGINE" >&2; exit 2; }
    case "$B_ENGINE" in "$REPO"/*) ;; *) echo "golden ab: --engine-b must live in this repository ($REPO)" >&2; exit 2 ;; esac
    for a in "${AB_ARGS[@]}"; do
        [[ "$a" == -o || "$a" == --output ]] && { echo "golden ab: leave out -o - each engine writes into its own working folder" >&2; exit 2; }
    done
    # Paths become absolute, so the same arguments work from the working folders.
    args=() mounts=()
    for a in "${AB_ARGS[@]}"; do
        if [[ -e "$a" ]]; then
            abs="$(cd "$(dirname "$a")" && pwd -P)/$(basename "$a")"; args+=("$abs")
            mounts+=(-v "$(dirname "$abs"):$(dirname "$abs"):ro")
        else args+=("$a"); fi
    done
    ACTUAL="$(mktemp -d)"; ACTUAL="$(cd "$ACTUAL" && pwd -P)"
    trap 'rm -rf "$ACTUAL"' EXIT
    if [[ "$LOCAL" == true ]]; then
        bash "$TEST_DIR/golden/ab-inside.sh" "$ENGINE" "$B_ENGINE" "$ACTUAL" -- "${args[@]}"
    else
        if [[ -z "$RT" ]]; then
            if command -v podman &>/dev/null; then RT=podman; elif command -v docker &>/dev/null; then RT=docker
            else echo "golden ab: no podman or docker (or use --local)" >&2; exit 2; fi
        fi
        IMAGE="$(golden_image)"
        "$RT" image inspect "$IMAGE" &>/dev/null || { echo "golden ab: image $IMAGE not built (holo-convert.sh --setup --engine container)" >&2; exit 2; }
        user=(--user "$(id -u):$(id -g)"); [[ "$RT" == podman ]] && user=(--userns=keep-id)
        "$RT" run --rm --network none "${user[@]}" --security-opt label=disable -e HOME=/tmp \
            -v "$REPO:$REPO:ro" -v "$ACTUAL:$ACTUAL" "${mounts[@]}" -w "$REPO" "$IMAGE" \
            bash "$TEST_DIR/golden/ab-inside.sh" "$ENGINE" "$B_ENGINE" "$ACTUAL" -- "${args[@]}"
    fi
    echo
    if diff -r -q "$ACTUAL/a" "$ACTUAL/b" >/dev/null; then
        echo "golden ab: identical - $(basename "$ENGINE") and ${B_ENGINE#"$REPO"/} produced the same result"; exit 0
    fi
    diff -r -u "$ACTUAL/a" "$ACTUAL/b" | head -80
    echo; echo "golden ab: the two engines differ (above: a = $(basename "$ENGINE"), b = ${B_ENGINE#"$REPO"/})"; exit 1
fi
case "$ENGINE" in "$REPO"/*) ;; *) echo "golden: the engine must live in this repository ($REPO)" >&2; exit 2 ;; esac

if [[ -z "$RT" ]]; then
    if command -v podman &>/dev/null; then RT=podman
    elif command -v docker &>/dev/null; then RT=docker
    else echo "SKIP - golden: no podman or docker"; exit 0; fi
fi
# The image the engine's own --engine container uses: its tag is the
# Containerfile's content hash, so a changed toolchain is a different image.
IMAGE="$(golden_image)" \
    || { echo "golden: could not work out the image tag" >&2; exit 2; }
if ! "$RT" image inspect "$IMAGE" &>/dev/null; then
    if [[ "$MODE" == record ]]; then
        echo "golden: image $IMAGE is not built - run: holo-convert.sh --setup --engine container" >&2; exit 2
    fi
    echo "SKIP - golden: image $IMAGE not built (holo-convert.sh --setup --engine container)"; exit 0
fi

ACTUAL="$(mktemp -d)"; ACTUAL="$(cd "$ACTUAL" && pwd -P)"
trap 'rm -rf "$ACTUAL"' EXIT
user=(--user "$(id -u):$(id -g)"); [[ "$RT" == podman ]] && user=(--userns=keep-id)
"$RT" run --rm --network none "${user[@]}" --security-opt label=disable -e HOME=/tmp \
    -v "$REPO:$REPO:ro" -v "$ACTUAL:$ACTUAL" -w "$REPO" "$IMAGE" \
    bash "$TEST_DIR/golden/run-inside.sh" "$ENGINE" "$ACTUAL" "$FILTER" \
    || { echo "golden: the run inside the image failed" >&2; exit 1; }

EXPECTED="$TEST_DIR/golden/expected"
if [[ "$MODE" == record ]]; then
    if [[ -n "$FILTER" ]]; then
        for d in "$ACTUAL"/*/; do n="$(basename "$d")"; rm -rf "${EXPECTED:?}/$n"; mkdir -p "$EXPECTED"; cp -R "$d" "$EXPECTED/$n"; done
    else
        rm -rf "$EXPECTED"; mkdir -p "$EXPECTED"; cp -R "$ACTUAL"/. "$EXPECTED/"
    fi
    echo "recorded $(find "$ACTUAL" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' ') case(s) into ${EXPECTED#"$REPO"/}"
    exit 0
fi

fails=0
for d in "$ACTUAL"/*/; do
    n="$(basename "$d")"
    if [[ ! -d "$EXPECTED/$n" ]]; then echo "FAIL - $n: no expected result (record it)"; fails=$((fails + 1)); continue; fi
    if diff -r -q "$EXPECTED/$n" "$d" >/dev/null; then
        echo "ok   - $n"
    else
        echo "FAIL - $n"
        diff -r -u "$EXPECTED/$n" "$d" | sed 's/^/        /' | head -40
        fails=$((fails + 1))
    fi
done
echo
if (( fails )); then echo "golden: ${fails} case(s) differ"; exit 1; fi
echo "golden: all cases match"
