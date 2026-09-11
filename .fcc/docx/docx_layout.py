#!/usr/bin/env python3
"""Post-process a generated .docx's layout (runtime, stdlib only):

  * page size  — optionally rewrite the section's pgSz (A4 / Letter)
  * image fit  — scale any image wider than the text column down to fit it
                 (keeps aspect ratio), so wide images don't overflow the margin
  * image align— centre every paragraph that contains an image

Usage:
    docx_layout.py <file.docx> [--page-size a4|letter]

Regex-based on the raw document.xml (preserves namespace prefixes). No-op parts
are skipped; a malformed file is left untouched.
"""
import argparse
import os
import re
import sys
import zipfile

TWIP_TO_EMU = 635  # 1 inch = 1440 twip = 914400 EMU  → 914400/1440
PAGE_TWIPS = {"a4": (11906, 16838), "letter": (12240, 15840)}


def set_page_size(doc: str, size: str) -> str:
    w, h = PAGE_TWIPS[size]
    return re.sub(r'<w:pgSz\b[^>]*/>',
                  f'<w:pgSz w:w="{w}" w:h="{h}"/>', doc, count=1)


def text_width_emu(doc: str) -> int:
    mw = re.search(r'<w:pgSz\b[^>]*w:w="(\d+)"', doc)
    mm = re.search(r'<w:pgMar\b[^>]*>', doc)
    if not mw:
        return 0
    pw = int(mw.group(1))
    left = right = 1440
    if mm:
        ml = re.search(r'w:left="(\d+)"', mm.group(0))
        mr = re.search(r'w:right="(\d+)"', mm.group(0))
        if ml:
            left = int(ml.group(1))
        if mr:
            right = int(mr.group(1))
    return max(0, (pw - left - right)) * TWIP_TO_EMU


def fit_images(doc: str, tw_emu: int) -> str:
    if tw_emu <= 0:
        return doc
    # cx/cy appear together in <wp:extent> and <a:ext>; scale any pair wider
    # than the text column. Same (cx,cy) value per image, so a global sub works.
    def repl(m):
        cx, cy = int(m.group(1)), int(m.group(2))
        if cx <= tw_emu:
            return m.group(0)
        cy = int(cy * tw_emu / cx)
        return m.group(0).replace(f'cx="{m.group(1)}"', f'cx="{tw_emu}"') \
                         .replace(f'cy="{m.group(2)}"', f'cy="{cy}"')
    return re.sub(r'cx="(\d+)" cy="(\d+)"', repl, doc)


# A near-zero-height paragraph (2pt font, 1pt exact line, no spacing) — invisible
# in practice, but a real paragraph a heading can "keep with".
SPACER = ('<w:p><w:pPr><w:spacing w:before="0" w:after="0" w:line="20" '
          'w:lineRule="exact"/><w:rPr><w:sz w:val="2"/><w:szCs w:val="2"/></w:rPr>'
          '</w:pPr></w:p>')


def spacer_before_heading_tables(doc: str) -> str:
    """Insert a tiny spacer paragraph between a heading and a following table.

    Heading styles carry "keep with next", and Word/Pages glue the heading to
    the table's first row. With a table taller than the space left on the page
    they relocate the *whole* table to the next page instead of flowing it,
    stranding the heading above a blank gap (Pages does this even when the docx
    keepNext flag is cleared — it re-applies keep-with-next to heading styles on
    import, so overriding the flag has no effect).

    A near-invisible spacer paragraph between the heading and the table gives the
    heading something else to "keep with", freeing the table to flow (and split)
    starting right under the heading. Only inserted when a heading directly
    precedes a table, so ordinary paragraphs before tables are untouched.
    """
    # A single heading paragraph (contains a Heading pStyle, no nested </w:p>)
    # immediately followed by a table (allowing bookmark anchors / whitespace).
    pat = re.compile(
        r'(<w:p\b(?:(?!</w:p>).)*?<w:pStyle w:val="Heading[^"]*"'
        r'(?:(?!</w:p>).)*?</w:p>)'
        r'((?:\s*(?:<w:bookmark(?:Start|End)\b[^>]*>)?\s*)*<w:tbl>)', re.S)
    return pat.sub(lambda m: m.group(1) + SPACER + m.group(2), doc)


def center_images(doc: str) -> str:
    def repl(m):
        attrs, body = m.group(1), m.group(2)
        if "<w:drawing" not in body:
            return m.group(0)
        if re.search(r'<w:pPr\b', body):
            if re.search(r'<w:jc\b[^>]*/>', body):
                body = re.sub(r'<w:jc\b[^>]*/>', '<w:jc w:val="center"/>', body, count=1)
            elif re.search(r'<w:rPr\b', body):
                body = re.sub(r'<w:rPr\b', '<w:jc w:val="center"/><w:rPr', body, count=1)
            else:
                body = re.sub(r'(<w:pPr\b[^>]*>)', r'\1<w:jc w:val="center"/>', body, count=1)
        else:
            body = '<w:pPr><w:jc w:val="center"/></w:pPr>' + body
        return f"<w:p{attrs}>{body}</w:p>"
    return re.sub(r'<w:p\b([^>]*)>(.*?)</w:p>', repl, doc, flags=re.S)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("docx")
    ap.add_argument("--page-size", choices=list(PAGE_TWIPS), default=None)
    args = ap.parse_args()

    try:
        with zipfile.ZipFile(args.docx) as z:
            infos = z.infolist()
            data = {i.filename: z.read(i.filename) for i in infos}
    except (OSError, zipfile.BadZipFile) as e:
        print(f"cannot read docx {args.docx}: {e}", file=sys.stderr)
        return 1
    key = "word/document.xml"
    if key not in data:
        print(f"not a docx (no {key}): {args.docx}", file=sys.stderr)
        return 1

    doc = data[key].decode("utf-8")
    orig = doc
    if args.page_size:
        doc = set_page_size(doc, args.page_size)
    doc = fit_images(doc, text_width_emu(doc))
    doc = center_images(doc)
    doc = spacer_before_heading_tables(doc)
    if doc == orig:
        return 0

    data[key] = doc.encode("utf-8")
    tmp = args.docx + ".tmp"
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        for i in infos:
            z.writestr(i, data[i.filename])
    os.replace(tmp, args.docx)
    print("adjusted docx layout (page-size/image fit/centering)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
