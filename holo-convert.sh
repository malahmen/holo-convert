#!/usr/bin/env bash
# holo-convert - Markdown <-> PDF / DOCX, flag-driven.
#
# The engine is Python (holo/, standard library only); this launcher keeps the
# name and calling convention every caller already uses - scomp-link, the
# golden harness, your own scripts: `holo-convert.sh --from md --to pdf doc.md`.
# Run holo_convert.py directly if you prefer. --help lists everything.
#
# HOLO_CONVERT_PYTHON picks the interpreter (default: python3, any 3.9+).
# The bash engine this replaced is release v1.0.0.
exec "${HOLO_CONVERT_PYTHON:-python3}" "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/holo_convert.py" "$@"
