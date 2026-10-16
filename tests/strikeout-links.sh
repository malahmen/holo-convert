#!/usr/bin/env bash
# Checks for .fcc/pdf/strikeout-links.lua: a link inside ~~strikeout~~ no
# longer puts \href inside soul's \st, which aborted the whole PDF ("Argument
# of \hyper@n@rmalise has an extra }"; Kamino item 82). Needs pandoc only; no
# LaTeX, no network. (That the result typesets was checked with the
# container engine on the two Kamino reports that failed.)
#
# Usage: tests/strikeout-links.sh   (exit 1 if any case fails)
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FILTER="${HERE}/.fcc/pdf/strikeout-links.lua"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
FAILS=0

if ! command -v pandoc >/dev/null 2>&1; then
    echo "SKIP - pandoc is not installed; these checks need it (and nothing else)" >&2
    exit 0
fi

check() {
    local desc="$1"; shift
    if "$@"; then echo "ok   - $desc"; else echo "FAIL - $desc"; FAILS=$((FAILS + 1)); fi
}
# latex <markdown> [filter]: the LaTeX body pandoc writes, into $T/out.
latex() { printf '%s\n' "$1" | pandoc --from=markdown --to=latex ${2:+--lua-filter="$2"} > "$T/out"; }
has() { grep -qF -- "$1" "$T/out"; }
# Does some \st{...} contain an \href before it closes? (one line is enough here)
href_in_st() { grep -qE '\\st\{[^}]*\\href' "$T/out"; }

DOC='~~answers [converter-services](cs.md) To-decide 1 ("does it pay?")~~'
latex "$DOC"
check "without the filter, \\href sits inside \\st (the failure)" href_in_st
latex "$DOC" "$FILTER"
check "with it, never" bash -c '! grep -qE "\\\\st\\{[^}]*\\\\href" "$1"' _ "$T/out"
check "  the link carries its own strike" has '\href{cs.md}{\st{converter-services}}'
check "  the text before it stays one struck run" has '\st{answers }'
check "  and the text after it too" has '\st{ To-decide 1'

latex '~~old **bold [deep](d.md) text** end~~' "$FILTER"
check "a link nested in bold inside the strike is reached" has '\href{d.md}{\st{deep}}'
check "  and still bold" has '\textbf{'

latex '~~struck, no link at all~~' "$FILTER"
check "a span with no link is left exactly as pandoc writes it" has '\st{struck, no link at all}'

latex 'plain [link](x.md) text' "$FILTER"
check "a link outside any strike is untouched" has '\href{x.md}{link}'

echo
if (( FAILS )); then echo "${FAILS} check(s) failed"; exit 1; fi
echo "all checks passed"
