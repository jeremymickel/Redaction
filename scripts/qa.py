#!/usr/bin/env python3
"""Run Fontspector's Google Fonts profile on each Redaction family separately.

The repo holds seven related families (Redaction, Redaction 10 ... 100). Running
Fontspector on all 21 fonts at once would treat them as one family and trip the
family-consistency checks, so this runs one job per family and writes:

    out/fontspector/<Family>.html / .md      one report per family
    out/fontspector/fontspector-report.html  an index with the totals

One check is excluded: googlefonts/repo/dirname_matches_nameid_1 expects the
fonts to live in a directory named after the family, which is the layout of the
google/fonts repository, not of an upstream repo like this one.

Usage:  python3 scripts/qa.py            (after a build; fonts/ttf must exist)
Exit status is 1 if any family has a FAIL or ERROR.
"""
import html
import os
import re
import subprocess
import sys
from collections import OrderedDict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TTF = os.path.join(ROOT, "fonts", "ttf")
OUT = os.path.join(ROOT, "out", "fontspector")
EXCLUDE = ["googlefonts/repo/dirname_matches_nameid_1"]
COLUMNS = ["FAIL", "WARN", "INFO", "PASS", "SKIP"]


def families():
    fams = OrderedDict()
    for f in sorted(os.listdir(TTF)):
        if f.endswith(".ttf"):
            fams.setdefault(f.split("-")[0], []).append(os.path.join(TTF, f))
    return fams


def summary(md_path):
    """Totals from the markdown report's summary table, keyed by status name."""
    text = open(md_path, encoding="utf-8").read()
    m = re.search(r"### Summary\s*\n\s*\|([^\n]*)\|\s*\n\s*\|[-| ]*\|\s*\n\s*\|([^\n]*)\|", text)
    if not m:
        return {}
    heads = [re.sub(r"[^A-Z]", "", h) for h in m.group(1).split("|")]
    nums = [n.strip() for n in m.group(2).split("|")]
    return {h: int(n) for h, n in zip(heads, nums) if h and n.isdigit()}


def main():
    os.makedirs(OUT, exist_ok=True)
    results = OrderedDict()
    for fam, fonts in families().items():
        cmd = ["fontspector", "--profile", "googlefonts", "-l", "warn", "--succinct", "--full-lists",
               "--html", os.path.join(OUT, fam + ".html"), "--ghmarkdown", os.path.join(OUT, fam + ".md")]
        for x in EXCLUDE:
            cmd += ["-x", x]
        subprocess.run(cmd + fonts, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        results[fam] = summary(os.path.join(OUT, fam + ".md"))

    rows = []
    for fam, s in results.items():
        rows.append(f"<tr><td><a href='{html.escape(fam)}.html'>{html.escape(fam)}</a></td>"
                    + "".join(f"<td>{s.get(c, 0)}</td>" for c in COLUMNS) + "</tr>")
    page = f"""<!doctype html><meta charset="utf-8"><title>Redaction Fontspector reports</title>
<style>body{{font:15px/1.5 system-ui,sans-serif;margin:2rem;max-width:48rem}}table{{border-collapse:collapse}}
td,th{{padding:.3rem .8rem;border-bottom:1px solid #ddd;text-align:right}}td:first-child,th:first-child{{text-align:left}}</style>
<h1>Fontspector, Google Fonts profile</h1>
<p>One report per family. The check <code>googlefonts/repo/dirname_matches_nameid_1</code> is excluded
because it describes the google/fonts directory layout, not an upstream repository.</p>
<table><tr><th>Family</th>{"".join(f"<th>{c}</th>" for c in COLUMNS)}</tr>{"".join(rows)}</table>"""
    open(os.path.join(OUT, "fontspector-report.html"), "w", encoding="utf-8").write(page)

    width = max(len(f) for f in results)
    print(f"{'family':{width}}  " + "  ".join(f"{c:>5}" for c in COLUMNS))
    for fam, s in results.items():
        print(f"{fam:{width}}  " + "  ".join(f"{s.get(c, 0):>5}" for c in COLUMNS))
    bad = sum(s.get("FAIL", 0) + s.get("ERROR", 0) for s in results.values())
    print(f"reports: {OUT}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
