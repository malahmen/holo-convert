#!/usr/bin/env bash
# --engine container, against a stub runtime that records what it was asked.
#
# Nothing is built or run: `docker`/`podman` here are recording stubs, so this
# checks the decisions the engine makes - which image, which mounts, as whom,
# with which arguments - not pandoc inside the image. (A real conversion in
# the image was verified by hand: see the README's "Container engine".)
#
# What it protects:
#   - the inner run never sees --engine/--runtime/--setup, and runs locally;
#   - every folder a conversion touches is mounted at its own path, the engine
#     read-only, with no network and as the caller, not root;
#   - a missing image is an error that names the fix, and --setup builds it;
#   - the image tag follows the Containerfile, so an edit asks for a rebuild.
set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
ENG="${HOLO_CONVERT:-${HERE}/holo-convert.sh}"
[[ -f "$ENG" ]] || { echo "holo-convert.sh not found at $ENG" >&2; exit 1; }

T="$(mktemp -d)"; trap 'rm -rf "$T"' EXIT
T="$(cd "$T" && pwd -P)"
FAILS=0
check() { local d="$1"; shift; if "$@"; then echo "ok   - $d"; else echo "FAIL - $d"; FAILS=$((FAILS + 1)); fi; }
has()   { grep -qF -- "$1" "$2"; }
lacks() { ! grep -qF -- "$1" "$2"; }
no_arg() { ! grep -qxF -- "$1" "$2"; }   # no line is exactly $1 (one argument per line)

# The stub: `image inspect` succeeds only once `build` has run; every call is
# logged one argument per line, between markers.
mkdir -p "$T/bin"
for rt in docker podman; do
    cat > "$T/bin/$rt" <<'EOF'
#!/usr/bin/env bash
{ echo "=== $(basename "$0")"; printf '%s\n' "$@"; } >> "$STUB_LOG"
case "${1:-} ${2:-}" in
    "image inspect") [[ -f "$STUB_BUILT" ]] ;;
    build*)          : > "$STUB_BUILT" ;;
    *)               exit 0 ;;
esac
EOF
    chmod +x "$T/bin/$rt"
done
export PATH="$T/bin:$PATH" STUB_LOG="$T/log" STUB_BUILT="$T/built"
unset HOLO_CONVERT_ENGINE HOLO_CONVERT_RUNTIME HOLO_CONVERT_IMAGE

mkdir -p "$T/work" "$T/docs"; echo "# hi" > "$T/docs/a.md"
run() { : > "$STUB_LOG"; (cd "$T/work" && bash "$ENG" "$@") > "$T/out" 2>&1; }

echo "## image"
run --engine container --runtime docker --from md --to pdf "$T/docs/a.md"
check "no image: refused, naming the fix" has "--setup --engine container" "$T/out"
check "  and nothing is run" no_arg "run" "$STUB_LOG"
run --setup --engine container --runtime docker
check "--setup builds from container/Containerfile" has "${HERE}/container/Containerfile" "$STUB_LOG"
tag="$(grep -m1 '^localhost/holo-convert-tools:' "$STUB_LOG")"
check "  tagged by the Containerfile's content" test -n "$tag"
check "  and stops there when no files are given" no_arg "run" "$STUB_LOG"

echo "## run"
run --engine container --runtime docker --from md --to pdf -o "$T/out-dir" --toc "$T/docs/a.md"
args="$T/args"; sed -n '/^run$/,$p' "$STUB_LOG" > "$args"
check "the image is the built one" has "$tag" "$args"
check "no network" has "none" "$args"
check "the working folder, at its own path" has "${T}/work:${T}/work" "$args"
check "the input's folder, at its own path" has "${T}/docs:${T}/docs" "$args"
check "the output folder is created and mounted" has "${T}/out-dir:${T}/out-dir" "$args"
check "  (it exists on the host)" test -d "$T/out-dir"
check "the engine, read-only" has "${HERE}:${HERE}:ro" "$args"
check "as the caller, not root" has "$(id -u):$(id -g)" "$args"
check "the inner run is local" has "HOLO_CONVERT_ENGINE=local" "$args"
check "the inner run gets the conversion flags" has "--toc" "$args"
check "  but not --engine" lacks "--engine" "$args"
check "  nor --runtime" lacks "--runtime" "$args"
check "  nor --setup" lacks "--setup" "$args"

echo "## podman"
run --engine container --runtime podman --setup --from md --to pdf "$T/docs/a.md"
sed -n '/^run$/,$p' "$STUB_LOG" > "$args"
check "podman keeps the caller's uid with keep-id" has "--userns=keep-id" "$args"
check "  instead of --user" no_arg "--user" "$args"

echo "## from the checkout itself"
: > "$STUB_LOG"; (cd "$HERE" && bash "$ENG" --engine container --runtime docker --from md --to pdf "$T/docs/a.md") > "$T/out" 2>&1
sed -n '/^run$/,$p' "$STUB_LOG" > "$args"
check "the checkout is mounted once, read-write" has "${HERE}:${HERE}" "$args"
check "  not a second time read-only" lacks "${HERE}:${HERE}:ro" "$args"

echo "## flags"
: > "$STUB_LOG"; (cd "$T/work" && bash "$ENG" --engine local --from md) > "$T/out" 2>&1
check "--engine local is accepted (and the local checks run)" has "missing --to" "$T/out"
(cd "$T/work" && bash "$ENG" --engine cloud --from md) > "$T/out" 2>&1
check "an unknown engine is refused" has "--engine must be local or container" "$T/out"
(cd "$T/work" && HOLO_CONVERT_ENGINE=container bash "$ENG" --runtime docker --from md --to pdf "$T/docs/a.md") > "$T/out" 2>&1
check "HOLO_CONVERT_ENGINE selects the engine too" has "localhost/holo-convert-tools:" "$STUB_LOG"

echo "## the tag follows the Containerfile"
mkdir -p "$T/copy/container"; cp "$ENG" "${HERE}/holo_convert.py" "$T/copy/"; cp -R "${HERE}/.fcc" "${HERE}/holo" "$T/copy/"
cp "${HERE}/container/Containerfile" "$T/copy/container/"
echo "# an edit" >> "$T/copy/container/Containerfile"
: > "$STUB_LOG"; (cd "$T/work" && bash "$T/copy/holo-convert.sh" --setup --engine container --runtime docker) > "$T/out" 2>&1
new="$(grep -m1 '^localhost/holo-convert-tools:' "$STUB_LOG")"
check "an edited Containerfile means a different image" test "$new" != "$tag"

echo
if (( FAILS )); then echo "${FAILS} check(s) failed"; exit 1; fi
echo "all checks passed"
