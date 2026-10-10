#!/usr/bin/env bash
# Which installer --setup picks, on hosts this machine is not.
#
# The bug this exists for: _engine_pkg_manager's predecessor asked "is dnf on
# PATH?" before "can this host install anything at all". On an ostree desktop
# (Fedora Silverblue/Kinoite, Bazzite) /usr/bin/dnf EXISTS while /usr is
# read-only, so it chose — every time, on the author's own machine — the one
# branch guaranteed to fail, and failed inside dnf rather than saying what was
# wrong. Homebrew in a writable prefix was right there and never considered,
# because brew was Darwin-only.
#
# Nothing here installs anything: the engine's two selection functions are
# eval'd out and driven against a fabricated PATH and a fake ostree marker.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENG="${HOLO_CONVERT:-${HERE}/holo-convert.sh}"
[[ -f "$ENG" ]] || { echo "holo-convert.sh not found at $ENG" >&2; exit 1; }

T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT

# Pulled out ONCE, here, where the real PATH still exists. Each case below
# replaces PATH wholesale so the selection cannot see this machine's own
# package managers — which also means no sed, no findmnt, nothing external
# that is not deliberately stubbed.
FUNCS="$(sed -n '/^_engine_host_immutable() {/,/^}/p;/^_engine_pkg_manager() {/,/^}/p' "$ENG")"
[[ -n "$FUNCS" ]] || { echo "could not extract the selection functions from $ENG" >&2; exit 1; }
FAILS=0
check() { local d="$1" want="$2" got="$3"
    if [[ "$got" == "$want" ]]; then echo "ok   - ${d}: ${got}"
    else echo "FAIL - ${d}: got '${got}', want '${want}'"; FAILS=$((FAILS + 1)); fi; }

# pick <os> <immutable:0|1> <tool>... -> the manager chosen
# A bin directory holding only <tool>..., and nothing else on PATH, so the
# selection cannot see this machine's real package managers.
pick() {
    local os="$1" immutable="$2"; shift 2
    local d="$T/bin.$RANDOM"; mkdir -p "$d"
    local t
    for t in "$@"; do printf '#!/bin/sh\nexit 0\n' > "$d/$t"; chmod +x "$d/$t"; done
    # uname is stubbed too: the point is to test hosts this one is not.
    printf '#!/bin/sh\nprintf "%%s" "%s"\n' "$os" > "$d/uname"; chmod +x "$d/uname"
    local marker="$T/no-such-marker"
    [[ "$immutable" == 1 ]] && { marker="$d/ostree-booted"; : > "$marker"; }
    (
        PATH="$d"; export PATH
        HC_OSTREE_MARKER="$marker"; export HC_OSTREE_MARKER
        eval "$FUNCS"
        _engine_pkg_manager || true
    )
}

echo "## an ostree host — the case that was broken"
# dnf present and the host immutable: the old code picked dnf. It must not.
check "immutable, dnf + brew"      brew           "$(pick Linux 1 dnf brew)"
check "immutable, dnf only"        none-immutable "$(pick Linux 1 dnf)"
check "immutable, dnf + rpm-ostree" rpm-ostree    "$(pick Linux 1 dnf rpm-ostree)"
check "immutable, brew beats rpm-ostree" brew     "$(pick Linux 1 dnf rpm-ostree brew)"
check "immutable, nothing usable"  none-immutable "$(pick Linux 1)"

echo "## a mutable Linux still behaves as before"
check "apt wins where present"     apt            "$(pick Linux 0 apt-get dnf brew)"
check "dnf on a traditional Fedora" dnf           "$(pick Linux 0 dnf)"
check "brew is a last resort"       brew          "$(pick Linux 0 brew)"
check "nothing at all"              none          "$(pick Linux 0)"

echo "## macOS and the rest"
check "Darwin uses brew"           brew           "$(pick Darwin 0 brew apt-get dnf)"
check "Darwin without brew says so" none-darwin   "$(pick Darwin 0 apt-get dnf)"
check "an unsupported OS is named" unsupported-os "$(pick FreeBSD 0 brew)"

echo "## the marker is not the only signal"
# A read-only /usr with no ostree marker must still count as immutable, via
# findmnt — that is what covers an image-based host that is not ostree.
ro_via_findmnt() {
    local d="$T/fm"; mkdir -p "$d"
    printf '#!/bin/sh\nprintf "%%s" "ro,relatime,seclabel"\n' > "$d/findmnt"; chmod +x "$d/findmnt"
    printf '#!/bin/sh\nprintf "%%s" "Linux"\n' > "$d/uname"; chmod +x "$d/uname"
    printf '#!/bin/sh\nexit 0\n' > "$d/dnf"; chmod +x "$d/dnf"
    ( PATH="$d"; export PATH
      HC_OSTREE_MARKER="$T/absent"; export HC_OSTREE_MARKER
      eval "$FUNCS"
      _engine_pkg_manager || true )
}
check "a read-only /usr without the marker" none-immutable "$(ro_via_findmnt)"
# And the inverse: rw must not be read as ro, or every apt box breaks.
rw_via_findmnt() {
    local d="$T/fm2"; mkdir -p "$d"
    printf '#!/bin/sh\nprintf "%%s" "rw,relatime,seclabel"\n' > "$d/findmnt"; chmod +x "$d/findmnt"
    printf '#!/bin/sh\nprintf "%%s" "Linux"\n' > "$d/uname"; chmod +x "$d/uname"
    printf '#!/bin/sh\nexit 0\n' > "$d/apt-get"; chmod +x "$d/apt-get"
    ( PATH="$d"; export PATH
      HC_OSTREE_MARKER="$T/absent"; export HC_OSTREE_MARKER
      eval "$FUNCS"
      _engine_pkg_manager || true )
}
check "a writable /usr is not immutable" apt "$(rw_via_findmnt)"

echo
if (( FAILS )); then echo "${FAILS} failed"; exit 1; fi
echo "all passed"
