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
