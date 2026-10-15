#!/usr/bin/env python3
"""Turn one golden run into text that can be compared exactly.

  collect.py <work-dir> <result-dir> <repo-root>

- every output file: a .docx is unzipped and its XML parts pretty-printed one
  per file (media listed by hash); a .md is copied; a .pdf is only noted as
  present - its bytes carry a build date, and pandoc's LaTeX for it is already
  recorded by the pandoc wrapper;
- the source files after the run (--fix-links rewrites them);
- then every text file in the result has the run's own paths and today's
  date replaced by placeholders, and terminal colours stripped.

Standard library only: it runs in the tools image.
"""
import datetime
import hashlib
import os
import re
import shutil
import sys
import zipfile
from xml.dom import minidom

ANSI = re.compile(r"\x1b\[[0-9;]*m")


def pretty(xml: bytes) -> str:
    try:
        return minidom.parseString(xml).toprettyxml(indent="  ")
    except Exception:  # noqa: BLE001 - keep it comparable even if odd
        return xml.decode("utf-8", "replace")


def collect_docx(path: str, dest: str):
    os.makedirs(dest, exist_ok=True)
    media = []
    with zipfile.ZipFile(path) as z:
        for name in sorted(z.namelist()):
            data = z.read(name)
            if name.endswith((".xml", ".rels")):
                target = os.path.join(dest, name.replace("/", "__"))
                with open(target, "w", encoding="utf-8") as fh:
                    fh.write(pretty(data))
            else:
                media.append(f"{name}  {hashlib.sha256(data).hexdigest()[:16]}  {len(data)} bytes")
    with open(os.path.join(dest, "MEDIA.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(media) + ("\n" if media else ""))


def collect_outputs(work: str, result: str):
    out_dir = os.path.join(work, "output")
    dest = os.path.join(result, "output")
    os.makedirs(dest, exist_ok=True)
    listing = []
    for root, _dirs, files in os.walk(out_dir):
        for name in sorted(files):
            path = os.path.join(root, name)
            rel = os.path.relpath(path, out_dir)
            listing.append(rel)
            if name.endswith(".docx"):
                collect_docx(path, os.path.join(dest, rel.replace("/", "__")))
            elif name.endswith((".md", ".tex", ".yaml")):
                shutil.copy(path, os.path.join(dest, rel.replace("/", "__")))
    with open(os.path.join(dest, "FILES.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(sorted(listing)) + ("\n" if listing else ""))


def collect_sources(work: str, result: str):
    dest = os.path.join(result, "sources-after")
    os.makedirs(dest, exist_ok=True)
    for name in sorted(os.listdir(work)):
        if name.endswith(".md"):
            shutil.copy(os.path.join(work, name), dest)


def today_forms():
    d = datetime.date.today()
    return [d.strftime("%d %B %Y").lstrip("0"), d.strftime("%d %B %Y"), d.isoformat()]


def normalise(result: str, work: str, engine_dir: str):
    subs = [(work, "<WORK>"), (os.path.realpath(work), "<WORK>"), (engine_dir, "<REPO>")]
    for root, _dirs, files in os.walk(result):
        for name in files:
            path = os.path.join(root, name)
            try:
                with open(path, encoding="utf-8") as fh:
                    text = fh.read()
            except UnicodeDecodeError:
                continue
            new = ANSI.sub("", text)
            for old, placeholder in subs:
                new = new.replace(old, placeholder)
            for form in today_forms():
                new = new.replace(form, "<TODAY>")
            if new != text:
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(new)


def main(argv):
    work, result, engine_dir = argv[1], argv[2], argv[3]
    collect_outputs(work, result)
    collect_sources(work, result)
    normalise(result, work, engine_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
