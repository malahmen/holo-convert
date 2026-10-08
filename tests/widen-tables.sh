#!/usr/bin/env bash
# Column-width checks for .fcc/pdf/widen-tables.lua (the DOCX copy is
# identical). Needs pandoc only; no LaTeX, no network.
#
# Usage: tests/widen-tables.sh   (exit 1 if any case fails)
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FILTER="${HERE}/.fcc/pdf/widen-tables.lua"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
FAILS=0

cmp -s "$FILTER" "${HERE}/.fcc/docx/widen-tables.lua" \
    || { echo "FAIL - .fcc/pdf and .fcc/docx copies of widen-tables.lua differ"; FAILS=$((FAILS + 1)); }

# Prints the column widths pandoc ends up with, rounded to 3 decimals.
cat > "$T/dump.lua" <<'LUA'
function Table(t)
  local o = {}
  for _, c in ipairs(t.colspecs) do o[#o + 1] = string.format("%.3f", c[2] or 0) end
  local f = assert(io.open(os.getenv("WIDTHS_OUT"), "w"))
  f:write(table.concat(o, " "))
  f:close()
end
LUA

# expect <name> <expected widths> — markdown table on stdin
expect() {
    local name="$1" want="$2" got
    cat > "$T/in.md"
    : > "$T/widths"
    WIDTHS_OUT="$T/widths" pandoc "$T/in.md" -t native -o /dev/null \
        --lua-filter="$FILTER" --lua-filter="$T/dump.lua" || { echo "FAIL - ${name}: pandoc failed"; FAILS=$((FAILS + 1)); return; }
    got=$(cat "$T/widths")
    if [[ "$got" == "$want" ]]; then echo "ok   - ${name}: ${got}"
    else echo "FAIL - ${name}: got '${got}', want '${want}'"; FAILS=$((FAILS + 1)); fi
}

# A long row makes pandoc assign widths (0.2 each for 5 equal separators).
LONG="this cell is long enough to push the source line past pandoc's 72 columns"

expect "one code row of two (the reported table) is left alone" "0.200 0.200 0.200 0.200 0.200" <<MD
| Who | Role | Scope | Why | Source |
| :-- | :-- | :-- | :-- | :-- |
| Pipeline identity (user-assigned managed identity) | **Key Vault Secrets User** | The project vault only | ${LONG} | \`aes-sandbox-infra\` |
| \`<team-group>\` | **Key Vault Secrets Officer** | The project vault only | The team populates the secret values | \`oracle-ebsint-infra\` |
MD

expect "code inside a sentence does not make a code cell" "0.200 0.200 0.200 0.200 0.200" <<MD
| Who | Role | Scope | Why | Source |
| :-- | :-- | :-- | :-- | :-- |
| Code base: \`aes-sandbox-infra\` | a | b | ${LONG} | c |
| Code base: \`oracle-ebsint-infra\` | a | b | c | d |
MD

expect "short identifiers in a 2-column table need no widening" "0.500 0.500" <<'MD'
| Variable | Meaning |
| :-- | :-- |
| `azdo_project_fleet_factory` | The project factory |
| `managers` | Entra ID group input |
MD

expect "identifier column sized to its longest entry" "0.325 0.169 0.169 0.169 0.169" <<MD
| Name | A | B | C | D |
| :-- | :-- | :-- | :-- | :-- |
| \`exactly_twenty_four_char\` | x | y | ${LONG} | z |
| \`short\` | x | y | z | w |
MD

expect "long identifiers are capped at 0.50" "0.500 0.167 0.167 0.167" <<MD
| Name | A | B | C |
| :-- | :-- | :-- | :-- |
| \`a_rather_long_identifier_name_of_fifty_characters_x\` | x | ${LONG} | z |
| \`another_identifier\` | x | y | z |
MD

expect "no other column is pushed below 0.10" "0.300 0.100 0.100 0.100 0.100 0.100 0.100 0.100" <<MD
| Name | A | B | C | D | E | F | G |
| :-- | :-- | :-- | :-- | :-- | :-- | :-- | :-- |
| \`a_rather_long_identifier_name_of_fifty_characters_x\` | a | b | c | d | e | f | ${LONG} |
| \`another_identifier\` | a | b | c | d | e | f | g |
MD

expect "a table without widths is evened out (fix 1)" "0.333 0.333 0.333" <<'MD'
| A | B | C |
| :-- | :-- | :-- |
| x | y | z |
MD

echo; if (( FAILS == 0 )); then echo "all passed"; else echo "${FAILS} failed"; exit 1; fi
