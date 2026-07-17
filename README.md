# holo-convert

A small, dependency-light **file conversion engine** — Markdown ↔ PDF / DOCX —
driven entirely by command-line flags. No TUI, no `gum`: it's the logic layer.
An interactive frontend (e.g. scomp-link's `holo-convert` menu) drives it with
flags.

## Usage

```sh
holo-convert.sh --from <md|docx> --to <pdf|docx|md> [options] <file>...
holo-convert.sh --setup [--to pdf|docx]     # install core dependencies
holo-convert.sh --with-optional             # core + optional tools
holo-convert.sh --help
```

Examples:

```sh
# Markdown → styled DOCX with a letterhead, TOC and title page
holo-convert.sh --from md --to docx --letterhead --author "ACME" \
    --toc --title-page doc.md

# Markdown → PDF (xelatex), TOC, horizontal rules stripped
holo-convert.sh --from md --to pdf --toc --strip-rules --font Helvetica doc.md

# DOCX → GitHub-flavored Markdown
holo-convert.sh --from docx --to md --md-variant gfm report.docx
```

Run `holo-convert.sh --help` for the full flag list (title-page chrome,
page size, fonts, concat, SVG rasterization, etc.).

## Dependencies

Checked at runtime and **never installed automatically** — run `--setup` to
install them, or install manually.

| Need | Requirement |
|------|-------------|
| Always | `bash` 4+, `pandoc` |
| → PDF  | a LaTeX engine (`xelatex` recommended; or lualatex/pdflatex/wkhtmltopdf/weasyprint/pagedjs-cli) |
| → DOCX | `python3` (standard library only) |
| Optional | `rsvg-convert` (SVG), `sips`/ImageMagick (GIF→PNG for PDF), fontconfig (font autodetect), `mermaid-cli` (diagrams) |

`--setup` installs the core via the OS package manager (Homebrew on macOS,
apt/dnf on Linux), scoped to `--to` when given. `--with-optional` additionally
installs the optional tools (rsvg-convert, ImageMagick, fontconfig, and — via
npm — mermaid-cli); it implies `--setup`. Neither is ever run automatically.

## Assets

Conversion assets — pandoc Lua filters, the code-block theme, the DOCX
reference documents, and title-page templates — live in `.fcc/` next to the
script and are copied into a working `./.fcc/` in the current directory on
first run (so they can be customized per project).

## Design

`holo-convert.sh` is intentionally UI-free and self-contained: flags in, files
out, clear guardrail errors when a dependency is missing. This keeps it easy to
script, test, and embed. The interactive experience is a separate concern.
