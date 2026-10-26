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
# The document text of a .docx. python3, not unzip: the engine needs python3
# anyway, and unzip is missing from some hosts and from the tools image, where
# this check then failed instead of reading the file.
docx_text() { python3 -c 'import sys, zipfile; sys.stdout.write(zipfile.ZipFile(sys.argv[1]).read("word/document.xml").decode())' "$1" 2>/dev/null; }

# Is there a .holo-run-* working folder under $1? A glob rather than
# `ls -a | grep` (SC2010, which failed CI): the prefix is literal, it needs no
# subprocess, and it is right whether or not nullglob is set — unmatched, the
# pattern itself is the single iteration and fails the -e test.
# Negation gets its own helper because `check "desc" ! fn ...` would try to run
# `!` as a command.
has_run_dir() { local d; for d in "$1"/.holo-run-*; do [[ -e "$d" ]] && return 0; done; return 1; }
no_run_dir()  { ! has_run_dir "$1"; }

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
check "  no working folder is left behind" no_run_dir "$W/output"
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
    has_run_dir "$W/output" && break
    sleep 0.1
done
check "a running conversion has its working folder" has_run_dir "$W/output"
kill -TERM "$engine" 2>/dev/null
wait "$engine" 2>/dev/null
pkill -f "sleep 60" 2>/dev/null
check "  SIGTERM removes it" no_run_dir "$W/output"

# --- one output per input -------------------------------------------------------------
# Inputs that share a base name get path-derived names (a/notes.md ->
# a_notes.docx). That name could itself be another input's (a_notes.md), and
# the base names were compared case-sensitively (a/Notes.md and b/notes.md
# both wrote Notes.docx on a case-insensitive disk): one output silently
# replaced another and the run said every input succeeded (Kamino item 191).
W="$T/names"; mkdir -p "$W/a" "$W/b" "$W/c" "$W/d"
printf 'MARK-a-dir\n' > "$W/a/notes.md"
printf 'MARK-b-dir\n' > "$W/b/notes.md"
printf 'MARK-flat\n'  > "$W/a_notes.md"
printf 'MARK-c-upper\n' > "$W/c/Notes.md"
printf 'MARK-d-lower\n' > "$W/d/notes.md"
names() { (cd "$W" && rm -rf output && "$HC" --from md --to docx --reference none --no-open "$@" > "$T/names.log" 2>&1); }
holds() { [[ "$(docx_text "$W/output/$1")" == *"$2"* ]]; }

names a/notes.md b/notes.md
check "two inputs with one base name both succeed" [ "$?" -eq 0 ]
check "  each in its own path-derived output" bash -c '[[ -f "$1/a_notes.docx" && -f "$1/b_notes.docx" ]]' _ "$W/output"
check "  holding its own text" bash -c "$(declare -f docx_text holds); W='$W'; holds a_notes.docx MARK-a-dir && holds b_notes.docx MARK-b-dir"

names a/notes.md b/notes.md a_notes.md
rc=$?
check "a path-derived name that is another input's output: the run fails" [ "$rc" -ne 0 ]
check "  and says so" grep -q "1 failed" "$T/names.log"
check "  the first input keeps that output, nothing overwrote it" bash -c "$(declare -f docx_text holds); W='$W'; holds a_notes.docx MARK-a-dir && ! holds a_notes.docx MARK-flat"
check "  the others are still converted" bash -c "$(declare -f docx_text holds); W='$W'; holds b_notes.docx MARK-b-dir"

# The same with the flat file's name in another case: one file on a
# case-insensitive disk, so refused on every disk (the same command must not
# pass on Linux and lose a file on macOS).
printf 'MARK-flat-upper\n' > "$W/a_Notes.md"
names a/notes.md b/notes.md a_Notes.md
check "  also when the two names differ only in case" [ "$?" -ne 0 ]
rm "$W/a_Notes.md"

names c/Notes.md d/notes.md
check "base names that differ only in case both succeed" [ "$?" -eq 0 ]
check "  in two outputs, also on a case-insensitive disk" bash -c "$(declare -f docx_text holds); W='$W'; holds c_Notes.docx MARK-c-upper && holds d_notes.docx MARK-d-lower"

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
