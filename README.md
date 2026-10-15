# holo-convert

[![ci](https://github.com/malahmen/holo-convert/actions/workflows/ci.yml/badge.svg)](https://github.com/malahmen/holo-convert/actions/workflows/ci.yml)

A small, dependency-light **file-conversion engine**: Markdown ↔ PDF / DOCX, driven entirely by command-line flags. \
No TUI, no `gum`: it's the logic layer. \
An interactive front-end (e.g. scomp-link's `holo-convert` menu) drives it with flags, you can also run it directly.

- **Flags in, files out.** Every option is a flag, nothing is prompted.
- **Guardrails, not surprises.** Dependencies are _checked_ and reported, never installed behind your back _(run `--setup` to install them explicitly)_.
- **Self-contained.** Conversion assets _(pandoc filters, code theme, DOCX reference docs, title-page templates)_ ship in `.fcc/` next to the script.
- **Python, standard library only.** `holo-convert.sh` launches the engine in `holo/`; `holo_convert.py` runs it directly. The bash engine it replaced is release [v1.0.0](https://github.com/malahmen/holo-convert/releases/tag/v1.0.0) — the same flags, messages and output, held to it by the golden harness.

---

## Quick start

```sh
git clone https://github.com/malahmen/holo-convert.git
cd holo-convert
./holo-convert.sh --setup            # install core dependencies (see below)
./holo-convert.sh --from md --to pdf --toc --title-page path/to/doc.md
./holo-convert.sh --help
```

Output lands in `./output/` (override with `-o`).

---

## Usage

```sh
holo-convert.sh --from <md|docx> --to <pdf|docx|md> [options] <file>...
holo-convert.sh --setup [--to pdf|docx]     # install core dependencies, then exit
holo-convert.sh --with-optional             # core + optional tools
holo-convert.sh --help
```

`--from` and `--to` are required; one or more input files are positional. \
Multiple files each convert independently, unless `--concat` merges them.

---

## Parameters

Legend for **Formats**: which conversions a flag affects — `md→pdf`, `md→docx`, `docx→md`. \
A flag listed for a format it doesn't apply to is simply ignored.

### General

| Flag                                           | Formats         | Default      | Effect                                                                                                      |
| ---------------------------------------------- | --------------- | ------------ | ----------------------------------------------------------------------------------------------------------- |
| `--from md\|docx`                              | all             | — (required) | Source format.                                                                                              |
| `--to pdf\|docx\|md`                           | all             | — (required) | Output format. Valid pairs: md→pdf, md→docx, docx→md.                                                       |
| `<file>...`                                    | all             | — (required) | Input file(s). Paths are relative to the current directory. The extension may be in any case (`NOTES.MD` → `NOTES.pdf`). An empty `.md` is reported as "nothing to convert" and counts as failed. |
| `-o, --output DIR`                             | all             | `./output`   | Output directory (created if missing).                                                                      |
| `--toc` / `--no-toc`                           | md→pdf, md→docx | off          | Build a table of contents from the headings. With a title page, the TOC is placed **after** the cover.      |
| `--toc-depth N`                                | md→pdf, md→docx | `3`          | Heading levels to include in the TOC.                                                                       |
| `--title-page` / `--no-title-page`             | md→pdf, md→docx | off          | Prepend a title page (see [Title pages](#title-pages)).                                                     |
| `--image PATH`                                 | md→pdf, md→docx | —            | Image shown on the title page. Non-PDF-embeddable formats (GIF, WebP, …) are auto-converted to PNG for PDF. |
| `--concat` / `--no-concat`                     | md→pdf, md→docx | off          | Merge all input files into one document; the first `#` heading becomes the title. **Skips the title page and the internal-link reconcile** (the merged document is named after the first input). |
| `--concat-pagebreak` / `--no-concat-pagebreak` | md→pdf, md→docx | on           | Insert a page break between concatenated files.                                                             |
| `--fix-links`                                  | md→pdf, md→docx | off          | Also write confident internal anchor-link fixes back into the **source** `.md`. By default only the working copy handed to pandoc is reconciled, so the output resolves and the source stays as authored. |
| `--no-check-links`                             | md→pdf, md→docx | check on     | Skip the internal anchor-link check/reconcile entirely (needs `python3`; never fatal).                       |
| `--open` / `--no-open`                         | all             | on           | Open each output in its default viewer when it is done. In a batch that is one viewer per file: `--no-open` for batches and scripts. |

### Markdown pre-passes (source clean-up)

| Flag                                           | Formats         | Default | Effect                                                                     |
| ---------------------------------------------- | --------------- | ------- | -------------------------------------------------------------------------- |
| `--substitutions` / `--no-substitutions`       | md→pdf, md→docx | off     | Smart-quote / dash substitutions and similar text tidying.                 |
| `--strip-rules` / `--no-strip-rules`           | md→pdf, md→docx | off     | Remove horizontal rules (`---`) from the output.                           |
| `--unwrap-wikilinks` / `--no-unwrap-wikilinks` | md→pdf, md→docx | off     | Convert `[[wikilinks]]` to plain text.                                     |
| `--raster-svg` / `--no-raster-svg`             | md→pdf, md→docx | off     | Rasterize local `.svg` images to PNG (needs `rsvg-convert`) so they embed. |

### PDF

| Flag                | Default           | Effect                                                                                                                               |
| ------------------- | ----------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| `--pdf-engine NAME` | auto              | PDF engine (`xelatex` preferred, then `lualatex`, `pdflatex`, `wkhtmltopdf`, `weasyprint`, `pagedjs-cli`). Must be installed. **HTML engines** (`wkhtmltopdf`/`weasyprint`/`pagedjs-cli`) skip the LaTeX pieces: no `header.tex` code/table styling, no monospace-font file, a plain centered title block instead of the LaTeX template, and pandoc's own `--toc` (placed **above** the title page). Page breaks become an HTML page-break `div`. |
| `--font NAME`       | pandoc default    | Prose font. Only installed fonts are honored; `none` forces the default.                                                             |
| `--no-tp-pagenum`   | page number shown | Hide the page number on the title page. (The PDF has no running header/footer, so only the page number is toggleable here.)          |

### DOCX

| Flag                                        | Default          | Effect                                                                    |
| ------------------------------------------- | ---------------- | ------------------------------------------------------------------------- |
| `--reference letterhead\|plain\|none\|PATH` | `plain`          | Reference document / styling — see [Reference styles](#reference-styles). |
| `--letterhead` / `--no-letterhead`          | off              | Shorthand: `--letterhead` ⇒ `--reference letterhead`.                     |
| `--page-size a4\|letter`                    | `a4`             | Page size (built-in references only).                                     |
| `--font NAME`                               | template default | Prose font (body + headings).                                             |
| `--mono NAME`                               | auto-detected    | Monospace/code font.                                                      |

#### DOCX letterhead fields (only with `--letterhead`)

| Flag                     | Effect                                          |
| ------------------------ | ----------------------------------------------- |
| `--author VALUE`         | Header "Created By" author.                     |
| `--classification VALUE` | Footer classification (e.g. `INTERNAL`).        |
| `--version VALUE`        | Version, shown in the header and footer.        |
| `--date VALUE`           | Footer date (`auto` or unset ⇒ today).          |
| `--logo PATH`            | Header logo (PNG), embedded at conversion time. |

#### DOCX title-page chrome (only with `--letterhead` + `--title-page`)

| Flag                               | Default | Effect                                                                                  |
| ---------------------------------- | ------- | --------------------------------------------------------------------------------------- |
| `--tp-header` / `--no-tp-header`   | show    | Show/hide the running header on the title page.                                         |
| `--tp-footer` / `--no-tp-footer`   | show    | Show/hide the footer on the title page.                                                 |
| `--tp-pagenum` / `--no-tp-pagenum` | show    | Show/hide the page number on the title page (only meaningful when the footer is shown). |

### DOCX → Markdown

| Flag                                     | Default | Effect                                                                           |
| ---------------------------------------- | ------- | -------------------------------------------------------------------------------- |
| `--md-variant gfm\|markdown\|commonmark` | `gfm`   | Markdown flavor of the output. Embedded media is extracted to `./output/media/`. |

### Setup

| Flag              | Effect                                                                                                                              |
| ----------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| `--setup`         | Install the **core** dependencies (scoped by `--to` if given), then exit — or, if a conversion is also given, install then convert. |
| `--with-optional` | Also install the **optional** tools (rsvg-convert, ImageMagick, fontconfig, DejaVu fonts, mermaid-cli). Implies `--setup`.          |
| `-h, --help`      | Print the flag list.                                                                                                                |

### Engine

| Flag | Effect |
| --- | --- |
| `--engine local` | **Default.** The tools installed on this host. |
| `--engine container` | The tools in a pinned image ([`container/Containerfile`](container/Containerfile)); nothing is installed here. Same flags, same output. Also `HOLO_CONVERT_ENGINE=container`. See [Container engine](#container-engine). |
| `--runtime podman\|docker` | The container runtime. Default: podman if present, else docker. Also `HOLO_CONVERT_RUNTIME`. |

---

## Configuration

Two config sources sit under the working `./.fcc/` in the current directory. They are the **only** files there that survive a run: `.fcc/docx/config` (never touched) and `.fcc/title-pages/*` (the bundled `default.*` is seeded once when missing). Everything under `.fcc/pdf/` and `.fcc/docx/` other than `config` is re-synced from the bundle next to the script on every run, so edits there are overwritten.

### `.fcc/docx/config` — DOCX letterhead defaults

`key=value` lines. \
**Only affects `md→docx` with `--letterhead`.** \
The annotated example is **not** seeded into the working `.fcc/`: copy it from the bundle next to the script, `<script-dir>/.fcc/docx/config.example`, to `./.fcc/docx/config` and edit:

| Key                      | What it sets                  | Values                    |
| ------------------------ | ----------------------------- | ------------------------- |
| `author`                 | Header "Created By"           | text                      |
| `classification`         | Footer classification         | text                      |
| `version`                | Header/footer version         | text                      |
| `date`                   | Footer date                   | text, or `auto` (⇒ today) |
| `logo`                   | Header logo                   | absolute PNG path         |
| `title_page_header`      | Header on the title page      | `true`/`false`            |
| `title_page_footer`      | Footer on the title page      | `true`/`false`            |
| `title_page_page_number` | Page number on the title page | `true`/`false`            |

**Precedence (highest wins):**

```
per-file YAML front matter  >  CLI flag  >  .fcc/docx/config  >  built-in default
```

- _Letterhead fields_ _(`author`/`classification`/`version`/`date`/`logo`)_ can be overridden per document via YAML front matter in the source `.md`:

  ```markdown
  ---
  title: Quarterly Report
  author: Platform Team
  classification: CONFIDENTIAL
  version: v2.1
  ---
  ```

  The document **title** comes from `title:` _(or the first `# H1`)_.

- _Title-page chrome_ (`title_page_*`) resolves as **flag → config → show**. \
  The page number is nested under the footer: \
  if the footer is hidden, so is the page number.

### `.fcc/title-pages/default.yaml` — title-page template

Used whenever `--title-page` is set (not in `--concat` mode, which skips the title page). Resolution per source file: \
`.fcc/title-pages/<flattened-source-path>.yaml` _(specific)_ → `default.yaml` _(fallback)_.

| Key        | What it sets                                                                                                |
| ---------- | ----------------------------------------------------------------------------------------------------------- |
| `template` | The **PDF** title-page layout (a LaTeX file, relative to the yaml), supporting `{{TITLE}}` and `{{IMAGE}}`. |
| `image`    | Optional title-page image (path relative to the yaml, or absolute). Overridden by `--image`.                |

DOCX ignores `template` and builds a **native** title page _(centered image + a `Title`-styled heading + a page break)_, because pandoc drops raw LaTeX for DOCX.

---

## How options chain together

A few flags pull in a cascade of behavior, worth understanding:

### `--letterhead`

Selects the letterhead reference doc, which gives every page a running **header** _(logo + title + version)_ and **footer** _(date · classification · `Page X / Y`)_. \
This in turn:

1. activates the **letterhead fields** (`--author`, `--classification`, `--version`, `--date`, `--logo`), resolved front-matter → flag → config;
2. stamps those into the header/footer **and** the document's core properties;
3. with `--title-page`, activates the **`--tp-*` chrome toggles** (and their `title_page_*` config keys) controlling what appears on page 1.

### `--title-page`

Seeds the bundled template and prepends a title page. For **PDF** (LaTeX engines) it renders the LaTeX `template`; for **DOCX**, and for PDF via an HTML engine, it builds a native centered image + title block. \
If `--toc` is also set, the TOC is placed **after** the title page rather than at the very top of the document (LaTeX engines and DOCX; HTML engines keep pandoc's TOC at the top). \
Ignored with `--concat`.

### `--reference` <a name="reference-styles"></a>

| Value               | Result                                                                                           |
| ------------------- | ------------------------------------------------------------------------------------------------ |
| `letterhead`        | Running header + footer (see above). Sets letterhead mode.                                       |
| `plain` _(default)_ | The built-in styling (shaded code blocks, aligned TOC, table banding) with **no** header/footer. Page size and margins as for `letterhead` (0.75" side margins). |
| `none`              | Pandoc's default DOCX styling.                                                                   |
| `PATH`              | Your own `.docx` as the pandoc reference document.                                               |

### Images

`--image` sets the title-page image; `--logo` sets the header logo. \
For PDF, images pandoc/xelatex can't embed directly (GIF, WebP, …) are auto-converted to PNG. \
Local `.svg` references in the body are embedded only when `--raster-svg` converts them to PNG first.

### Tables

Tables always span the full text width, in PDF and DOCX alike: columns without explicit widths are shared out evenly. A first column that is an identifier list (most of its cells are entirely `code`) is widened to fit its longest identifier, up to half the table, without pushing any other column below 10%; a first column that merely contains some code is left alone. In DOCX the column widths are fitted to the page's real text width (built-in references), so Word and Pages no longer stop a table short of the right margin.

### Long words, URLs and inline code (PDF)

Hyphenation is off in the PDF, so a string wider than its space used to run into the next table column or off the page. Strings longer than 20 characters now get break opportunities after `/ . - _ ? & = :` and the like, and every 10 characters where there is none; TeX still prefers to break between words. Long inline code breaks the same way, its dark background continuing across the line. Headings are left as they are (`.fcc/pdf/breakable.lua`).

### Characters beyond Latin (PDF)

The default PDF font, Latin Modern, has no Greek, Cyrillic, `⇒`, `✓`, `✗` or box drawing; those used to vanish without a word. With XeLaTeX and no `--font`, they now fall back to DejaVu Serif (letters) and DejaVu Sans (symbols), block by block; code keeps its monospace font. What no font has is reported once per file, by character:

```
[warn]  report.pdf: 3 character(s) missing from the PDF in at least one place - the PDF fonts there have no glyph for them: 你 (U+4F60) 好 (U+597D) 🚀 (U+1F680)
```

Not supported in PDF output: CJK, emoji and right-to-left scripts (Hebrew, Arabic; XeLaTeX would set them left to right) - DOCX keeps all of them. With `--font`, the font is yours and nothing falls back. The fallback needs DejaVu installed (it is, in the container image).

### Line breaks (`<br>`)

`<br>`, `<br/>` and `<br />` _(any case)_ become real line breaks in PDF and DOCX, so a table cell can hold several lines:

```markdown
| A    | B                |
| :--- | :--------------- |
| text | text <br> text   |
```

Without it, pandoc keeps `<br>` as raw HTML, which the LaTeX and Word writers drop, so the cell would read `text  text`. The same applies to a `<br>` in a paragraph.

### Page breaks (`\newpage`)

Put `\newpage` (or `\pagebreak`, `\newpage{}`, `\pagebreak{}`) on a line of its own where the next page should start:

```markdown
End of the first section.

\newpage

# Second section
```

It becomes a real page break in every output: `\newpage` in LaTeX/PDF, a Word page break in DOCX, and a page-break `<div>` for the HTML PDF engines (`wkhtmltopdf`, `weasyprint`, `pagedjs-cli`). In DOCX, a heading that follows the break starts the new page with no blank line above it.

- **Blank lines are optional.** A marker on its own line inside a paragraph splits the paragraph there.
- **It is not limited to its own line.** A `\newpage` in the middle of a sentence also breaks the page there, so keep it on its own line.
- **Code stays literal.** In a fenced code block or in inline code (`` `\newpage` ``) it is shown as text, never as a break.
- **The engine inserts the same marker itself:** between files with `--concat` _(unless `--no-concat-pagebreak`)_, after the title page, and after a title-page table of contents.

---

## Working directory & assets

- On every run the bundled `.fcc/pdf/*` and `.fcc/docx/*` assets _(filters, code theme, reference docs, post-processors)_ are synced into a working `./.fcc/` in the current directory, **overwriting** local copies so a stale filter never lingers. `monofont.tex` and `fallback.tex` are regenerated there for each `md→pdf` run.
- Only `./.fcc/docx/config` and `./.fcc/title-pages/*` are yours to edit per project: they are never overwritten (the bundled `default.yaml`/`default.md` title page is seeded only when missing).
- Output is written to `./output/` (or `-o DIR`). Both `.fcc/` and `output/` are runtime artifacts, keep them out of version control.
- Working copies (`<name>.tmp.md`, `_concat.tmp.md`) live in a folder of the run's own inside the output folder, `.holo-run-XXXXXX/`, removed when the run ends - also on Ctrl-C and `SIGTERM`. Several runs into one output folder therefore no longer overwrite each other's working copies (their outputs still share the folder: give them different names). The `.fcc/` files every run regenerates are replaced atomically.
- DOCX → Markdown: images go to `output/media/<name>/`, and the links in the `.md` are relative to it (`media/<name>/...`), so they resolve from the `.md`'s own folder.

---

## Dependencies

Checked at runtime and **never installed automatically**: run `--setup` _(or `--with-optional`)_, or install manually.

| Need     | Requirement                                                                                                        |
| -------- | ------------------------------------------------------------------------------------------------------------------ |
| Always   | `python3` 3.9+ (standard library only), `pandoc` **≥ 2.10** — the version is checked at start-up; 3.7+ uses `--syntax-highlighting`, older releases fall back to `--highlight-style` automatically (Debian/Ubuntu apt ship 2.17/3.1, both fine) |
| → PDF    | a LaTeX engine (`xelatex` recommended; or lualatex / pdflatex). wkhtmltopdf / weasyprint / pagedjs-cli are accepted with reduced styling — see `--pdf-engine` above |
| → DOCX   | nothing more: the DOCX post-steps are `python3` scripts in `.fcc/docx/`                                            |
| Optional | `rsvg-convert` (SVG), `sips`/ImageMagick (GIF→PNG for PDF), fontconfig (font autodetect), DejaVu fonts (monospace for PDF code, Courier New otherwise; the fallback for Greek, Cyrillic and symbols in PDF prose), `mermaid-cli` (diagrams) |

- `--setup` installs the **core** via whatever this host can actually use, scoped to `--to` when given:

  | Host | Uses |
  | --- | --- |
  | macOS | Homebrew |
  | Debian/Ubuntu | `apt-get` |
  | Fedora, RHEL | `dnf` |
  | **ostree desktops** (Fedora Silverblue/Kinoite, **Bazzite**) | Homebrew if installed, else `rpm-ostree install --apply-live` |
  | anything else with Homebrew | Homebrew |

  On an ostree host `/usr` is **read-only**, so `dnf` cannot install even though
  `/usr/bin/dnf` exists — which is why the check is "can this host install?"
  before "is dnf on `PATH`?", and why Homebrew is preferred there: a writable
  prefix, no `sudo`, no change to the host image, no reboot. `rpm-ostree` layers
  the package onto the image instead and says so before doing it. With neither
  available, `--setup` names both options rather than failing inside a package
  manager.
- `--with-optional` additionally installs the **optional** tools _(rsvg-convert, ImageMagick, fontconfig, the DejaVu fonts, and - via npm - mermaid-cli)_; it implies `--setup`. Fonts are never installed during a conversion: without DejaVu/Noto/Liberation Mono, PDF code falls back to Courier New with a hint.
- On macOS, `sips` (built in) covers GIF→PNG without ImageMagick.

---

## Container engine

`--engine container` runs this same script inside an image that holds only the tools:

| In the image | Not in the image |
| --- | --- |
| pandoc, XeLaTeX with every package `header.tex` and pandoc's template load, python3 + lxml, fontconfig + DejaVu, `rsvg-convert` | mermaid-cli (it needs a headless Chromium): mermaid blocks stay as code, as on any host without `mmdc` |

```sh
holo-convert.sh --setup --engine container                        # build the image once
holo-convert.sh --engine container --from md --to pdf --toc doc.md
```

- **Nothing is installed on the host** - the answer for an immutable desktop (Bazzite, Silverblue) where `--setup` would otherwise layer packages or need Homebrew, and a pinned toolchain everywhere else.
- **The engine and `.fcc/` are mounted read-only from this checkout**, not copied into the image, so the filters always match the script you run.
- **Every folder a conversion touches** - the working directory, each input's folder, the output folder - is mounted at **its own path** inside, so no argument needs rewriting.
- **No network** (`--network none`), and the container runs **as you**: outputs belong to you, not root (`--userns=keep-id` on podman, `--user` on docker). SELinux labels are left alone (`label=disable`) rather than relabelling home folders.
- **The image tag is the Containerfile's content hash.** Edit the file and the engine asks for a rebuild instead of running yesterday's tools. `HOLO_CONVERT_IMAGE` overrides the tag.
- Fonts are the image's (Latin Modern, DejaVu): a `--font` that exists only on your host falls back to pandoc's default, as it would on any host without it.

---

## Tests

```sh
tests/widen-tables.sh
tests/breakable.sh
tests/render-mermaid.sh   # mmdc found and run under a path with spaces and quotes
tests/runs.sh             # side-by-side runs, a killed run, --no-open
```

```sh
tests/run-all.sh          # every file; skips what the host cannot run
```

**The golden harness** — `tests/golden.sh` — puts 29 reference conversions
(`tests/golden/cases.txt`: PDF and DOCX with every option family, DOCX→Markdown,
`--concat`, `--fix-links`) through the engine **in the pinned tools image**, and
compares the results exactly with `tests/golden/expected/`, recorded from this
engine:

- the exit code and the engine's messages;
- every pandoc call — its arguments, and the files the engine made for it (the
  Markdown after the pre-passes, generated LaTeX headers);
- for a PDF, the LaTeX pandoc generates from those arguments (the PDF's own bytes
  carry a date; the real PDF is still built, so a LaTeX error still fails);
- and what typesetting that LaTeX reports, which the source cannot show: every
  overfull box (text wider than its space) and every character no font had;
- every DOCX as its XML parts, pretty-printed, after the Python post-steps;
- the sources after the run (`--fix-links` rewrites them).

Time is fixed (`SOURCE_DATE_EPOCH`) and paths are normalised, so two runs match
byte for byte. It exists for the Python port (`--engine` points it at another
engine), and catches any change in output along the way: a changed substitution,
a pandoc option, a skipped DOCX step and a changed message each fail it.

```sh
tests/golden.sh                    # check
tests/golden.sh record             # re-record after a deliberate change
tests/golden.sh check --case docx  # only some cases
```

`tests/golden.sh ab --engine-b PATH -- <flags> <files>` puts one real conversion
through this engine and another, and compares them the same way; `--local` runs
it on this host's tools instead of the image. To compare with the last bash
release: `git worktree add .golden-v1 v1.0.0`, then `--engine-b
.golden-v1/holo-convert.sh`.

It needs podman or docker and the image (`--setup --engine container`); without
them it prints SKIP, so `tests/run-all.sh` still works anywhere. CI builds the
image and runs it as its own job.

**26 checks** in `tests/container-engine.sh` over `--engine container`, against a
stub runtime that records what it is asked: which image, which mounts (each at
its own path, the engine read-only), no network, as the caller rather than
root, `--engine`/`--runtime`/`--setup` never reaching the inner run, a missing
image refused with the fix named, and a different tag once the Containerfile
changes. Nothing is built; a real conversion in the image was checked by hand.

**14 checks** in `tests/pkg-manager.sh` over the `--setup` host selection above,
driven against a fabricated `PATH` and a fake ostree marker — so hosts this
machine is not can still be checked, and nothing is installed. The case it
exists for is the one that was broken: `dnf` present *and* the host immutable
must not choose `dnf`.

**8 checks** over `.fcc/pdf/widen-tables.lua`, the filter that decides table
column widths. It needs **pandoc and nothing else** — no LaTeX, no network —
and skips itself with a message where pandoc is absent rather than reporting
eight failures that are really one missing dependency.

The first check is that the `.fcc/pdf` and `.fcc/docx` copies of the filter are
byte-identical, since they are meant to be and nothing enforces it. The rest
assert the widths pandoc actually ends up with: that an identifier column is
sized to its longest entry, capped at `0.50`, that no other column is pushed
below `0.10`, that a table with no widths at all is evened out, and that code
*inside a sentence* does not make the cell a code cell.

Both of those last two are measured by reading the colspecs back out of
pandoc's native AST, not by eyeballing a PDF.

## CI

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs on every push to
`main`, every pull request, and on demand:

| Step | What |
| --- | --- |
| `pandoc` | `apt-get install pandoc` — the suite's only dependency |
| `shellcheck` | `-S warning` on `holo-convert.sh` and `tests/*.sh` — globbed, so the next test file is covered automatically |
| Python | `python3 -m compileall -q holo holo_convert.py .fcc` — the engine and the DOCX stampers are syntax-checked |
| tests | `tests/run-all.sh` |

No LaTeX in CI, so the PDF path is not exercised there. It needs a TeX
distribution, and a conversion that produces a PDF is checked by running one.

## Design

`holo-convert.sh` is intentionally UI-free and self-contained: flags in, files out, clear guardrail errors when a dependency is missing. \
That keeps it easy to script, test, and embed. \
The interactive experience is a separate concern, this repo is just the engine.

## License

[MIT](LICENSE) © 2026 malahmen.
