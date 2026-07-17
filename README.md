# holo-convert

A small, dependency-light **file-conversion engine**: Markdown ↔ PDF / DOCX, driven entirely by command-line flags. \
No TUI, no `gum`: it's the logic layer. \
An interactive front-end (e.g. scomp-link's `holo-convert` menu) drives it with flags, you can also run it directly.

- **Flags in, files out.** Every option is a flag, nothing is prompted.
- **Guardrails, not surprises.** Dependencies are _checked_ and reported, never installed behind your back _(run `--setup` to install them explicitly)_.
- **Self-contained.** Conversion assets _(pandoc filters, code theme, DOCX reference docs, title-page templates)_ ship in `.fcc/` next to the script.

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
| `<file>...`                                    | all             | — (required) | Input file(s). Paths are relative to the current directory.                                                 |
| `-o, --output DIR`                             | all             | `./output`   | Output directory (created if missing).                                                                      |
| `--toc` / `--no-toc`                           | md→pdf, md→docx | off          | Build a table of contents from the headings. With a title page, the TOC is placed **after** the cover.      |
| `--toc-depth N`                                | md→pdf, md→docx | `3`          | Heading levels to include in the TOC.                                                                       |
| `--title-page` / `--no-title-page`             | md→pdf, md→docx | off          | Prepend a title page (see [Title pages](#title-pages)).                                                     |
| `--image PATH`                                 | md→pdf, md→docx | —            | Image shown on the title page. Non-PDF-embeddable formats (GIF, WebP, …) are auto-converted to PNG for PDF. |
| `--concat` / `--no-concat`                     | md→pdf, md→docx | off          | Merge all input files into one document; the first `#` heading becomes the title.                           |
| `--concat-pagebreak` / `--no-concat-pagebreak` | md→pdf, md→docx | on           | Insert a page break between concatenated files.                                                             |

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
| `--pdf-engine NAME` | auto              | LaTeX/HTML engine (`xelatex` preferred, then `lualatex`, `pdflatex`, `wkhtmltopdf`, `weasyprint`, `pagedjs-cli`). Must be installed. |
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
| `--with-optional` | Also install the **optional** tools (rsvg-convert, ImageMagick, fontconfig, mermaid-cli). Implies `--setup`.                        |
| `-h, --help`      | Print the flag list.                                                                                                                |

---

## Configuration

Two config sources sit under `.fcc/` _(copied into a working `./.fcc/` in the current directory on first run, so you can customize them per project)_.

### `.fcc/docx/config` — DOCX letterhead defaults

`key=value` lines. \
**Only affects `md→docx` with `--letterhead`.** \
Copy `.fcc/docx/config.example` to `.fcc/docx/config` and edit:

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

Used whenever `--title-page` is set. Resolution per source file: \
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

Seeds the bundled template and prepends a title page. For **PDF** it renders the LaTeX `template`, for **DOCX** it builds a native centered image + `Title` heading. \
If `--toc` is also set, the TOC is placed **after** the title page rather than at the very top of the document.

### `--reference` <a name="reference-styles"></a>

| Value               | Result                                                                                           |
| ------------------- | ------------------------------------------------------------------------------------------------ |
| `letterhead`        | Running header + footer (see above). Sets letterhead mode.                                       |
| `plain` _(default)_ | The built-in styling (shaded code blocks, aligned TOC, table banding) with **no** header/footer. |
| `none`              | Pandoc's default DOCX styling.                                                                   |
| `PATH`              | Your own `.docx` as the pandoc reference document.                                               |

### Images

`--image` sets the title-page image; `--logo` sets the header logo. \
For PDF, images pandoc/xelatex can't embed directly (GIF, WebP, …) are auto-converted to PNG. \
Local `.svg` references in the body are embedded only when `--raster-svg` converts them to PNG first.

---

## Working directory & assets

- On first run in a directory, the canonical `.fcc/` assets are copied to a working `./.fcc/` there, edit those _(config, title-page templates, code theme, filters)_ to customize a specific project. \
- Output is written to `./output/` (or `-o DIR`). Both `.fcc/` and `output/` are runtime artifacts, keep them out of version control.

---

## Dependencies

Checked at runtime and **never installed automatically**: run `--setup` _(or `--with-optional`)_, or install manually.

| Need     | Requirement                                                                                                        |
| -------- | ------------------------------------------------------------------------------------------------------------------ |
| Always   | `bash` 4+, `pandoc`                                                                                                |
| → PDF    | a LaTeX engine (`xelatex` recommended; or lualatex / pdflatex / wkhtmltopdf / weasyprint / pagedjs-cli)            |
| → DOCX   | `python3` (standard library only)                                                                                  |
| Optional | `rsvg-convert` (SVG), `sips`/ImageMagick (GIF→PNG for PDF), fontconfig (font autodetect), `mermaid-cli` (diagrams) |

- `--setup` installs the **core** via the OS package manager _(Homebrew on macOS, apt/dnf on Linux)_, scoped to `--to` when given.
- `--with-optional` additionally installs the **optional** tools _(rsvg-convert, ImageMagick, fontconfig, and - via npm - mermaid-cli)_; it implies `--setup`.
- On macOS, `sips` (built in) covers GIF→PNG without ImageMagick.

---

## Design

`holo-convert.sh` is intentionally UI-free and self-contained: flags in, files out, clear guardrail errors when a dependency is missing. \
That keeps it easy to script, test, and embed. \
The interactive experience is a separate concern, this repo is just the engine.
