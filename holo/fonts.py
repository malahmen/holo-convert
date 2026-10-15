"""Font detection - the PDF monospace font, the DOCX ones, "is it installed?"."""
import os
import subprocess
import platform

from . import sh
from .state import FCC_DIR, S
from .ui import info, success, warn

_fc_families = None
_macos_families = None


def _fc():
    """fontconfig's families, loaded once, one per line, trimmed. Captured
    whole rather than piped into grep: under pipefail a grep that exits on the
    first match could SIGPIPE fc-list into a false "missing"."""
    global _fc_families
    if _fc_families is None:
        _fc_families = []
        if sh.which("fc-list"):
            raw = sh.capture(["fc-list", ":", "family"], stderr=subprocess.DEVNULL) or ""
            _fc_families = [p.strip(sh.SPACE) for line in raw.split("\n") for p in line.split(",")]
    return _fc_families


def reset_fc():
    global _fc_families
    _fc_families = None


def fc_has_family(family: str) -> bool:
    fams = _fc()
    if not any(fams):
        return False
    low = family.lower()
    return any(f.lower() == low for f in fams)


def _macos():
    """The macOS registry: fontconfig does not always index the system fonts,
    so Helvetica can be absent from fc-list while XeLaTeX loads it by name."""
    global _macos_families
    if _macos_families is None:
        _macos_families = []
        if sh.which("system_profiler"):
            raw = sh.capture(["system_profiler", "SPFontsDataType"], stderr=subprocess.DEVNULL) or ""
            names = set()
            for line in raw.split("\n"):
                s = line.lstrip(sh.SPACE)
                if s.startswith("Family:"):
                    names.add(s[len("Family:"):].lstrip(sh.SPACE))
            _macos_families = sorted(names)
    return _macos_families


def font_installed(family: str) -> bool:
    if fc_has_family(family):
        return True
    if platform.system() == "Darwin":
        low = family.lower()
        return any(f.lower() == low for f in _macos())
    if sh.which("fc-list"):
        return False          # fc-list gave a definitive "no"
    return True               # no detector: stay optimistic


def _exists_any(*paths) -> bool:
    return any(os.path.exists(p) for p in paths)


def detect_mono_font():
    """Write .fcc/pdf/monofont.tex: DejaVu Sans Mono, Noto Mono, Liberation
    Mono, else Courier New. Path-based on macOS (XeLaTeX's font database lags
    behind cask installs), name-based on Linux."""
    pdf_dir = f"{FCC_DIR}/pdf"
    monofont_tex = f"{pdf_dir}/monofont.tex"
    os.makedirs(pdf_dir, exist_ok=True)
    if platform.system() == "Darwin":
        home = os.environ.get("HOME", "")
        user_fonts, sys_fonts = f"{home}/Library/Fonts", "/Library/Fonts"
        if _exists_any(f"{user_fonts}/DejaVuSansMono.ttf", f"{sys_fonts}/DejaVuSansMono.ttf"):
            chosen = "DejaVu Sans Mono"
            where = sys_fonts if os.path.exists(f"{sys_fonts}/DejaVuSansMono.ttf") else user_fonts
            line = (r"\setmonofont{DejaVuSansMono.ttf}[Path=" + where + "/, BoldFont=DejaVuSansMono-Bold.ttf, "
                    "ItalicFont=DejaVuSansMono-Oblique.ttf, BoldItalicFont=DejaVuSansMono-BoldOblique.ttf]")
        elif _exists_any(f"{user_fonts}/NotoMono-Regular.ttf", f"{sys_fonts}/NotoMono-Regular.ttf"):
            chosen = "Noto Mono"
            where = sys_fonts if os.path.exists(f"{sys_fonts}/NotoMono-Regular.ttf") else user_fonts
            line = r"\setmonofont{NotoMono-Regular.ttf}[Path=" + where + "/]"
        elif _exists_any(f"{user_fonts}/LiberationMono-Regular.ttf", f"{sys_fonts}/LiberationMono-Regular.ttf"):
            chosen = "Liberation Mono"
            where = sys_fonts if os.path.exists(f"{sys_fonts}/LiberationMono-Regular.ttf") else user_fonts
            line = r"\setmonofont{LiberationMono-Regular.ttf}[Path=" + where + "/]"
        else:
            chosen, line = "Courier New", r"\setmonofont{Courier New}"
            warn("No DejaVu/Noto/Liberation Mono found — code falls back to Courier New. Install one with: holo-convert.sh --with-optional (or: brew install --cask font-dejavu).")
    else:
        for name in ("DejaVu Sans Mono", "Noto Mono", "Liberation Mono"):
            if fc_has_family(name):
                chosen, line = name, r"\setmonofont{" + name + "}"
                break
        else:
            chosen, line = "Courier New", r"\setmonofont{Courier New}"
            warn("No DejaVu/Noto/Liberation Mono found — code falls back to Courier New. Install one with: holo-convert.sh --with-optional (or: sudo apt-get install fonts-dejavu).")
    # Guarded: \setmonofont is fontspec's, loaded only for XeLaTeX and LuaLaTeX.
    sh.write(monofont_tex, "\\ifdefined\\setmonofont\n  " + line + "\n\\fi\n")
    S.monofont_tex = monofont_tex
    success(f"Monospace font: {chosen} → {sh.basename(monofont_tex)}")


def detect_docx_mono():
    S.docx_mono = ""
    for f in ("Menlo", "DejaVu Sans Mono", "Monaco", "Consolas", "Courier New"):
        if font_installed(f):
            S.docx_mono = f
            break
    S.docx_mono = S.docx_mono or "Courier New"
    info(f"DOCX monospace font: {S.docx_mono}")


# Unicode blocks Latin Modern has no glyphs for, and the DejaVu face that
# stands in: letters in the serif (they sit in running text), symbols in the
# sans (DejaVu Serif lacks the dingbats - ✓ ✗). The basic arrows ← ↑ → ↓ ↔ ↕
# (2190-2195) stay out: Latin Modern draws those itself.
# Not here, on purpose: Hebrew and Arabic (XeLaTeX would set them left to right,
# which reads wrong - worse than missing), CJK and emoji (no font in the image;
# CJK also needs xeCJK to break lines). Those are reported after the run.
FALLBACK_LETTERS = ((0x0370, 0x03FF), (0x1F00, 0x1FFF), (0x0400, 0x052F))
FALLBACK_SYMBOLS = ((0x2196, 0x21FF), (0x2200, 0x22FF), (0x2300, 0x23FF), (0x2460, 0x24FF),
                    (0x2500, 0x257F), (0x2580, 0x259F), (0x25A0, 0x25FF), (0x2600, 0x26FF),
                    (0x2700, 0x27BF), (0x27F0, 0x27FF), (0x2900, 0x297F), (0x2980, 0x29FF),
                    (0x2A00, 0x2AFF), (0x2B00, 0x2BFF))

_FALLBACK_TEX = r"""% fallback.tex - written by holo-convert for each run (fonts.py).
% Characters Latin Modern has no glyph for used to vanish from the PDF, with
% only a warning per character from pandoc. XeTeX's character classes switch
% to DejaVu for exactly those Unicode blocks and back after them. Code (the
% monospace family) is left alone: its font has these, and ASCII art there
% must keep its fixed width. No groups, so a brace between the two ends of a
% run cannot unbalance anything.
\ifdefined\XeTeXinterchartoks
\newfontfamily\hcfallbackletters@LETTERS@
\newfontfamily\hcfallbacksymbols@SYMBOLS@
\newXeTeXintercharclass\hcclassletters
\newXeTeXintercharclass\hcclasssymbols
\makeatletter
\def\hc@range#1#2#3{\count@=#1\relax
  \loop\XeTeXcharclass\count@=#3\relax\ifnum\count@<#2\advance\count@\@ne\repeat}
@RANGES@
\let\hc@close\relax
\def\hc@restore{\fontfamily{\hc@saved}\selectfont\let\hc@close\relax}
\def\hc@open#1{\hc@close
  \edef\hc@a{\f@family}\edef\hc@b{\ttdefault}%
  \ifx\hc@a\hc@b\else\let\hc@saved\hc@a\let\hc@close\hc@restore#1\fi}
\XeTeXinterchartoks 0 \hcclassletters = {\hc@open\hcfallbackletters}
\XeTeXinterchartoks 4095 \hcclassletters = {\hc@open\hcfallbackletters}
\XeTeXinterchartoks \hcclasssymbols \hcclassletters = {\hc@open\hcfallbackletters}
\XeTeXinterchartoks 0 \hcclasssymbols = {\hc@open\hcfallbacksymbols}
\XeTeXinterchartoks 4095 \hcclasssymbols = {\hc@open\hcfallbacksymbols}
\XeTeXinterchartoks \hcclassletters \hcclasssymbols = {\hc@open\hcfallbacksymbols}
\XeTeXinterchartoks \hcclassletters 0 = {\hc@close}
\XeTeXinterchartoks \hcclassletters 4095 = {\hc@close}
\XeTeXinterchartoks \hcclasssymbols 0 = {\hc@close}
\XeTeXinterchartoks \hcclasssymbols 4095 = {\hc@close}
\makeatother
\XeTeXinterchartokenstate=1
\fi
"""


def _dejavu_spec(face: str, filename: str) -> str:
    """fontspec's argument for a DejaVu face: by family name where fontconfig
    knows it, by file on macOS (XeLaTeX's font database lags behind cask
    installs, as for the monospace font), "" when it is not installed."""
    if fc_has_family(face):
        return "{" + face + "}"
    if platform.system() == "Darwin":
        home = os.environ.get("HOME", "")
        for where in ("/Library/Fonts", f"{home}/Library/Fonts"):
            if os.path.exists(f"{where}/{filename}"):
                return "{" + filename + "}[Path=" + where + "/]"
    return ""


def detect_fallback_fonts():
    """Write .fcc/pdf/fallback.tex for XeLaTeX with the default main font.
    With --font the choice is the user's: missing characters are reported."""
    S.fallback_tex = ""
    if S.pdf_engine != "xelatex" or S.pdf_font:
        return
    letters = _dejavu_spec("DejaVu Serif", "DejaVuSerif.ttf")
    symbols = _dejavu_spec("DejaVu Sans", "DejaVuSans.ttf")
    if not (letters and symbols):
        info("DejaVu Serif/Sans not found: Greek, Cyrillic and symbols Latin Modern lacks will be "
             "missing from the PDF (reported after each file). Install fonts-dejavu to fill them in.")
        return
    ranges = "\n".join(
        f"\\hc@range{{\"{lo:04X}}}{{\"{hi:04X}}}{{{cls}}}"
        for cls, table in (("\\hcclassletters", FALLBACK_LETTERS), ("\\hcclasssymbols", FALLBACK_SYMBOLS))
        for lo, hi in table)
    tex = (_FALLBACK_TEX.replace("@LETTERS@", letters).replace("@SYMBOLS@", symbols)
           .replace("@RANGES@", ranges))
    path = f"{FCC_DIR}/pdf/fallback.tex"
    os.makedirs(f"{FCC_DIR}/pdf", exist_ok=True)
    sh.write(path, tex)
    S.fallback_tex = path
    info("Characters Latin Modern lacks (Greek, Cyrillic, arrows, ✓, box drawing) fall back to DejaVu.")
