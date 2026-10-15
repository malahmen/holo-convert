"""The md pre-passes and the title page - on the .tmp.md working copy only.

Substitutions, rule stripping, wikilink unwrapping, SVG rasterisation and the
title page, each matching the sed/awk it replaces line for line (see sh.py).
"""
import os
import re
import subprocess

from . import sh
from .state import TITLE_PAGES_DIR, S
from .ui import info, warn

_RULE = re.compile(r"---[ \t\r\v\f]*\Z")
_FM_END = re.compile(r"(---|\.\.\.)[ \t\r\v\f]*\Z")


# --- substitutions, rules, wikilinks -------------------------------------------------

def apply_substitutions(tmp: str):
    """→ to ->, — to -, ✓ removed; outside fenced code only."""
    text = sh.read(tmp)
    sh.write(tmp, sh.outside_fences(
        text, lambda line: line.replace("\u2192", "->").replace("\u2014", "-").replace("\u2713", "")))


def apply_strip_rules(tmp: str):
    """Drop thematic breaks (^---\\s*$), keeping front matter and code."""
    out, in_fm, in_code = [], False, False
    for n, line in enumerate(sh.awk_records(sh.read(tmp)), 1):
        if n == 1 and _RULE.match(line):
            in_fm = True
            out.append(line)
        elif in_fm and _RULE.match(line):
            in_fm = False
            out.append(line)
        elif in_fm:
            out.append(line)
        elif line.startswith("```"):
            in_code = not in_code
            out.append(line)
        elif in_code:
            out.append(line)
        elif _RULE.match(line):
            continue
        else:
            out.append(line)
    sh.write(tmp, sh.awk_print(out))


_WIKI_PIPED = re.compile(r"\[\[[^\]|]*\|([^\]]+)\]\]")
_WIKI_BARE = re.compile(r"\[\[([^\]#|]+)[^\]]*\]\]")


def apply_wikilink_unwrap(tmp: str):
    """[[Target|Label]] -> Label, [[Target#anchor]] -> Target; outside code."""
    sh.write(tmp, sh.outside_fences(
        sh.read(tmp), lambda line: _WIKI_BARE.sub(r"\1", _WIKI_PIPED.sub(r"\1", line))))


# --- SVG ---------------------------------------------------------------------------------

def ensure_rsvg() -> bool:
    if sh.which("rsvg-convert"):
        return True
    warn("rsvg-convert (librsvg) is not installed — leaving .svg images as-is.")
    return False


def ensure_pdf_image(src: str):
    """A path xelatex can embed (pdf/png/jpg/jpeg/eps), converting other
    formats to PNG; None if it cannot."""
    ext = src.rsplit(".", 1)[-1].lower() if "." in src else src.lower()
    if ext in ("pdf", "png", "jpg", "jpeg", "eps"):
        return src
    os.makedirs(S.output_dir, exist_ok=True)
    stem = sh.basename(src.rsplit(".", 1)[0] if "." in src else src)
    png = f"{S.output_dir}/title_img_{stem}.png"
    quiet = {"stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if ext == "svg":
        if ensure_rsvg() and sh.run(["rsvg-convert", "--zoom", "2", "-o", png, src], stderr=subprocess.DEVNULL) == 0:
            return png
    elif sh.which("sips"):
        if sh.run(["sips", "-s", "format", "png", src, "--out", png], **quiet) == 0:
            return png
    elif sh.which("magick"):
        if sh.run(["magick", src, png], stderr=subprocess.DEVNULL) == 0:
            return png
    elif sh.which("convert"):
        if sh.run(["convert", src, png], stderr=subprocess.DEVNULL) == 0:
            return png
    return None


_SVG_REF = re.compile(r"!\[[^\]\n]*\]\([^)\n]*\.svg", re.I)
_SVG_IMG = re.compile(r"!\[[^\]\n]*\]\([^)\n]*\.svg[^)\n]*\)", re.I)
_TARGET = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")


def apply_svg_raster(tmp: str, srcdir: str):
    """Local .svg images -> PNG via rsvg-convert, so pandoc can embed them."""
    text = sh.read(tmp)
    if not _SVG_REF.search(text):
        return
    if not ensure_rsvg():
        warn("rsvg-convert unavailable — leaving .svg images as-is.")
        return
    media = f"{S.output_dir}/media"
    os.makedirs(media, exist_ok=True)
    targets = set()
    for line in text.split("\n"):
        for m in _SVG_IMG.finditer(line):
            t = _TARGET.match(m.group(0)).group(1)
            t = re.split(r"[ \t\r\v\f]", t, 1)[0]
            t = t[1:] if t.startswith("<") else t
            t = t[:-1] if t.endswith(">") else t
            targets.add(t)
    if not targets:
        warn("Found an .svg reference this cannot parse as an image target — leaving it as-is.")
        return
    i = 0
    for svg in sorted(targets):
        if not svg or re.match(r"https?://", svg):
            continue
        if "#" in svg:
            warn(f"SVG target carries a #fragment, which cannot be rasterised: {svg} — leaving it as-is.")
            continue
        expanded = sh.expand_tilde(svg)
        abs_path = expanded if expanded.startswith("/") else f"{srcdir}/{expanded}"
        abs_path = f"{sh.logical_dir(sh.dirname(abs_path)) or ''}/{sh.basename(abs_path)}"
        if not os.path.isfile(abs_path):
            warn(f"SVG not found: {svg}")
            continue
        i += 1
        png = f"{media}/svg_{i}_{sh.basename(sh.strip_suffix(abs_path, '.svg'))}.png"
        if sh.run(["rsvg-convert", "--zoom", "2", "-o", png, abs_path], stderr=subprocess.DEVNULL) == 0:
            text = sh.read(tmp).replace(f"({svg})", f"({png})")
            sh.write(tmp, text)
        else:
            warn(f"Failed to rasterize: {svg}")


# --- title page -----------------------------------------------------------------------------

def resolve_title_page_yaml(source_path: str) -> str:
    flat = sh.strip_suffix(source_path, ".md").replace("/", "_")
    specific = f"{TITLE_PAGES_DIR}/{flat}.yaml"
    default = f"{TITLE_PAGES_DIR}/default.yaml"
    if os.path.isfile(specific):
        return specific
    if os.path.isfile(default):
        return default
    return ""


def parse_yaml_field(path: str, field: str) -> str:
    """A one-line scalar. A markdown file is read only inside its leading
    front matter; a .yaml/.yml file whole."""
    whole = path.endswith((".yaml", ".yml"))
    try:
        records = sh.awk_records(sh.read(path))
    except OSError:
        return ""
    for n, line in enumerate(records, 1):
        if n == 1 and not whole:
            if not _RULE.match(line):
                return ""
            continue
        if not whole and _FM_END.match(line):
            return ""
        if line.startswith(field + ":"):
            return re.sub("^" + re.escape(field) + ":[ \t\r\n\v\f]*", "", line, 1).replace("\r", "")
    return ""


def extract_title(path: str) -> str:
    """Front matter title: (quotes removed), else the first "# " heading."""
    records = sh.awk_records(sh.read(path))
    if records and re.match(r"---[ \t\r\v\f]*\Z", records[0]):
        title = ""
        for n, line in enumerate(records, 1):
            if line.startswith("---"):
                if n == 1:
                    continue
                break
            if line.startswith("title:"):
                title = re.sub(r"^title:[ \t\r\n\v\f]*", "", line, 1)
                break
        title = sh.subst(title.replace('"', "").replace("'", ""))
        if title:
            return title
    for line in records:
        if line.startswith("# "):
            return line[2:]
    return ""


def strip_title(path: str) -> str:
    """The file without its title: the title: line inside front matter, else
    the first "# " line. As `$(...)` returns it: no trailing newlines."""
    records = sh.awk_records(sh.read(path))
    out = []
    if records and re.match(r"---[ \t\r\v\f]*\Z", records[0]):
        done = False
        for n, line in enumerate(records, 1):
            if n == 1:
                out.append(line)
            elif not done and _FM_END.match(line):
                done = True
                out.append(line)
            elif not done and line.startswith("title:"):
                continue
            else:
                out.append(line)
    else:
        found = False
        for line in records:
            if not found and line.startswith("# "):
                found = True
                continue
            out.append(line)
    return sh.subst(sh.awk_print(out))


def latex_escape_text(s: str) -> str:
    """Escape a title for the TeX template. The backslash goes through a
    placeholder: its replacement has braces the brace rules would re-escape."""
    s = s.replace("\\", "\x01")
    for a, b in (("&", "\\&"), ("%", "\\%"), ("$", "\\$"), ("#", "\\#"), ("_", "\\_"),
                 ("{", "\\{"), ("}", "\\}"), ("~", "\\textasciitilde{}"), ("^", "\\textasciicircum{}"),
                 ("\x01", "\\textbackslash{}")):
        s = s.replace(a, b)
    return s


def apply_title_page(source_path: str, tmp: str):
    yaml_file = resolve_title_page_yaml(source_path)
    if not yaml_file:
        warn(f"No title page template for '{source_path}' — skipping title page.")
        return
    yaml_dir = sh.dirname(yaml_file)
    template_rel = parse_yaml_field(yaml_file, "template")
    image_rel = parse_yaml_field(yaml_file, "image")
    if not template_rel:
        warn(f"YAML '{yaml_file}' missing 'template:' field — skipping title page.")
        return
    template_path = f"{yaml_dir}/{template_rel}"
    if not os.path.isfile(template_path):
        warn(f"Template file not found: '{template_path}' — skipping title page.")
        return
    title = extract_title(source_path)
    if not title:
        warn(f"No title found in '{source_path}' — skipping title page.")
        return

    # The image: absolute, else relative to the yaml, else to the working dir.
    image_abs = ""
    if image_rel:
        expanded = sh.expand_tilde(image_rel)
        if expanded.startswith("/") and os.path.isfile(expanded):
            image_abs = expanded
        else:
            for base in (yaml_dir, os.environ.get("PWD") or os.getcwd()):
                cand = os.path.realpath(f"{base}/{expanded}")
                if os.path.isfile(cand):
                    image_abs = cand
                    break
        if not image_abs:
            warn(f"Configured title-page image not found: '{image_rel}'.")
    if not image_abs and S.title_img_cache:
        image_abs = S.title_img_cache

    if S.output_format == "docx":
        img_line = f"![]({image_abs}){{width=35%}}" if image_abs else ""
        rendered = sh.subst(f"{img_line}\n\n::: {{custom-style=\"Title\"}}\n{title}\n:::\n\n\\newpage\n")
    elif not S.is_latex_engine():
        img_line = f"![]({image_abs}){{width=35%}}" if image_abs else ""
        rendered = sh.subst('::: {style="text-align:center; margin-top:30vh; margin-bottom:30vh"}\n'
                            f"{img_line}\n\n[{title}]{{style=\"font-size:2.2em; font-weight:bold\"}}\n:::\n\n\\newpage\n")
    else:
        image_md = ""
        if image_abs:
            pdf_img = ensure_pdf_image(image_abs)
            if pdf_img:
                image_md = "\\includegraphics[width=0.3\\textwidth]{" + pdf_img.replace("_", "\\_") + "}"
            else:
                warn(f"Title-page image can't be embedded in PDF (unsupported format, no converter): {image_abs} — skipping.")
        template = sh.subst(sh.read(template_path))
        rendered = template.replace("{{TITLE}}", latex_escape_text(title)).replace("{{IMAGE}}", image_md)
        if (S.tp_pagenum or "true") == "false":
            rendered = "\\thispagestyle{empty}\n" + rendered

    # The TOC belongs after the title page; pandoc's --toc would put it above.
    if S.use_toc:
        depth = S.toc_depth or "3"
        if S.output_format == "docx":
            toc = ('<w:sdt><w:sdtPr><w:docPartObj><w:docPartGallery w:val="Table of Contents"/><w:docPartUnique/>'
                   '</w:docPartObj></w:sdtPr><w:sdtContent><w:p><w:pPr><w:pStyle w:val="TOCHeading"/></w:pPr><w:r>'
                   '<w:t xml:space="preserve">Table of Contents</w:t></w:r></w:p><w:p><w:r>'
                   '<w:fldChar w:fldCharType="begin" w:dirty="true"/><w:instrText xml:space="preserve">'
                   f'TOC \\o "1-{depth}" \\h \\z \\u</w:instrText><w:fldChar w:fldCharType="separate"/>'
                   '<w:fldChar w:fldCharType="end"/></w:r></w:p></w:sdtContent></w:sdt>')
            rendered += "\n\n```{=openxml}\n" + toc + "\n```\n\n\\newpage"
            S.toc_placed_in_title = True
        elif S.is_latex_engine():
            rendered += "\n\\setcounter{tocdepth}{" + depth + "}\n\\tableofcontents\n\\newpage"
            S.toc_placed_in_title = True

    # strip_title reads the working copy: the pre-passes already ran on it.
    stripped = strip_title(tmp)
    sh.write(tmp, rendered + "\n" + "\n" + stripped + "\n")
    info(f"Title page applied (template: {sh.basename(yaml_file)}) → {sh.basename(tmp)}")


def preprocess_md_tmp(tmp: str, source: str, do_tp: bool):
    S.toc_placed_in_title = False
    if S.apply_substitutions:
        apply_substitutions(tmp)
    if S.strip_rules:
        apply_strip_rules(tmp)
    if S.unwrap_wikilinks:
        apply_wikilink_unwrap(tmp)
    if S.raster_svg:
        apply_svg_raster(tmp, sh.dirname(source))
    if do_tp and S.use_title_page:
        apply_title_page(source, tmp)
