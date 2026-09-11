#!/usr/bin/env python3
"""Check a Markdown file's internal anchor links against its headings.

An internal link like [x](#some-heading) only works if #some-heading matches a
heading's generated id. When it doesn't (a stray hyphen, a renamed heading, a
slug authored for a different tool) Word/Pages silently jump to the top of the
document. This catches those before conversion.

Heading ids come from pandoc's OWN AST using the same identifier extension the
converter uses (gfm_auto_identifiers), so what we check is exactly what ends up
in the .docx/.pdf — no reimplementing slug rules.

Modes:
  check_links.py <file.md>                   report broken links (human, stderr)
  check_links.py --json <file.md>            machine-readable findings (stdout)
  check_links.py --fix <file.md>             rewrite confident fixes into the file
  check_links.py --reconcile <file.md>       like --fix, but phrased for a throwaway
                                             working copy (source left untouched)
  check_links.py --apply <a> <sug> <file>    rewrite one chosen anchor -> sug
                                             (for the TUI's per-link accept flow)

A "confident" suggestion is a single heading whose id, with runs of hyphens
collapsed, equals the broken anchor collapsed the same way (e.g. the classic
'part-iii--the-framework' vs 'part-iii---the-framework'). Otherwise the closest
heading is offered as an unconfident hint (reported, never auto-applied).

Exit status: 0 = no broken links (or all fixed), 1 = broken links remain.
"""
import sys
import os
import re
import json
import difflib
import subprocess

FROM_FORMAT = "markdown+gfm_auto_identifiers"


def _norm(s):
    """Collapse hyphen runs and lowercase — for confident near-miss matching."""
    return re.sub(r'-+', '-', s).strip('-').lower()


def _inline_text(inlines):
    """Flatten a list of pandoc inline nodes to plain text (for the heading label)."""
    out = []
    for n in inlines:
        t = n.get("t")
        if t == "Str":
            out.append(n["c"])
        elif t in ("Space", "SoftBreak", "LineBreak"):
            out.append(" ")
        elif t in ("Emph", "Strong", "Strikeout", "Superscript", "Subscript",
                   "SmallCaps", "Underline"):
            out.append(_inline_text(n["c"]))
        elif t == "Quoted":
            out.append(_inline_text(n["c"][1]))
        elif t in ("Link", "Span"):
            out.append(_inline_text(n["c"][1]))
        elif t == "Code":
            out.append(n["c"][1])
    return "".join(out)


def _walk(node, headings, links):
    """Collect (id -> heading text) and internal link anchors from the AST."""
    if isinstance(node, dict):
        t = node.get("t")
        if t == "Header":
            hid = node["c"][1][0]
            if hid:
                headings[hid] = _inline_text(node["c"][2])
        elif t == "Link":
            url = node["c"][2][0]
            if url.startswith("#") and len(url) > 1:
                links.append(url[1:])
        for v in node.get("c", []) if isinstance(node.get("c"), list) else []:
            _walk(v, headings, links)
        # 'c' may itself hold nested lists/dicts handled by the loop above.
    elif isinstance(node, list):
        for v in node:
            _walk(v, headings, links)


def analyze(path):
    ast = json.loads(subprocess.check_output(
        ["pandoc", path, "--from", FROM_FORMAT, "--to", "json"],
        stderr=subprocess.DEVNULL))
    headings, links = {}, []
    _walk(ast.get("blocks", []), headings, links)

    ids = set(headings)
    norm_index = {}
    for hid in headings:
        norm_index.setdefault(_norm(hid), []).append(hid)

    findings = []
    seen = set()
    for anchor in links:
        if anchor in ids or anchor in seen:
            continue
        seen.add(anchor)
        matches = norm_index.get(_norm(anchor), [])
        if len(matches) == 1:
            sug = matches[0]
            findings.append({"anchor": anchor, "suggestion": sug,
                             "heading": headings[sug], "confident": True})
        else:
            close = difflib.get_close_matches(anchor, list(ids), n=1, cutoff=0.5)
            sug = close[0] if close else None
            findings.append({"anchor": anchor, "suggestion": sug,
                             "heading": headings.get(sug) if sug else None,
                             "confident": False})
    return findings


def apply_fixes(path, findings, working=False):
    """Rewrite confident [x](#anchor) targets. Returns count fixed.

    working=True means path is the throwaway working copy (source untouched) —
    phrased as 'reconciled ... for the output' so it's clear the user's file
    isn't being edited.
    """
    with open(path, encoding="utf-8") as f:
        text = f.read()
    fixed = 0
    for fnd in findings:
        if not fnd["confident"]:
            continue
        anchor, sug = fnd["anchor"], fnd["suggestion"]
        # Match the anchor only as a link target: ](#anchor) up to ) space or "
        pat = re.compile(r'(\]\(#)' + re.escape(anchor) + r'(?=[)\s"])')
        text, n = pat.subn(r'\g<1>' + sug, text)
        if n:
            fixed += 1
            if working:
                print("[info]  reconciled '#%s' -> '#%s' for the output "
                      "(source unchanged)" % (anchor, sug), file=sys.stderr)
            else:
                print("[ok]    fixed '#%s' -> '#%s' in the source"
                      % (anchor, sug), file=sys.stderr)
    if fixed:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    return fixed


def apply_one(path, anchor, suggestion):
    """Rewrite a single [x](#anchor) target to #suggestion. Returns count."""
    with open(path, encoding="utf-8") as f:
        text = f.read()
    pat = re.compile(r'(\]\(#)' + re.escape(anchor) + r'(?=[)\s"])')
    text, n = pat.subn(r'\g<1>' + suggestion, text)
    if n:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
    return n


def report(findings):
    for f in findings:
        print("[warn]  Internal link '#%s' matches no heading." % f["anchor"],
              file=sys.stderr)
        if f["suggestion"] and f["confident"]:
            print("        Did you mean '#%s'  (# %s)?" % (f["suggestion"], f["heading"]),
                  file=sys.stderr)
        elif f["suggestion"]:
            print("        Closest heading: '#%s'  (# %s)  — unsure, please verify."
                  % (f["suggestion"], f["heading"]), file=sys.stderr)
        else:
            print("        No similar heading found.", file=sys.stderr)


def main():
    args = sys.argv[1:]
    # --apply <anchor> <suggestion> <file>: rewrite one link, no analysis.
    if args and args[0] == "--apply":
        if len(args) != 4 or not os.path.isfile(args[3]):
            print("usage: check_links.py --apply <anchor> <suggestion> <file.md>", file=sys.stderr)
            return 2
        return 0 if apply_one(args[3], args[1], args[2]) else 1
    mode = "report"
    if args and args[0] in ("--json", "--fix", "--reconcile"):
        mode = args[0][2:]
        args = args[1:]
    if not args:
        print("usage: check_links.py [--json|--fix|--reconcile] <file.md>", file=sys.stderr)
        return 2
    path = args[0]
    if not os.path.isfile(path):
        print(f"check_links: no such file: {path}", file=sys.stderr)
        return 2
    try:
        findings = analyze(path)
    except Exception:
        return 0  # never block a conversion on the checker itself

    if mode == "json":
        print(json.dumps(findings))
        return 1 if findings else 0
    if mode in ("fix", "reconcile"):
        apply_fixes(path, findings, working=(mode == "reconcile"))
        remaining = [f for f in findings if not f["confident"]]
        if remaining:
            report(remaining)
        return 1 if remaining else 0
    # report
    if findings:
        report(findings)
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
