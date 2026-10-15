"""The conversions themselves: md->pdf, md->docx, docx->md, --concat, the batch."""
import atexit
import os
import re
import shutil
import subprocess
import sys
import tempfile

from . import assets, sh
from .deps import highlight_theme_arg
from .docx import (apply_docx_fonts, caption_docx_figures, docx_post, fold_docx_pagebreaks, layout_docx,
                   reconcile_internal_links, shade_docx_tables, stamp_docx_letterhead)
from .prepass import first_h1, preprocess_md_tmp, yaml_quote
from .state import FCC_DIR, MD_INPUT_FORMAT, TOC_TITLE, S
from .ui import echo_blank, edie, enote, header, info, success, warn


def open_file(path: str):
    if not S.open_output:
        return
    if sh.which("xdg-open"):
        subprocess.Popen(["xdg-open", path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elif sh.which("open"):
        sh.run(["open", path])


def work_dir() -> str:
    """This run's own folder for its working copies (<name>.tmp.md,
    _concat.tmp.md), inside the output folder, removed when the run ends -
    also on Ctrl-C and SIGTERM, which exit through sys.exit. Fixed names in
    the output folder itself let two runs into one folder overwrite each
    other's copies, and a killed run left them behind."""
    if not S.work_dir:
        os.makedirs(S.output_dir, exist_ok=True)
        S.work_dir = tempfile.mkdtemp(prefix=".holo-run-", dir=S.output_dir)
        atexit.register(shutil.rmtree, S.work_dir, True)
    return S.work_dir


def strip_source_ext(name: str) -> str:
    """name without its source extension, in any case: UPPER.MD is UPPER, not
    UPPER.MD (which made UPPER.MD.docx)."""
    suffix = f".{S.source_format}"
    if len(name) > len(suffix) and name.lower().endswith(suffix.lower()):
        return name[: -len(suffix)]
    return name


def resolve_output_path(source_path: str, out_dir: str, ext: str):
    """<out>/<base>.<ext>, or a path-derived name when another input of this
    run shares the base name. A file already in the output folder is not a
    collision: re-running overwrites it."""
    base = strip_source_ext(sh.basename(source_path))
    dupes = 0
    for line in S.selected_files:
        if not line:
            continue
        if strip_source_ext(line.rsplit("/", 1)[-1]) == base:
            dupes += 1
    if dupes > 1:
        flat = strip_source_ext(source_path).replace("/", "_")
        info(f"Name collision for '{base}.{ext}' ({dupes} inputs share it) — using path-derived name: {flat}.{ext}")
        S.output_file = f"{out_dir}/{flat}.{ext}"
    else:
        S.output_file = f"{out_dir}/{base}.{ext}"
    if os.path.isfile(S.output_file):
        enote(f"Output exists — overwriting: {S.output_file}")


def resolve_resource_path(src: str) -> str:
    """Relative images resolve against the SOURCE's folder, not ./output/."""
    src_dir = sh.logical_dir(sh.dirname(src))
    return f"{src_dir}:{S.output_dir}:." if src_dir else ""


# pandoc's warning for a character no font in use has: one line per occurrence.
_MISSING_CHAR = re.compile(r"Missing character: There is no (.+?) \(U\+([0-9A-Fa-f]+)\)")
_MISSING_SHOWN = 30


def run_pandoc_pdf(args) -> tuple:
    """pandoc, its output passed through as it comes, except the "Missing
    character" warnings: those are collected (one per distinct character) for
    a single summary. Returns (exit status, missing characters in order)."""
    missing = {}
    try:
        proc = subprocess.Popen(["pandoc", *args], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, errors="replace")
    except FileNotFoundError:
        return 127, []
    for line in proc.stdout:
        m = _MISSING_CHAR.search(line)
        if m:
            missing.setdefault(m.group(2).upper(), m.group(1))
        else:
            sys.stdout.write(line)
            sys.stdout.flush()
    return proc.wait(), list(missing.items())


def report_missing_chars(output_file: str, missing):
    """The PDF is written, but without these characters: say so once, plainly."""
    if not missing:
        return
    shown = " ".join(f"{ch} (U+{cp})" for cp, ch in missing[:_MISSING_SHOWN])
    more = f" … and {len(missing) - _MISSING_SHOWN} more" if len(missing) > _MISSING_SHOWN else ""
    font = f"'{S.pdf_font}'" if S.pdf_font else "the PDF fonts"
    warn(f"{sh.basename(output_file)}: {len(missing)} character(s) missing from the PDF in at least "
         f"one place - {font} there have no glyph for them: {shown}{more}")
    warn("  CJK, emoji and right-to-left scripts (Hebrew, Arabic) are not supported in PDF output "
         "(DOCX keeps them); for other characters, --font with a font that has them.")


def convert_md_to_pdf(input_file: str, name_source: str = "") -> bool:
    name_source = name_source or input_file
    if not S.pdf_engine:
        warn(f"PDF_ENGINE is not set — skipping: {input_file}")
        return False
    resolve_output_path(name_source, S.output_dir, "pdf")
    output_file = S.output_file
    res_path = resolve_resource_path(name_source)
    args = [input_file, "-o", output_file, f"--from={MD_INPUT_FORMAT}", f"--pdf-engine={S.pdf_engine}"]
    if S.is_latex_engine():
        args += ["-H", S.header_tex, "-H", S.monofont_tex, "-V", "colorlinks=true", "-V", "linkcolor=blue",
                 "-V", "urlcolor=blue", "-V", "citecolor=blue"]
        if S.fallback_tex:
            args += ["-H", S.fallback_tex]
    if res_path:
        args.append(f"--resource-path={res_path}")
    if os.path.isfile(f"{FCC_DIR}/pdf/p10k.theme"):
        args.append(highlight_theme_arg(f"{FCC_DIR}/pdf/p10k.theme"))
    # breakable.lua last: widen-tables.lua measures inline code it would split.
    for lf in ("br.lua", "widen-tables.lua", "render-mermaid.lua", "pagebreak.lua", "breakable.lua"):
        path = assets.resolve_lua_filter(lf)
        if path:
            args.append(f"--lua-filter={path}")
    if S.pdf_font:
        args += ["-V", f"mainfont={S.pdf_font}"]
    if S.use_toc and not S.toc_placed_in_title:
        args += ["--toc", f"--toc-depth={S.toc_depth}", "-V", f"toc-title={TOC_TITLE}"]
    enote(f"Converting {sh.basename(input_file)} → {sh.basename(output_file)} …")
    status, missing = run_pandoc_pdf(args)
    if status == 0:
        report_missing_chars(output_file, missing)
        success(f"{sh.basename(output_file)} ✓")
        open_file(output_file)
        return True
    warn(f"Failed to convert: {name_source}")
    return False


def convert_md_to_docx(input_file: str, name_source: str = "") -> bool:
    name_source = name_source or input_file
    resolve_output_path(name_source, S.output_dir, "docx")
    output_file = S.output_file
    args = [input_file, "-o", output_file, f"--from={MD_INPUT_FORMAT}", "--to=docx"]
    res_path = resolve_resource_path(name_source)
    if res_path:
        args.append(f"--resource-path={res_path}")
    for lf in ("br.lua", "widen-tables.lua", "pagebreak.lua", "render-mermaid.lua"):
        path = assets.resolve_docx_asset(lf)
        if path:
            args.append(f"--lua-filter={path}")
    if S.use_toc and not S.toc_placed_in_title:
        args += ["--toc", f"--toc-depth={S.toc_depth}"]
    if S.docx_reference_doc:
        args.append(f"--reference-doc={S.docx_reference_doc}")
    if S.is_builtin_docx_ref():
        theme = assets.resolve_docx_asset("p10k.theme")
        if theme:
            args.append(highlight_theme_arg(theme))
    enote(f"Converting {sh.basename(input_file)} → {sh.basename(output_file)} ...")
    if sh.run(["pandoc", *args]) != 0:
        warn(f"Failed to convert: {name_source}")
        return False
    docx_post(fold_docx_pagebreaks, output_file)
    docx_post(apply_docx_fonts, output_file)
    if S.is_builtin_docx_ref():
        docx_post(shade_docx_tables, output_file)
        docx_post(layout_docx, output_file)
        docx_post(caption_docx_figures, output_file)
    if S.docx_letterhead:
        docx_post(stamp_docx_letterhead, output_file, name_source)
    if not os.path.isfile(output_file):
        warn(f"Post-processing left no output for: {input_file}")
        return False
    success(f"{sh.basename(output_file)} ✓")
    open_file(output_file)
    return True


def convert_docx_to_md(input_file: str) -> bool:
    resolve_output_path(input_file, S.output_dir, "md")
    output_file = S.output_file
    media_rel = f"media/{sh.basename(output_file, '.md')}"
    media_dir = f"{S.output_dir}/{media_rel}"
    # Run from the output folder: pandoc writes image links as the path given
    # to --extract-media, so they are relative to the .md that uses them.
    # (From the working directory they read output/media/..., broken from
    # the .md's own folder.)
    args = [os.path.abspath(input_file), "-o", sh.basename(output_file), "--from=docx", f"--to={S.md_variant}",
            f"--extract-media={media_rel}"]
    enote(f"Converting {sh.basename(input_file)} → {sh.basename(output_file)} ...")
    if sh.run(["pandoc", *args], cwd=S.output_dir) != 0:
        warn(f"Failed to convert: {input_file}")
        return False
    success(f"{sh.basename(output_file)} ✓")
    if os.path.isdir(media_dir):
        count = sum(len(files) for _r, _d, files in os.walk(media_dir))
        if count > 0:
            info(f"Extracted {count} media file(s) → {media_dir}")
    open_file(output_file)
    return True


def _is_blank(path: str) -> bool:
    """Nothing but whitespace. (An empty file made LaTeX fail with only
    "Error producing PDF".) Unreadable files are left to the copy below."""
    try:
        return sh.read(path).strip(sh.SPACE) == ""
    except OSError:
        return False


def run_concat() -> bool:
    """Every input into one working copy, converted once. The first "# H1"
    becomes the document title; inputs are separated by an optional page break."""
    combined = f"{work_dir()}/_concat.tmp.md"
    first_input, title = "", ""
    sh.write(combined, "")
    for idx, input_file in enumerate([f for f in S.selected_files if f], 1):
        first_input = first_input or input_file
        part = f"{work_dir()}/_part.tmp.md"
        try:
            shutil.copyfile(input_file, part)
        except OSError:
            edie(f"--concat: {input_file} became unreadable mid-run — refusing to write a document that is missing it.")
        preprocess_md_tmp(part, input_file, False)
        if idx == 1:
            records = sh.awk_records(sh.read(part))
            h1 = first_h1(records)
            if h1 >= 0:
                title = records[h1][2:]
                del records[h1]
            sh.write(part, sh.awk_print(records))
        chunk = ""
        if idx > 1 and S.concat_pagebreak:
            chunk += "\n\n\\newpage\n\n"
        chunk += sh.read(part) + "\n\n"
        with open(combined, "a", encoding="utf-8", errors="surrogateescape", newline="") as fh:
            fh.write(chunk)
        os.remove(part)
    if title:
        # Quoted for YAML: a " in the heading used to end the string early.
        sh.write(combined, f"---\ntitle: {yaml_quote(title)}\n---\n\n" + sh.read(combined))
    pair = f"{S.source_format}→{S.output_format}"
    if pair == "md→pdf":
        ok = convert_md_to_pdf(combined, first_input)
    elif pair == "md→docx":
        ok = convert_md_to_docx(combined, first_input)
    else:
        warn(f"Concat not supported for {S.source_format}→{S.output_format}.")
        ok = False
    if os.path.exists(combined):
        os.remove(combined)
    return ok


def run_conversions() -> bool:
    header("Converting Files")
    os.makedirs(S.output_dir, exist_ok=True)
    info(f"Output directory: {S.output_dir}")
    pair = f"{S.source_format}→{S.output_format}"
    failed = succeeded = 0

    # Every input is checked before any conversion starts, and the unusable
    # ones are reported together.
    usable, unusable = [], []
    for f in S.selected_files:
        if not f:
            continue
        if os.path.isdir(f):
            unusable.append(f"{f} (is a directory)")
        elif not os.path.lexists(f) or not os.path.exists(f):
            unusable.append(f"{f} (does not exist)")
        elif not os.path.isfile(f):
            unusable.append(f"{f} (not a regular file)")
        elif not os.access(f, os.R_OK):
            unusable.append(f"{f} (not readable)")
        else:
            usable.append(f)
    if unusable:
        for u in unusable:
            warn(f"cannot convert {u}")
        if S.concat and S.source_format == "md":
            edie(f"--concat needs every input: {len(unusable)} of {len(usable) + len(unusable)} cannot be read.")
        failed = len(unusable)
    if not usable:
        echo_blank()
        enote(f"Conversion complete — 0 succeeded, {failed} failed.")
        return False
    S.selected_files = usable

    if S.concat and S.source_format == "md":
        if run_concat():
            succeeded = 1
        else:
            failed = 1
    else:
        for input_file in S.selected_files:
            effective, tmp = input_file, ""
            if S.source_format == "md" and _is_blank(input_file):
                warn(f"{input_file} is empty — nothing to convert.")
                failed += 1
                continue
            if S.source_format == "md":
                tmp = f"{work_dir()}/{strip_source_ext(sh.basename(input_file))}.tmp.md"
                try:
                    shutil.copyfile(input_file, tmp)
                except OSError:
                    warn(f"cannot read {input_file} — skipping it.")
                    failed += 1
                    if os.path.exists(tmp):
                        os.remove(tmp)
                    continue
                effective = tmp
                preprocess_md_tmp(tmp, input_file, True)
                # After the pre-passes: a substitution can change a heading's slug.
                reconcile_internal_links(tmp, input_file)
            if pair == "md→pdf":
                ok = convert_md_to_pdf(effective, input_file)
            elif pair == "md→docx":
                ok = convert_md_to_docx(effective, input_file)
            elif pair == "docx→md":
                ok = convert_docx_to_md(effective)
            else:
                ok = None
            if ok is True:
                succeeded += 1
            elif ok is False:
                failed += 1
            if tmp and os.path.isfile(tmp):
                os.remove(tmp)

    echo_blank()
    enote(f"Conversion complete — {succeeded} succeeded, {failed} failed.")
    return failed == 0
