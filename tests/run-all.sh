#!/usr/bin/env bash
# Run every tests/*.sh except this one, and exit non-zero if any fails.
# No network. Checks that need a tool the host lacks skip themselves and say so.
set -uo pipefail

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
failed=()
for t in "$TEST_DIR"/*.sh; do
    name="$(basename "$t")"
    [[ "$name" == run-all.sh ]] && continue
    if out="$(bash "$t" 2>&1)"; then
        if grep -q '^SKIP' <<< "$out"; then echo "SKIP  ${name}"; grep -m1 '^SKIP' <<< "$out" | sed 's/^/        /'
        else echo "PASS  ${name}"; fi
    else
        echo "FAIL  ${name}"; grep -E '^ *FAIL' <<< "$out" | sed 's/^/        /'
        failed+=("$name")
    fi
done
echo
if (( ${#failed[@]} )); then echo "${#failed[@]} test file(s) failed: ${failed[*]}"; exit 1; fi
echo "all test files passed"
