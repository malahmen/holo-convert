#!/usr/bin/env bash
# Checks for render-mermaid.lua (the .fcc/pdf and .fcc/docx copies): mmdc is
# found and run even when its path has a space or a quote - a HOME such as
# "/home/Jo Ann's" - and its arguments arrive whole. The command line used to
# be pasted together unquoted for a shell. Needs pandoc only: mmdc is a stub
# that records its arguments and writes a placeholder PNG.
#
# Usage: tests/render-mermaid.sh   (exit 1 if any check fails)
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
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

if [[ "$(cat "$HERE/.fcc/pdf/render-mermaid.lua")" == "$(cat "$HERE/.fcc/docx/render-mermaid.lua")" ]]; then
    echo "ok   - .fcc/pdf and .fcc/docx copies of render-mermaid.lua are identical"
else
    echo "FAIL - .fcc/pdf and .fcc/docx copies of render-mermaid.lua differ"; FAILS=$((FAILS + 1))
fi

# The filter looks for mmdc as a mise shim under $HOME first.
H="$T/Jo Ann's home"
SHIMS="$H/.local/share/mise/shims"
mkdir -p "$SHIMS"
cat > "$SHIMS/mmdc" <<STUB
#!/bin/sh
for a in "\$@"; do printf '[%s]\n' "\$a"; done > "$T/mmdc-args"
while [ \$# -gt 0 ]; do [ "\$1" = -o ] && printf 'png' > "\$2"; shift; done
STUB
chmod +x "$SHIMS/mmdc"

printf '```mermaid\ngraph TD; A-->B\n```\n' > "$T/doc.md"
for copy in pdf docx; do
    rm -f "$T/mmdc-args"
    HOME="$H" pandoc "$T/doc.md" --lua-filter="$HERE/.fcc/$copy/render-mermaid.lua" -t native \
        > "$T/out" 2> "$T/err"
    check "$copy: mmdc under a HOME with a space and a quote runs" [ -s "$T/mmdc-args" ]
    check "  its arguments arrive whole" grep -qx '\[--scale\]' "$T/mmdc-args"
    check "  the input path is one argument" grep -q '^\[.*_mermaid/diagram_1.mmd\]$' "$T/mmdc-args"
    check "  the diagram becomes an image" grep -q 'diagram_1.png' "$T/out"
    check "  with no warning" bash -c '! grep -q WARNING "$1"' _ "$T/err"
done

# A failing mmdc: the block stays as code, with a warning naming the cause.
printf '#!/bin/sh\necho "parse error on line 1" >&2\nexit 1\n' > "$SHIMS/mmdc"
HOME="$H" pandoc "$T/doc.md" --lua-filter="$HERE/.fcc/pdf/render-mermaid.lua" -t native > "$T/out" 2> "$T/err"
check "a failing mmdc leaves the code block" grep -q 'CodeBlock' "$T/out"
check "  and warns" grep -q 'mmdc failed for diagram 1' "$T/err"

echo
if (( FAILS )); then echo "${FAILS} check(s) failed"; exit 1; fi
echo "all checks passed"
