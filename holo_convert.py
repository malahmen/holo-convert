#!/usr/bin/env python3
"""holo-convert's entry point. holo-convert.sh runs this; so can you."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from holo.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
