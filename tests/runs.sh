#!/usr/bin/env bash
# Runs side by side and runs cut short: each run works in a folder of its own
# inside the output folder (holo/convert.py work_dir), removed when it ends -
# also on SIGTERM. Before, every run used fixed names there (_concat.tmp.md,
# <name>.tmp.md), so two runs into one folder overwrote each other's working
# copies, and a killed run left them behind. Plus --no-open.
#
# Needs pandoc only (Markdown to DOCX; no LaTeX, no network). The PATH is
# given stubs for `open`/`xdg-open` (record instead of opening a viewer) and,
# in one check, a pandoc that hangs.
#
# Usage: tests/runs.sh   (exit 1 if any check fails)
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HC="$HERE/holo-convert.sh"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
FAILS=0

if ! command -v pandoc >/dev/null 2>&1; then
    echo "SKIP - pandoc is not installed; these checks need it (and nothing else)" >&2
    exit 0
fi
REAL_PANDOC="$(command -v pandoc)"

check() {
    local desc="$1"; shift
    if "$@"; then echo "ok   - $desc"; else echo "FAIL - $desc"; FAILS=$((FAILS + 1)); fi
}
mkdir -p "$T/bin"
for viewer in open xdg-open; do
    printf '#!/bin/sh\necho "$*" >> "%s/opened"\n' "$T" > "$T/bin/$viewer"
    chmod +x "$T/bin/$viewer"
done
export PATH="$T/bin:$PATH"
docx_text() { unzip -p "$1" word/document.xml 2>/dev/null; }

# --- side by side ------------------------------------------------------------------
# Six --concat runs at once into one output folder, each with its own two
# inputs. They used to share output/_concat.tmp.md.
W="$T/side"; mkdir -p "$W"
for i in 1 2 3 4 5 6; do
    printf '# Run %s\n\nMARK-%s-first\n' "$i" "$i" > "$W/r${i}a.md"
    printf 'MARK-%s-second\n' "$i" > "$W/r${i}b.md"
done
pids=()
for i in 1 2 3 4 5 6; do
    (cd "$W" && "$HC" --from md --to docx --reference none --no-open --concat "r${i}a.md" "r${i}b.md" \
        > "$T/side-$i.log" 2>&1) &
    pids+=("$!")
done
rcs=0
for p in "${pids[@]}"; do wait "$p" || rcs=$((rcs + 1)); done
check "six --concat runs into one folder all succeed" [ "$rcs" -eq 0 ]
mixed=0
for i in 1 2 3 4 5 6; do
    text="$(docx_text "$W/output/r${i}a.docx")"
    [[ "$text" == *"MARK-$i-first"* && "$text" == *"MARK-$i-second"* ]] || mixed=$((mixed + 1))
    for j in 1 2 3 4 5 6; do
        [[ "$j" == "$i" ]] && continue
        [[ "$text" == *"MARK-$j-"* ]] && mixed=$((mixed + 1))
    done
done
check "  each document holds its own two inputs and nothing of the others'" [ "$mixed" -eq 0 ]
check "  no working folder is left behind" bash -c '! ls -a "$1" | grep -q "^\.holo-run-"' _ "$W/output"
check "  nor any working copy" bash -c '! find "$1" -name "*.tmp.md" | grep -q .' _ "$W/output"

# --- cut short ----------------------------------------------------------------------
# A pandoc that hangs on the conversion (but answers --version, which the
# dependency check asks), then SIGTERM to the engine.
W="$T/killed"; mkdir -p "$W/bin"
printf '#!/bin/sh\ncase "$1" in --version|--list-*) exec "%s" "$@" ;; esac\nexec sleep 60\n' "$REAL_PANDOC" > "$W/bin/pandoc"
chmod +x "$W/bin/pandoc"
printf '# Doc\n\ntext\n' > "$W/doc.md"
(cd "$W" && PATH="$W/bin:$PATH" exec "$HC" --from md --to docx --reference none --no-open doc.md > "$T/killed.log" 2>&1) &
engine=$!
for _ in $(seq 1 100); do
    ls -a "$W/output" 2>/dev/null | grep -q '^\.holo-run-' && break
    sleep 0.1
done
check "a running conversion has its working folder" bash -c 'ls -a "$1" | grep -q "^\.holo-run-"' _ "$W/output"
kill -TERM "$engine" 2>/dev/null
wait "$engine" 2>/dev/null
pkill -f "sleep 60" 2>/dev/null
check "  SIGTERM removes it" bash -c '! ls -a "$1" | grep -q "^\.holo-run-"' _ "$W/output"

# --- --no-open ------------------------------------------------------------------------
W="$T/open"; mkdir -p "$W"
printf '# Doc\n\ntext\n' > "$W/doc.md"
rm -f "$T/opened"
(cd "$W" && "$HC" --from md --to docx --reference none --no-open doc.md > /dev/null 2>&1)
check "--no-open opens nothing" [ ! -e "$T/opened" ]
(cd "$W" && "$HC" --from md --to docx --reference none doc.md > /dev/null 2>&1)
# xdg-open is started in the background (open_file): give it a moment.
for _ in $(seq 1 20); do [ -s "$T/opened" ] && break; sleep 0.1; done
check "without it, the output is opened (as before)" grep -q "doc.docx" "$T/opened"

echo
if (( FAILS )); then echo "${FAILS} check(s) failed"; exit 1; fi
echo "all checks passed"
