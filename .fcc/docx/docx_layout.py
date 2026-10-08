#!/usr/bin/env python3
"""Post-process a generated .docx's layout (runtime, stdlib only):

  * page size  — optionally rewrite the section's pgSz (A4 / Letter); when the
                 section has no pgSz/pgMar at all (the plain reference doc
                 ships none) they are added, so the page is not left to the
                 viewer's default
  * table fit  — scale every table's columns to the text width (100% wide)
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
# Same margins as the letterhead reference doc (build-reference.py MARGINS).
DEFAULT_PGMAR = ('<w:pgMar w:top="1440" w:right="1080" w:bottom="1440" w:left="1080" '
                 'w:header="720" w:footer="600" w:gutter="0"/>')


def set_page_size(doc: str, size: str) -> str:
    w, h = PAGE_TWIPS[size]
    return re.sub(r'<w:pgSz\b[^>]*/>',
                  f'<w:pgSz w:w="{w}" w:h="{h}"/>', doc, count=1)


def ensure_page_geometry(doc: str, size: str) -> str:
    """Give the body's section a pgSz/pgMar when it has none.

    pandoc copies the reference doc's section properties, and reference-plain.docx
    has no page size or margins: the page was then whatever the viewer defaults
    to, --page-size had nothing to rewrite, and the image/table fitting below
    had no text width to work with. Existing values are left alone.
    """
    m = None
    for m in re.finditer(r'<w:sectPr\b[^>]*>(.*?)</w:sectPr>', doc, re.S):
        pass
    if m is None:  # no closing sectPr: the body's last section is <w:sectPr/> or absent
        return doc
    body = m.group(1)
    add = ""
    if "<w:pgSz" not in body:
        w, h = PAGE_TWIPS[size]
        add += f'<w:pgSz w:w="{w}" w:h="{h}"/>'
    if "<w:pgMar" not in body:
        add += DEFAULT_PGMAR
    if not add:
        return doc
    # Schema order: pgSz/pgMar come after header/footer refs, footnotePr,
    # endnotePr and type, and before everything else. Word rejects a sectPr
    # whose children are out of order.
    after = re.search(r'<w:(?:paperSrc|pgBorders|lnNumType|pgNumType|cols|formProt|'
                      r'vAlign|noEndnote|titlePg|textDirection|bidi|rtlGutter|docGrid|'
                      r'printerSettings|sectPrChange)\b', body)
    cut = after.start() if after else len(body)
    start, end = m.span(1)
    return doc[:start] + body[:cut] + add + body[cut:] + doc[end:]


def text_width_twips(doc: str) -> int:
    return text_width_emu(doc) // TWIP_TO_EMU


def fit_tables(doc: str, tw: int) -> str:
    """Make every table span the text width.

    pandoc sizes a table's grid against its own 5.5in default text width (7920
    twips), not the page's, and a table without explicit widths is left to
    autofit to its content. Word and Pages lay a fixed-layout table out by its
    grid, so tables stopped short of the right margin. Scale each table's
    gridCol (and any dxa tcW) so the grid sums to the text width, and mark the
    table 100% wide with a fixed layout. Tables holding a nested table are
    skipped (the regex would see the inner one first).
    """
    if tw <= 0:
        return doc

    def repl(m):
        tbl = m.group(0)
        if "<w:tbl>" in tbl[len("<w:tbl>"):]:
            return tbl
        cols = [int(x) for x in re.findall(r'<w:gridCol w:w="(\d+)"\s*/>', tbl)]
        total = sum(cols)
        if not cols or total <= 0:
            return tbl
        factor = tw / total
        new = [int(c * factor) for c in cols]
        new[-1] += tw - sum(new)          # rounding remainder onto the last column
        it = iter(new)
        tbl = re.sub(r'<w:gridCol w:w="\d+"\s*/>',
                     lambda _: f'<w:gridCol w:w="{next(it)}"/>', tbl)
        tbl = re.sub(r'<w:tcW w:w="(\d+)" w:type="dxa"\s*/>',
                     lambda c: f'<w:tcW w:w="{int(int(c.group(1)) * factor)}" w:type="dxa"/>', tbl)
        tbl = re.sub(r'<w:tblW\b[^>]*/>', '<w:tblW w:type="pct" w:w="5000"/>', tbl, count=1)
        if "<w:tblLayout" in tbl:
            tbl = re.sub(r'<w:tblLayout\b[^>]*/>', '<w:tblLayout w:type="fixed"/>', tbl, count=1)
        else:
            tbl = re.sub(r'(<w:tblW\b[^>]*/>)', r'\1<w:tblLayout w:type="fixed"/>', tbl, count=1)
        return tbl

    return re.sub(r'<w:tbl>.*?</w:tbl>', repl, doc, flags=re.S)


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
        doc = ensure_page_geometry(doc, args.page_size)
        doc = set_page_size(doc, args.page_size)
    doc = fit_tables(doc, text_width_twips(doc))
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
    print("adjusted docx layout (page geometry/table width/image fit/centering)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
