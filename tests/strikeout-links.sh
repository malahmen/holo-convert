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
# The same, with inline math as either pandoc writes it: $x$ (3.9) or \(x\) (3.1).
has_math() { has "${1//@/\$}" || has "$(sed -e 's/@/\\(/' -e 's/@/\\)/' <<< "$1")"; }
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

# A strike inside the struck link: soul cannot nest \st (item 101). Every \st
# must close before the next one opens.
latex '~~a [link with ~~inner~~ strike](q.md) end~~' "$FILTER"
check "a strike inside a struck link is dissolved: no \\st inside \\st" bash -c '! grep -qE "\\\\st\\{[^}]*\\\\st\\{" "$1"' _ "$T/out"
check "  the link's text is struck once, whole" has '\href{q.md}{\st{link with inner strike}}'

# A strike inside a run of plain text (no link anywhere): bold inside the
# strike holding another strike. soul cannot nest \st (item 205).
latex '~~a **b ~~c~~ d** e~~' "$FILTER"
check "a strike inside bold inside a strike is dissolved: no \\st inside \\st" bash -c '! grep -qE "\\\\st\\{[^}]*\\\\st\\{" "$1"' _ "$T/out"
check "  the whole run is struck once" has '\st{a \textbf{b c d} e}'

# A strike directly in the run of a struck span with a link
# (strikeout-links.lua's run branch). Markdown cannot write that nesting, so
# the document is given as pandoc's native AST.
nat='[Para [Strikeout [Str "a",Space,Strikeout [Str "b"],Space,Link ("",[],[]) [Str "l"] ("x.md",""),Space,Str "c"]]]'
printf '%s\n' "$nat" | pandoc --from=native --to=latex --lua-filter="$FILTER" > "$T/out"
check "a strike directly inside a struck run is dissolved into it" has '\st{a b }\href{x.md}{\st{l}}\st{ c}'

# Inline math and characters fallback.tex sets in DejaVu (Greek here): soul
# takes them apart and fails ("Extra }, or forgotten $"; "Reconstruction
# failed"). Each goes into an \mbox, which soul strikes through whole.
latex '~~math $x^2$ end~~' "$FILTER"
check "inline math inside a strike is boxed" has_math '\st{math \mbox{@x^2@} end}'
latex '~~greek αβγ δ end~~' "$FILTER"
check "Greek inside a strike is boxed, each run on its own" has '\st{greek \mbox{αβγ} \mbox{δ} end}'
latex '~~mixed Ωmega and ✓ tick~~' "$FILTER"
check "  only the fallback characters of a word, and symbols too" has '\st{mixed \mbox{Ω}mega and \mbox{✓} tick}'
latex '~~see [αβ link](g.md) $y$~~' "$FILTER"
check "  inside a struck link as well" has_math '\href{g.md}{\st{\mbox{αβ} link}}\st{ \mbox{@y@}}'
latex 'no strike αβ $x$ ~~café~~' "$FILTER"
check "outside a strike, and Latin-1 inside one, nothing is boxed" bash -c '! grep -qF "\\mbox" "$1"' _ "$T/out"

# The filter's copy of fallback.tex's Unicode ranges must match holo/fonts.py.
same_ranges() {
    python3 - "$HERE" "$FILTER" <<'PY'
import re, sys
sys.path.insert(0, sys.argv[1])
from holo.fonts import FALLBACK_LETTERS, FALLBACK_SYMBOLS
lua = open(sys.argv[2], encoding="utf-8").read()
table = lua[lua.index("local FALLBACK = {"):lua.index("\n}", lua.index("local FALLBACK = {"))]
got = [(int(a, 16), int(b, 16)) for a, b in re.findall(r"\{ 0x([0-9A-Fa-f]+), 0x([0-9A-Fa-f]+) \}", table)]
sys.exit(0 if got == list(FALLBACK_LETTERS + FALLBACK_SYMBOLS) else 1)
PY
}
check "the filter's fallback ranges are holo/fonts.py's" same_ranges

latex 'plain [link](x.md) text' "$FILTER"
check "a link outside any strike is untouched" has '\href{x.md}{link}'

echo
if (( FAILS )); then echo "${FAILS} check(s) failed"; exit 1; fi
echo "all checks passed"
