#!/usr/bin/env python3
"""Run Fontspector on a folder of fonts, one job per family.

Fonts are grouped by family from the file name (everything before the first
"-"), so a folder holding several related families, like Redaction's seven
optical sizes, gets one report per family instead of one bogus combined
"family". For each family it writes <out>/<Family>.html and .md, plus an
index at <out>/fontspector-report.html with the totals, and prints a table.

    python3 scripts/qa.py                              # Redaction repo defaults
    python3 scripts/qa.py path/to/fonts --profile universal --out path/to/reports

Profiles: googlefonts (default, what Google's onboarders run), universal
(same checks minus the Google Fonts policy ones, right for retail fonts),
opentype, adobefonts, fontwerk, etc. Run `fontspector --list-profiles`.

One check is excluded by default: googlefonts/repo/dirname_matches_nameid_1
expects fonts to live in a directory named after the family, which is the
layout of the google/fonts repository, not of a build folder.

Exit status is 1 if any family has a FAIL or ERROR, so it works in CI.
"""
import argparse
import html
import os
import re
import subprocess
import sys
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
COLUMNS = ["ERROR", "FAIL", "WARN", "INFO", "PASS", "SKIP"]
FONT_EXT = (".ttf", ".otf")


def families(folder, recursive):
    fams = OrderedDict()
    if recursive:
        paths = [os.path.join(d, f) for d, _, fs in os.walk(folder) for f in fs]
    else:
        paths = [os.path.join(folder, f) for f in os.listdir(folder)]
    for p in sorted(paths):
        if p.lower().endswith(FONT_EXT):
            fams.setdefault(os.path.basename(p).split("-")[0], []).append(p)
    return fams


def summary(md_path):
    """Totals from the markdown report's summary table, keyed by status name."""
    if not os.path.exists(md_path):
        return {}
    text = open(md_path, encoding="utf-8").read()
    m = re.search(r"### Summary\s*\n\s*\|([^\n]*)\|\s*\n\s*\|[-| ]*\|\s*\n\s*\|([^\n]*)\|", text)
    if not m:
        return {}
    heads = [re.sub(r"[^A-Z]", "", h) for h in m.group(1).split("|")]
    nums = [n.strip() for n in m.group(2).split("|")]
    return {h: int(n) for h, n in zip(heads, nums) if h and n.isdigit()}


def main():
    ap = argparse.ArgumentParser(description="Fontspector, one run per family.")
    ap.add_argument("fonts", nargs="?", default=os.path.join(REPO, "fonts", "ttf"), help="folder of .ttf/.otf files")
    ap.add_argument("--profile", default="googlefonts")
    ap.add_argument("--out", help="report folder (default: <fonts>/../../out/fontspector for the repo, else <fonts>/fontspector-reports)")
    ap.add_argument("--recursive", action="store_true", help="also look in subfolders")
    ap.add_argument("--exclude", action="append", default=["googlefonts/repo/dirname_matches_nameid_1"], help="check id to skip (repeatable)")
    ap.add_argument("--loglevel", default="warn", help="lowest status to report: error, fail, warn, info, pass")
    args = ap.parse_args()

    fonts = os.path.abspath(args.fonts)
    if not os.path.isdir(fonts):
        sys.exit(f"not a folder: {fonts}")
    out = args.out or (os.path.join(REPO, "out", "fontspector") if fonts.startswith(REPO) else os.path.join(fonts, "fontspector-reports"))
    os.makedirs(out, exist_ok=True)
    fams = families(fonts, args.recursive)
    if not fams:
        sys.exit(f"no fonts found in {fonts}")

    results = OrderedDict()
    for fam, files in fams.items():
        cmd = ["fontspector", "--profile", args.profile, "-l", args.loglevel, "--succinct", "--full-lists",
               "--html", os.path.join(out, fam + ".html"), "--ghmarkdown", os.path.join(out, fam + ".md")]
        for x in args.exclude:
            cmd += ["-x", x]
        subprocess.run(cmd + files, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        results[fam] = summary(os.path.join(out, fam + ".md"))

    rows = "".join(f"<tr><td><a href='{html.escape(f)}.html'>{html.escape(f)}</a></td>"
                   + "".join(f"<td>{s.get(c, 0)}</td>" for c in COLUMNS) + "</tr>" for f, s in results.items())
    page = f"""<!doctype html><meta charset="utf-8"><title>Fontspector reports</title>
<style>body{{font:15px/1.5 system-ui,sans-serif;margin:2rem;max-width:52rem}}table{{border-collapse:collapse}}
td,th{{padding:.3rem .8rem;border-bottom:1px solid #ddd;text-align:right}}td:first-child,th:first-child{{text-align:left}}</style>
<h1>Fontspector, {html.escape(args.profile)} profile</h1>
<p>Fonts: <code>{html.escape(fonts)}</code>. One report per family. Excluded checks: <code>{html.escape(", ".join(args.exclude))}</code>.</p>
<table><tr><th>Family</th>{"".join(f"<th>{c}</th>" for c in COLUMNS)}</tr>{rows}</table>"""
    open(os.path.join(out, "fontspector-report.html"), "w", encoding="utf-8").write(page)

    width = max(len(f) for f in results)
    print(f"{'family':{width}}  " + "  ".join(f"{c:>5}" for c in COLUMNS))
    for fam, s in results.items():
        print(f"{fam:{width}}  " + "  ".join(f"{s.get(c, 0):>5}" for c in COLUMNS))
    print(f"reports: {out}")
    sys.exit(1 if any(s.get("FAIL", 0) or s.get("ERROR", 0) for s in results.values()) else 0)


if __name__ == "__main__":
    main()
