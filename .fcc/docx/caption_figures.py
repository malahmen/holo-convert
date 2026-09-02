#!/usr/bin/env python3
"""Turn pandoc's image alt text into a *native* Word figure caption.

pandoc emits a lone image as a `CaptionedFigure` paragraph followed by an
`ImageCaption` paragraph holding the alt text, and *also* copies the alt text
into the image's description (`<wp:docPr descr=...>`). The result reads like a
stray line + a duplicated description rather than a caption Word recognises.

This post-processor rewrites each `ImageCaption` paragraph into a genuine Word
caption:

  * the built-in `Caption` paragraph style (not pandoc's custom `Image Caption`)
  * a `SEQ Figure` field so it auto-numbers and shows up in
    References -> Table of Figures, e.g. "Figure 1: <alt text>"

and clears the now-redundant image description on the captioned figure, so the
alt text lives only in the caption. `word/settings.xml` gets `updateFields` so
Word recomputes the SEQ numbers on open.

Regex-based on the raw XML (like shade_tables.py / apply_docx_fonts.py) to keep
namespace prefixes intact. Idempotent: once converted the paragraphs are
`Caption`, so a second pass finds no `ImageCaption` to touch.

Usage: caption_figures.py <file.docx> [label]     (label default: "Figure")
"""
import sys
import os
import re
import zipfile

LABEL = "Figure"

PARA_RE = re.compile(r'<w:p\b.*?</w:p>', re.S)
TEXT_RE = re.compile(r'<w:t[^>]*>(.*?)</w:t>', re.S)


def label_runs(n, has_text):
    """The 'Figure N' (+ ': ' when a caption follows) run sequence."""
    seq = (
        '<w:fldSimple w:instr=" SEQ %s \\* ARABIC ">'
        '<w:r><w:t>%d</w:t></w:r></w:fldSimple>' % (LABEL, n)
    )
    lead = '<w:r><w:t xml:space="preserve">%s </w:t></w:r>' % LABEL
    tail = '<w:r><w:t xml:space="preserve">: </w:t></w:r>' if has_text else ''
    return lead + seq + tail


def convert_caption(para, n):
    """Rewrite an ImageCaption paragraph into a numbered Caption paragraph."""
    # Swap the paragraph style to the built-in Caption.
    para = re.sub(r'(<w:pStyle w:val=")ImageCaption(")', r'\1Caption\2', para, count=1)
    # Does the caption carry any visible text?
    has_text = any(t.strip() for t in TEXT_RE.findall(para))
    runs = label_runs(n, has_text)
    # Insert the label right after the paragraph properties (or at the start of
    # the paragraph body when there is no <w:pPr>).
    if '</w:pPr>' in para:
        return para.replace('</w:pPr>', '</w:pPr>' + runs, 1)
    return re.sub(r'(<w:p\b[^>]*>)', r'\1' + runs, para, count=1)


def clear_descr(para):
    """Drop the redundant alt-text description from a captioned figure's image."""
    def strip(m):
        return re.sub(r'\s+descr="[^"]*"', '', m.group(0), count=1)
    return re.sub(r'<wp:docPr\b[^>]*/>', strip, para)


def ensure_update_fields(data):
    """Make Word recompute SEQ (and any other) fields on open."""
    key = 'word/settings.xml'
    if key not in data:
        return
    s = data[key].decode('utf-8')
    if '<w:updateFields' in s:
        return
    m = re.search(r'(<w:settings\b[^>]*>)', s)
    if not m:
        return
    s = s[:m.end()] + '<w:updateFields w:val="true"/>' + s[m.end():]
    data[key] = s.encode('utf-8')


def main():
    if len(sys.argv) < 2:
        return
    path = sys.argv[1]
    global LABEL
    if len(sys.argv) > 2 and sys.argv[2]:
        LABEL = sys.argv[2]

    try:
        with zipfile.ZipFile(path) as z:
            infos = z.infolist()
            data = {i.filename: z.read(i.filename) for i in infos}
    except (OSError, zipfile.BadZipFile):
        return

    key = 'word/document.xml'
    if key not in data:
        return
    doc = data[key].decode('utf-8')

    count = [0]

    def process(m):
        para = m.group(0)
        if 'w:val="CaptionedFigure"' in para:
            return clear_descr(para)
        if 'w:val="ImageCaption"' in para:
            count[0] += 1
            return convert_caption(para, count[0])
        return para

    new = PARA_RE.sub(process, doc)
    if count[0] == 0 and new == doc:
        return
    data[key] = new.encode('utf-8')
    if count[0]:
        ensure_update_fields(data)

    tmp = path + '.tmp'
    with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as z:
        for i in infos:
            z.writestr(i, data[i.filename])
    os.replace(tmp, path)
    print('captioned %d figure(s) as native Word captions (%s N: ...)' % (count[0], LABEL))


if __name__ == '__main__':
    main()
