"""Messages - byte for byte what holo-convert.sh prints.

Unlike protocol-droid, this engine always colours its prefixes, terminal or
not; the golden harness strips the colours before comparing. Everything goes
to stderr, so stdout stays capture-clean (the only stdout writes are the
blank lines the bash engine echoes).
"""
import sys


class Fatal(Exception):
    """edie: print the message, exit 1."""


def _err(text: str) -> None:
    sys.stderr.write(text)
    sys.stderr.flush()


def enote(msg: str) -> None:
    _err(f"\033[0;36m[info]\033[0m  {msg}\n")


info = enote


def success(msg: str) -> None:
    _err(f"\033[0;32m[ok]\033[0m    {msg}\n")


def warn(msg: str) -> None:
    _err(f"\033[0;33m[warn]\033[0m  {msg}\n")


def header(msg: str) -> None:
    _err(f"\n\033[0;36m== {msg} ==\033[0m\n")


def error(msg: str) -> None:
    _err(f"\033[0;31m[error]\033[0m {msg}\n")


def edie(msg: str):
    raise Fatal(msg)


def echo_blank() -> None:
    """`echo ""` - to stdout, as the bash engine does."""
    sys.stdout.write("\n")
    sys.stdout.flush()
