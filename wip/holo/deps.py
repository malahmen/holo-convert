"""Guardrail checks: pandoc and its version, the PDF engines, python3 for DOCX."""
import re

from . import sh
from .state import PANDOC_MIN, S
from .ui import edie, enote, warn

_ENGINES = ("xelatex", "lualatex", "pdflatex", "wkhtmltopdf", "weasyprint", "pagedjs-cli")


def detect_pandoc_version():
    out = sh.capture(["pandoc", "--version"]) or ""
    words = out.split("\n", 1)[0].split()
    v = words[1] if len(words) > 1 else ""
    m = re.match(r"[0-9]+(\.[0-9]+)*", v)
    S.pandoc_version = v if m else ""


def pandoc_at_least(major: int, minor: int) -> bool:
    v = S.pandoc_version
    if not v:
        return False
    maj = v.split(".", 1)[0]
    mi = v.split(".")[1] if "." in v else "0"
    try:
        maj_n, min_n = int(maj), int(re.match(r"[0-9]*", mi).group(0) or 0)
    except ValueError:
        return False
    return maj_n > major or (maj_n == major and min_n >= minor)


def highlight_theme_arg(path: str) -> str:
    """--syntax-highlighting replaced --highlight-style in pandoc 3.7."""
    return f"--syntax-highlighting={path}" if pandoc_at_least(3, 7) else f"--highlight-style={path}"


def guard_deps():
    if not sh.which("pandoc"):
        edie("pandoc not found — install it (https://pandoc.org/installing.html), or run this tool via scomp-link which can install it for you.")
    detect_pandoc_version()
    if not S.pandoc_version:
        warn(f"could not read the pandoc version — need {PANDOC_MIN}+; continuing anyway.")
    else:
        major, minor = PANDOC_MIN.split(".")
        if not pandoc_at_least(int(major), int(minor)):
            edie(f"pandoc {S.pandoc_version} is too old — need {PANDOC_MIN}+ (https://pandoc.org/installing.html).")
    pair = f"{S.source_format}->{S.output_format}"
    if pair == "md->pdf":
        found = [e for e in _ENGINES if sh.which(e)]
        if not found:
            edie("no PDF engine found (need one of: xelatex, lualatex, pdflatex, wkhtmltopdf, weasyprint, pagedjs-cli).")
        S.available_engines = found
    elif pair == "md->docx":
        if not sh.which("python3"):
            edie("python3 not found — required for DOCX post-processing (letterhead, layout, fonts).")
    elif pair == "docx->md":
        pass
    else:
        edie(f"conversion '{S.source_format} -> {S.output_format}' is not supported.")
    enote(f"dependencies OK for {S.source_format}->{S.output_format} (pandoc {S.pandoc_version or '?'}).")
