# wip/ — holo-convert's engine in Python

**Work in progress. Nothing uses it by default:** `holo-convert.sh` at the
repository root is still the engine, and scomp-link still calls it.

The same engine - flags, defaults, messages, exit codes, the pandoc calls it
makes and the files it writes - in Python (standard library only). pandoc,
TeX, the Lua filters and the `.fcc/docx/*.py` helpers stay as they are; only
the bash around them is replaced. The gain is portability and tests: no
bash-4-on-a-3.2-Mac, no GNU/BSD `sed`/`awk`/`find` differences.

## Trying it

```sh
wip/holo-convert.sh --from md --to pdf doc.md          # any command, as with the bash engine
python3 wip/holo_convert.py --from md --to docx doc.md  # the same, without the launcher
```

## How it is checked

```sh
tests/golden.sh check --engine wip/holo-convert.sh     # the 20 reference cases, in the pinned image
tests/golden.sh ab -- <flags> <files>                  # one real conversion through both engines
tests/golden.sh ab --local -- <flags> <files>          # the same, on this host's own tools
```

The 20 reference cases compare the exit code, every message, every pandoc
call with the files the engine made for it, the LaTeX behind each PDF and the
DOCX XML after the post-steps - byte for byte with the bash engine. All 20
match. Breaking the port on purpose (a substitution, a skipped DOCX step, the
`&` escape in a title) fails them.

`ab` takes any real command: both engines run it from their own working
folders and are recorded and compared the same way. The owner's own
letterhead DOCX command (every pre-pass, title page with image, logo,
Helvetica) is identical between the two, in the image and on a Mac.

## Layout

| Bash (`holo-convert.sh`) | Python (`holo/`) |
| --- | --- |
| messages, `run_step` | `ui.py` |
| globals | `state.py` |
| `cd && pwd`, `basename`, `$(...)`, sed ranges, awk records | `sh.py` |
| `ensure_fcc_*`, `resolve_*` | `assets.py` |
| `fc_has_family`, `detect_mono_font`, `font_installed` | `fonts.py` |
| substitutions, rules, wikilinks, SVG, title page | `prepass.py` |
| DOCX post-steps, letterhead, link reconcile | `docx.py` |
| `convert_*`, `run_concat`, `run_conversions` | `convert.py` |
| `guard_deps`, pandoc version | `deps.py` |
| `--setup` | `setup.py` |
| `--engine container` | `container.py` |
| `parse_args`, `main_engine`, usage | `cli.py` |

## Before it replaces the bash engine

- Use it for real for a while (scomp-link can be pointed at it).
- Then swap: `holo-convert.sh` becomes the launcher and `wip/` goes away; the
  reference cases keep guarding it.
