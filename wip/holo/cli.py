"""holo-convert's command line - the Python of parse_args / main_engine.

The same flags, defaults, messages and exit codes as holo-convert.sh, so the
golden harness and scomp-link cannot tell the two engines apart.
"""
import os
import signal
import sys

from . import assets, container, convert, docx, fonts, setup
from .deps import guard_deps
from .state import DOCX_DEFAULT_REFERENCE, DOCX_PLAIN_REFERENCE, S
from .ui import Fatal, echo_blank, edie, enote, error

USAGE = r"""holo-convert — file conversion engine (Markdown <-> PDF / DOCX)

USAGE
  holo-convert.sh --from <fmt> --to <fmt> [options] <file>...
  holo-convert.sh --setup [--to pdf|docx]
  holo-convert.sh --help

REQUIRED
  --from md|docx                     source format
  --to   pdf|docx|md                 output format
  <file>...                          one or more input files

COMMON
  -o, --output DIR                   output directory (default: ./output)
  --[no-]toc [--toc-depth N]         table of contents (depth default 3)
  --[no-]title-page [--image PATH]   add a title page (optional image); skipped by --concat
  --[no-]substitutions               smart quote/dash substitutions
  --[no-]strip-rules                 strip horizontal rules
  --[no-]unwrap-wikilinks            unwrap [[wikilinks]]
  --[no-]raster-svg                  rasterize SVG images
  --[no-]concat                      combine inputs into one document (first # heading
                                       becomes the title; no title page / link reconcile)
  --[no-]concat-pagebreak            page break between concatenated inputs (default on)
  --fix-links                        also write confident anchor-link fixes to the SOURCE
                                       (default only reconciles the output copy)
  --no-check-links                   skip the internal-link reconcile/check (on by default)

DOCX
  --reference letterhead|plain|none|PATH   reference doc (default: plain)
  --[no-]letterhead                  shorthand for --reference letterhead (plain)
  --page-size a4|letter
  --font NAME   --mono NAME          prose / monospace fonts
  --author|--classification|--version|--date|--logo VALUE   letterhead fields
  --[no-]tp-header --[no-]tp-footer --[no-]tp-pagenum        title-page chrome

PDF
  --pdf-engine xelatex|lualatex|pdflatex|wkhtmltopdf|weasyprint|pagedjs-cli
                                     (HTML engines: no LaTeX header/title template;
                                     pandoc-native --toc lands above the title page)
  --font NAME                        prose font

DOCX->MD
  --md-variant gfm|markdown|commonmark

SETUP
  --setup                            install dependencies, then exit (or, if a
                                     conversion is also given, install then run)
  --with-optional                    also install the optional tools (rsvg,
                                     ImageMagick, fontconfig, DejaVu fonts,
                                     mermaid-cli); implies --setup
    holo-convert.sh --setup                install the core (pandoc, LaTeX, python3)
    holo-convert.sh --setup --to docx       install just the DOCX deps
    holo-convert.sh --with-optional         install the core + all optional tools
    holo-convert.sh --setup --from md --to pdf doc.md   install PDF deps, then convert

By default (no --setup) engine dependencies are CHECKED but never installed.

ENGINE
  --engine local|container           local (default): the tools on this host.
                                     container: the tools in a pinned image
                                     (container/Containerfile); nothing is
                                     installed here. Same flags, same output.
                                     Also: HOLO_CONVERT_ENGINE.
  --runtime podman|docker            container runtime (default: podman if
                                     present, else docker). Also: HOLO_CONVERT_RUNTIME.
    holo-convert.sh --setup --engine container                 build the image once
    holo-convert.sh --engine container --from md --to pdf doc.md
  The image holds no mermaid-cli: mermaid blocks stay as code there.
"""


def usage():
    sys.stderr.write(USAGE)
    sys.stderr.flush()


class _Usage(Exception):
    pass


# Flags with a value: (attribute, value transform). Booleans: (attribute, value).
_VALUE = {
    "--from": "source_format", "--to": "output_format", "-o": "output_dir", "--output": "output_dir",
    "--toc-depth": "toc_depth", "--image": "title_img_cache", "--reference": "engine_reference",
    "--page-size": "docx_page_size", "--font": "engine_font", "--mono": "docx_mono",
    "--pdf-engine": "pdf_engine", "--author": "docx_author", "--classification": "docx_classification",
    "--version": "docx_version", "--date": "docx_date", "--logo": "docx_logo", "--md-variant": "md_variant",
}
_BOOL = {
    "--toc": ("use_toc", True), "--no-toc": ("use_toc", False),
    "--title-page": ("use_title_page", True), "--no-title-page": ("use_title_page", False),
    "--substitutions": ("apply_substitutions", True), "--no-substitutions": ("apply_substitutions", False),
    "--strip-rules": ("strip_rules", True), "--no-strip-rules": ("strip_rules", False),
    "--unwrap-wikilinks": ("unwrap_wikilinks", True), "--no-unwrap-wikilinks": ("unwrap_wikilinks", False),
    "--raster-svg": ("raster_svg", True), "--no-raster-svg": ("raster_svg", False),
    "--concat": ("concat", True), "--no-concat": ("concat", False),
    "--concat-pagebreak": ("concat_pagebreak", True), "--no-concat-pagebreak": ("concat_pagebreak", False),
    "--letterhead": ("docx_letterhead", True), "--no-letterhead": ("docx_letterhead", False),
    "--tp-header": ("tp_header", "true"), "--no-tp-header": ("tp_header", "false"),
    "--tp-footer": ("tp_footer", "true"), "--no-tp-footer": ("tp_footer", "false"),
    "--tp-pagenum": ("tp_pagenum", "true"), "--no-tp-pagenum": ("tp_pagenum", "false"),
    "--fix-links": ("fix_links", True), "--no-check-links": ("check_links", False),
    "--setup": ("setup_deps", True),
}


def parse_args(args):
    files, i = [], 0
    while i < len(args):
        a = args[i]
        if a in _VALUE:
            if i + 1 >= len(args):
                edie(f"{a} needs a value (try --help)")
            setattr(S, _VALUE[a], args[i + 1])
            i += 2
        elif a in _BOOL:
            attr, value = _BOOL[a]
            setattr(S, attr, value)
            i += 1
        elif a == "--with-optional":
            S.with_optional = S.setup_deps = True
            i += 1
        elif a in ("-h", "--help"):
            raise _Usage()
        elif a == "--":
            files += args[i + 1:]
            break
        elif a.startswith("-"):
            edie(f"unknown flag: {a} (try --help)")
        else:
            files.append(a)
            i += 1
    if files:
        S.selected_files = files


def main_engine(args) -> int:
    parse_args(args)
    if S.setup_deps and not S.selected_files:
        setup.setup_deps()
        return 0
    if not S.source_format:
        edie("missing --from <md|docx>")
    if not S.output_format:
        edie("missing --to <pdf|docx|md>")
    if not S.selected_files:
        edie("no input files given (pass one or more paths)")
    if S.setup_deps:
        setup.setup_deps()

    # Deferred --font: the prose font of the chosen target ("none" = pandoc's default).
    if S.engine_font:
        if S.engine_font == "none":
            S.engine_font = ""
        if S.output_format == "pdf":
            S.pdf_font = S.engine_font
        else:
            S.docx_font = S.engine_font
    guard_deps()

    pair = f"{S.source_format}->{S.output_format}"
    if pair == "md->pdf":
        if not S.pdf_engine:
            S.pdf_engine = "xelatex" if "xelatex" in S.available_engines else S.available_engines[0]
        elif S.pdf_engine not in S.available_engines:
            edie(f"--pdf-engine '{S.pdf_engine}' not available (have: {' '.join(S.available_engines)}).")
        if S.is_latex_engine():
            assets.ensure_pdf_config()
            fonts.detect_mono_font()
        else:
            assets.ensure_fcc_pdf_assets()
            enote(f"HTML PDF engine '{S.pdf_engine}': LaTeX header/monospace font/title template are skipped; TOC and page breaks use pandoc's HTML output.")
        if S.pdf_font and not fonts.font_installed(S.pdf_font):
            enote(f"font '{S.pdf_font}' not installed — using pandoc default.")
            S.pdf_font = ""
    elif pair == "md->docx":
        if not assets.ensure_fcc_docx_assets():
            return 1          # set -e in the bash engine: no reference doc, no run
        ref = S.engine_reference
        if ref == "letterhead":
            S.docx_reference_doc, S.docx_letterhead = DOCX_DEFAULT_REFERENCE, True
        elif ref == "plain":
            S.docx_reference_doc, S.docx_letterhead = DOCX_PLAIN_REFERENCE, False
        elif ref == "none":
            S.docx_reference_doc, S.docx_letterhead = "", False
        elif ref == "":
            S.docx_reference_doc = DOCX_DEFAULT_REFERENCE if S.docx_letterhead else DOCX_PLAIN_REFERENCE
        else:
            if not os.path.isfile(ref):
                edie(f"--reference file not found: {ref}")
            S.docx_reference_doc, S.docx_letterhead = ref, False
        if S.docx_letterhead:
            docx.resolve_letterhead()
        if not S.docx_mono:
            fonts.detect_docx_mono()

    # The title page needs the bundled template seeded into the working .fcc/.
    if S.use_title_page and S.source_format == "md":
        assets.ensure_fcc_title_pages()
    return 0 if convert.run_conversions() else 1


def engine_preparse(args):
    """--engine / --runtime out of the arguments (up to a `--`)."""
    engine = os.environ.get("HOLO_CONVERT_ENGINE") or "local"
    runtime = os.environ.get("HOLO_CONVERT_RUNTIME") or ""
    rest, i = [], 0
    while i < len(args):
        a = args[i]
        if a == "--engine":
            if i + 1 >= len(args):
                edie("--engine needs a value: local or container")
            engine = args[i + 1]
            i += 2
        elif a == "--runtime":
            if i + 1 >= len(args):
                edie("--runtime needs a value: podman or docker")
            runtime = args[i + 1]
            i += 2
        elif a == "--":
            rest += args[i:]
            break
        else:
            rest.append(a)
            i += 1
    if engine not in ("local", "container"):
        edie(f"--engine must be local or container, got '{engine}'.")
    return engine, runtime, rest


def _interrupted(_sig, _frame):
    echo_blank()
    enote("Interrupted.")
    sys.exit(130)


def main(argv=None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    signal.signal(signal.SIGINT, _interrupted)
    signal.signal(signal.SIGTERM, _interrupted)
    if not args or args[0] in ("-h", "--help"):
        usage()
        return 0
    try:
        engine, runtime, rest = engine_preparse(args)
        if engine == "container":
            return container.run_in_container(rest, runtime)
        return main_engine(rest)
    except _Usage:
        usage()
        return 0
    except Fatal as exc:
        error(str(exc))
        return 1
