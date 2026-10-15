"""DOCX post-processing, the letterhead, and the internal-link reconcile.

The post-steps are the bundled .fcc/docx/*.py helpers, run with `python3` from
PATH exactly as the bash engine runs them; only the orchestration is here.
"""
import locale
import os
import time

from . import assets, sh
from .prepass import extract_title, parse_yaml_field
from .state import DOCX_CONFIG, S
from .ui import info, warn


def _python() -> bool:
    return sh.which("python3")


def fold_docx_pagebreaks(docx: str) -> int:
    if not _python():
        info("python3 not found — leaving page-break paragraphs as-is (a blank line may show above headings).")
        return 0
    script = assets.synced_helper("fold_pagebreaks.py")
    if not script:
        warn("fold_pagebreaks.py not found — skipping page-break tidy.")
        return 0
    return sh.run(["python3", script, docx])


def shade_docx_tables(docx: str) -> int:
    if not _python():
        info("python3 not found — leaving table rows unbanded.")
        return 0
    script = assets.synced_helper("shade_tables.py")
    if not script:
        warn("shade_tables.py not found — skipping table shading.")
        return 0
    return sh.run(["python3", script, docx])


def apply_docx_fonts(docx: str) -> int:
    if not S.docx_font and not S.docx_mono:
        return 0
    if not _python():
        info("python3 not found — leaving DOCX fonts as the template defaults.")
        return 0
    script = assets.synced_helper("apply_docx_fonts.py")
    if not script:
        warn("apply_docx_fonts.py not found — skipping DOCX font apply.")
        return 0
    return sh.run(["python3", script, docx, S.docx_font, S.docx_mono])


def layout_docx(docx: str) -> int:
    if not _python():
        return 0
    script = assets.resolve_docx_asset("docx_layout.py")
    if not script:
        return 0
    return sh.run(["python3", script, docx, "--page-size", S.docx_page_size])


def caption_docx_figures(docx: str) -> int:
    if not _python():
        return 0
    script = assets.resolve_docx_asset("caption_figures.py")
    if not script:
        return 0
    return sh.run(["python3", script, docx])


def _today() -> str:
    """`date +'%d %B %Y' | sed 's/^0//'`, in the user's locale as `date` is."""
    try:
        locale.setlocale(locale.LC_TIME, "")
    except locale.Error:
        pass
    s = time.strftime("%d %B %Y")
    return s[1:] if s.startswith("0") else s


def stamp_docx_letterhead(docx: str, source: str) -> int:
    if not _python():
        warn("python3 not found — letterhead tokens left unstamped.")
        return 0
    script = assets.resolve_docx_asset("stamp_docx_tokens.py")
    if not script:
        warn("stamp_docx_tokens.py not found — skipping letterhead.")
        return 0
    title = extract_title(source)
    author = parse_yaml_field(source, "author") or S.docx_author
    classification = parse_yaml_field(source, "classification") or S.docx_classification
    version = parse_yaml_field(source, "version") or S.docx_version
    date = parse_yaml_field(source, "date") or S.docx_date
    logo = sh.expand_tilde(parse_yaml_field(source, "logo") or S.docx_logo)
    if logo and not os.path.isfile(logo):
        warn(f"Logo not found: {logo} — skipping.")
        logo = ""
    if not date or date == "auto":
        date = _today()
    vsuffix = f", {version}" if version else ""
    args = ["python3", script, docx, "--title", title, "--version-suffix", vsuffix,
            "--author", author, "--date", date, "--classification", classification]
    if logo:
        args += ["--logo", logo]
    if S.use_title_page:
        show = lambda v: "show" if v == "true" else "hide"   # noqa: E731
        args += ["--tp-header", show(S.tp_header), "--tp-footer", show(S.tp_footer),
                 "--tp-pagenum", show(S.tp_pagenum)]
    return sh.run(args)


def docx_post(step, *args):
    """A styling pass: a failure is reported and pandoc's output kept."""
    rc = step(*args)
    if rc != 0:
        warn(f"{step.__name__} failed (exit {rc}) — output kept as produced by pandoc.")


# --- letterhead ---------------------------------------------------------------------------

def docx_cfg(key: str) -> str:
    """A value from .fcc/docx/config (key=value); empty if absent."""
    if not os.path.isfile(DOCX_CONFIG):
        return ""
    for line in sh.read(DOCX_CONFIG).split("\n"):
        if line.startswith(key + "="):
            return line[len(key) + 1:].replace("\r", "")
    return ""


def _tp_resolve(current: str, key: str) -> str:
    """An explicit --tp-*/--no-tp-* wins; else the config key; else show."""
    if current:
        return current
    return "false" if docx_cfg(key).lower() in ("false", "no", "0", "off", "hide") else "true"


def resolve_letterhead():
    """Flags win; then .fcc/docx/config. The date defaults to today, stamped later."""
    S.docx_author = S.docx_author or docx_cfg("author")
    S.docx_classification = S.docx_classification or docx_cfg("classification")
    S.docx_version = S.docx_version or docx_cfg("version")
    S.docx_date = S.docx_date or docx_cfg("date")
    if S.docx_date == "auto":
        S.docx_date = ""
    S.docx_logo = sh.expand_tilde(S.docx_logo or docx_cfg("logo"))
    if S.docx_logo and not os.path.isfile(S.docx_logo):
        warn(f"Configured logo not found: {S.docx_logo}")
        S.docx_logo = ""
    S.tp_header = _tp_resolve(S.tp_header, "title_page_header")
    S.tp_footer = _tp_resolve(S.tp_footer, "title_page_footer")
    S.tp_pagenum = _tp_resolve(S.tp_pagenum, "title_page_page_number")
    if S.tp_footer == "false":
        S.tp_pagenum = "false"
    info(f"Letterhead — author='{S.docx_author}' classification='{S.docx_classification}' "
         f"version='{S.docx_version}' logo='{S.docx_logo or 'none'}'")
    info(f"Title-page chrome — header={S.tp_header} footer={S.tp_footer} page#={S.tp_pagenum}")


# --- internal links -----------------------------------------------------------------------

def reconcile_internal_links(tmp: str, src: str):
    """Anchors that match no heading jump to the top in Word/Pages. Fix the
    working copy so the OUTPUT resolves; --fix-links also writes confident
    fixes to the source. Never fatal."""
    if not S.check_links:
        return
    if not (_python() and sh.which("pandoc")):
        return
    script = assets.resolve_docx_asset("check_links.py")
    if not script:
        return
    sh.run(["python3", script, "--reconcile", tmp])
    if S.fix_links:
        sh.run(["python3", script, "--fix", src])
