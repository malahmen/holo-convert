#!/usr/bin/env bash
# Checks for .fcc/pdf/breakable.lua: where long words, URLs and inline code get
# their break opportunities, and what is left alone. Needs pandoc only; no
# LaTeX, no network. (Whether the result typesets without overflow is the
# golden harness's job: case pdf-long, and its "typeset" record.)
#
# Usage: tests/breakable.sh   (exit 1 if any case fails)
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FILTER="${HERE}/.fcc/pdf/breakable.lua"
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
# latex <markdown>: the LaTeX body pandoc writes with the filter, into $T/out.
latex() { printf '%s\n' "$1" | pandoc --from=markdown --to=latex --lua-filter="$FILTER" > "$T/out"; }
has() { grep -qF -- "$1" "$T/out"; }
lacks() { ! grep -qF -- "$1" "$T/out"; }

latex 'See https://registry.example.internal/v2/projects/platform for it.'
check "a long URL breaks after its separators" has 'https:\hcbreak{}/\hcbreak{}/\hcbreak{}registry.\hcbreak{}example.\hcbreak{}internal/'
check "  short words around it are untouched" has 'See'

latex 'Donaudampfschifffahrtselektrizitätenhauptbetriebswerk'
check "a long word without separators splits every 10 characters, at the dearer \\hcsplit" \
    has 'Donaudampf\hcsplit{}schifffahr\hcsplit{}tselektriz'
check "  never at the cheaper \\hcbreak" lacks '\hcbreak'

latex 'A short_identifier and ordinary words stay whole.'
check "strings of 20 characters or fewer are left alone" lacks '\hc'

latex 'Run `holo-convert.sh --engine container --to pdf` now.'
check "long inline code becomes pieces" has '\hccodepart'
check "  the first piece keeps its left padding" has '\hccodepart{}{\kern-\fboxsep{}}{holo-'
check "  later pieces overlap the one before by a hair" has '\hcbreak{}\kern-.25pt{}\hccodepart{\kern-\fboxsep{}}'
check "  the last piece keeps its right padding" grep -qE '\\hccodepart\{\\kern-\\fboxsep\{\}\}\{\}\{pdf\}' "$T/out"
check "  no plain \\texttt is left for it" lacks '\texttt'

latex 'Code with specials: `a_b{c}%d#e&f$g~h^i\j_and_more_text`.'
check "pieces escape as pandoc escapes a whole code span" has '{a\_}\hcbreak{}'
check "  braces, percent, hash, ampersand and dollar escaped" has '\{c\}'
check "  percent escaped" has '\%'
check "  backslash escaped" has '\textbackslash'

latex '`short_code`'
check "short inline code stays one \\texttt" has '\texttt{short\_code}'

latex '# A heading with averyveryverylongwordthatstaysuntouched'
check "headings are left alone (bookmark and TOC text)" lacks '\hcbreak'

# Inside ~~strikeout~~ (soul's \st) nothing is split: its breaks and boxes
# abort the PDF there (item 101).
latex '~~call `some_long_inline_code_identifier_here` and https://registry.example.internal/v2/projects/platform end~~'
check "inside a strike, long code and a long URL are left whole" lacks '\hc'
check "  the code is still ordinary \\texttt" has '\texttt{some\_long\_inline\_code\_identifier\_here}'
latex 'Outside, `some_long_inline_code_identifier_here` still breaks.'
check "  outside a strike it still breaks" has '\hccodepart'

latex '[the registry](https://registry.example.internal/v2/projects/platform-engineering)'
check "a link keeps its target whole" has '\href{https://registry.example.internal/v2/projects/platform-engineering}'

printf '%s\n' 'https://registry.example.internal/v2/projects/platform' \
    | pandoc --from=markdown --to=docx --lua-filter="$FILTER" -o "$T/out.docx"
check "DOCX is untouched (the filter only acts on LaTeX)" bash -c '! unzip -p "$1" word/document.xml | grep -q hcbreak' _ "$T/out.docx"

echo
if (( FAILS )); then echo "${FAILS} check(s) failed"; exit 1; fi
echo "all checks passed"
