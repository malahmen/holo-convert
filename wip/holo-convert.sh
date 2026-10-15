#!/usr/bin/env bash
# The Python engine behind the bash engine's name and calling convention, so
# anything that runs `bash holo-convert.sh ...` - the golden harness, scomp-link -
# can be pointed at it unchanged:
#
#   tests/golden.sh check --engine wip/holo-convert.sh
#
# HOLO_CONVERT_PYTHON picks the interpreter (default: python3).
exec "${HOLO_CONVERT_PYTHON:-python3}" "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/holo_convert.py" "$@"
