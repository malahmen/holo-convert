"""The .fcc/ asset trees: synced from the bundle into the working ./.fcc/."""
import filecmp
import os
import shutil

from . import sh
from .state import CANONICAL_FCC, DOCX_DEFAULT_REFERENCE, FCC_DIR, TITLE_PAGES_DIR, S
from .ui import info, warn

PDF_ASSETS = ("header.tex", "p10k.theme", "widen-tables.lua", "render-mermaid.lua", "pagebreak.lua", "br.lua",
              "breakable.lua")
DOCX_ASSETS = ("reference.docx", "reference-plain.docx", "stamp_docx_tokens.py", "docx_layout.py",
               "caption_figures.py", "check_links.py", "pagebreak.lua", "render-mermaid.lua", "br.lua",
               "widen-tables.lua", "p10k.theme")

_BASIC_HEADER = r"""\usepackage{listings}
\usepackage{xcolor}
\lstset{
  breaklines=true,
  breakatwhitespace=true,
  basicstyle=\small\ttfamily,
  columns=flexible,
  backgroundcolor=\color{gray!10},
  frame=single,
  framesep=3pt
}
"""


def _same(a: str, b: str) -> bool:
    return filecmp.cmp(a, b, shallow=False)


def _sync(src: str, dest: str) -> bool:
    """Copy src over dest unless identical; True if it copied."""
    if not os.path.isfile(dest) or not _same(src, dest):
        shutil.copyfile(src, dest)
        return True
    return False


def ensure_fcc_pdf_assets(assets=PDF_ASSETS):
    """Every PDF asset is behaviour-critical and kept in sync with the bundle,
    so a stale copy from an older run never lingers."""
    pdf_dir = f"{FCC_DIR}/pdf"
    src = f"{CANONICAL_FCC}/pdf"
    os.makedirs(pdf_dir, exist_ok=True)
    for a in assets:
        dest = f"{pdf_dir}/{a}"
        if os.path.isfile(f"{src}/{a}"):
            if _sync(f"{src}/{a}", dest):
                info(f"Synced {dest} (bundled).")
        elif a == "header.tex" and not os.path.isfile(dest):
            sh.write(dest, _BASIC_HEADER)
            warn(f"Bundled header.tex not found — wrote minimal fallback to {dest}.")
        elif not os.path.isfile(dest):
            warn(f"Bundled asset '{a}' not found at {src}/ — feature relying on it will be skipped.")


def ensure_pdf_config():
    ensure_fcc_pdf_assets()
    S.header_tex = f"{FCC_DIR}/pdf/header.tex"
    info(f"Using {S.header_tex}.")


def ensure_fcc_title_pages():
    """User-customisable: the bundled default.* are copied only when missing."""
    src = f"{CANONICAL_FCC}/title-pages"
    if not os.path.isdir(src):
        return
    os.makedirs(TITLE_PAGES_DIR, exist_ok=True)
    for name in ("default.yaml", "default.md"):
        f = f"{src}/{name}"
        if not os.path.isfile(f):
            continue
        dest = f"{TITLE_PAGES_DIR}/{name}"
        if not os.path.isfile(dest):
            shutil.copyfile(f, dest)
            info(f"Seeded {dest} (bundled default title page).")


def resolve_lua_filter(name: str) -> str:
    """The working copy if present (a project may customise it), else the bundle."""
    if os.path.isfile(f"{FCC_DIR}/pdf/{name}"):
        return f"{FCC_DIR}/pdf/{name}"
    if os.path.isfile(f"{CANONICAL_FCC}/pdf/{name}"):
        return f"{CANONICAL_FCC}/pdf/{name}"
    return ""


def resolve_docx_asset(name: str) -> str:
    if os.path.isfile(f"{FCC_DIR}/docx/{name}"):
        return f"{FCC_DIR}/docx/{name}"
    if os.path.isfile(f"{CANONICAL_FCC}/docx/{name}"):
        return f"{CANONICAL_FCC}/docx/{name}"
    return ""


def ensure_fcc_docx_assets() -> bool:
    """The DOCX tree, kept apart from the PDF one and synced from the bundle.
    False only if no reference doc ended up available."""
    docx_dir = f"{FCC_DIR}/docx"
    src = f"{CANONICAL_FCC}/docx"
    os.makedirs(docx_dir, exist_ok=True)
    for a in DOCX_ASSETS:
        dest = f"{docx_dir}/{a}"
        if os.path.isfile(f"{src}/{a}"):
            if _sync(f"{src}/{a}", dest):
                info(f"Synced {dest} (bundled).")
        elif not os.path.isfile(dest):
            warn(f"Bundled DOCX asset '{a}' not found at {src}/ — related styling will be skipped.")
    return os.path.isfile(DOCX_DEFAULT_REFERENCE)


def synced_helper(name: str):
    """fold_pagebreaks / shade_tables / apply_docx_fonts: kept in sync with the
    bundle like the filters. The script path to run, or None (already warned
    about by the caller)."""
    dest = f"{FCC_DIR}/docx/{name}"
    src = f"{CANONICAL_FCC}/docx/{name}"
    os.makedirs(sh.dirname(dest), exist_ok=True)
    if os.path.isfile(src) and _sync(src, dest):
        info(f"Synced {dest} (bundled).")
    if os.path.isfile(dest):
        return dest
    if os.path.isfile(src):
        return src
    return None
