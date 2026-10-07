#!/usr/bin/env python3
"""Pixelate glyphs from the clean Redaction sources into the bitmap optical sizes.

For each glyph name given, the outline is read from the clean UFO of the same
style (Redaction-Regular/Bold/Italic.ufo), sampled on the pixel grid of each
bitmap family (the family number: 10, 20, 35, 50, 70, 100 units) and written
to the matching bitmap UFO as a rectilinear outline. Unicodes, anchors, lib
(including mark colour) of an existing target glyph are kept; outline and
advance width are replaced.

    python3 scripts/bitmap-from-clean.py uni1E9E
    python3 scripts/bitmap-from-clean.py --compare germandbls B S   # no writing

--compare pixelates the clean glyph and reports how closely the result matches
the glyph already in each bitmap UFO, without changing anything.
"""
import argparse
import glob
import math
import os
import re

import pathops
from fontTools.pens.recordingPen import (
    DecomposingRecordingPen,
    RecordingPen,
    RecordingPointPen,
)
from fontTools.ufoLib.glifLib import GlyphSet
from PIL import Image, ImageChops, ImageDraw

SOURCES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sources")


class Obj:
    pass


def flatten(recording, steps=16):
    polys, cur = [], None
    for op, args in recording:
        if op == "moveTo":
            cur = args[0]
            polys.append([cur])
        elif op == "lineTo":
            cur = args[0]
            polys[-1].append(cur)
        elif op == "curveTo":
            p0, (p1, p2, p3) = cur, args
            for i in range(1, steps + 1):
                t = i / steps
                u = 1 - t
                polys[-1].append((
                    u**3 * p0[0] + 3 * u * u * t * p1[0] + 3 * u * t * t * p2[0] + t**3 * p3[0],
                    u**3 * p0[1] + 3 * u * u * t * p1[1] + 3 * u * t * t * p2[1] + t**3 * p3[1],
                ))
            cur = p3
        elif op == "qCurveTo":  # skia sometimes returns quadratics after simplifying
            p0 = cur
            for i in range(len(args) - 1):
                c = args[i]
                if i < len(args) - 2:  # implied on-curve point between two off-curves
                    n = ((c[0] + args[i + 1][0]) / 2, (c[1] + args[i + 1][1]) / 2)
                else:
                    n = args[-1]
                for k in range(1, steps + 1):
                    t = k / steps
                    u = 1 - t
                    polys[-1].append((
                        u * u * p0[0] + 2 * u * t * c[0] + t * t * n[0],
                        u * u * p0[1] + 2 * u * t * c[1] + t * t * n[1],
                    ))
                p0 = n
            cur = args[-1]
    return [p for p in polys if len(p) > 2]


def area(pts):
    return sum(x0 * y1 - x1 * y0 for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1])) / 2


def decomposed(gs, name):
    pen = DecomposingRecordingPen(gs)
    gs[name].draw(pen)
    return pen.value


def coverage(recording, grid, ss=8):
    """Per-cell ink coverage (0-255). Returns (image, X0, Y0, cols, rows) or None if empty."""
    path = pathops.Path()
    pen = path.getPen()
    for op, args in recording:
        getattr(pen, op)(*args)
    path.simplify(fix_winding=True)
    rec = RecordingPen()
    path.draw(rec)
    polys = flatten(rec.value)
    if not polys:
        return None
    xs = [x for p in polys for x, _ in p]
    ys = [y for p in polys for _, y in p]
    X0, Y0 = math.floor(min(xs) / grid) * grid, math.floor(min(ys) / grid) * grid
    cols = max(1, math.ceil((max(xs) - X0) / grid))
    rows = max(1, math.ceil((max(ys) - Y0) / grid))
    px = grid / ss
    img = Image.new("1", (cols * ss, rows * ss), 0)
    for p in polys:
        tmp = Image.new("1", img.size, 0)
        ImageDraw.Draw(tmp).polygon([((x - X0) / px, (Y0 + rows * grid - y) / px) for x, y in p], fill=1)
        img = ImageChops.logical_xor(img, tmp)
    return img.convert("L").resize((cols, rows), Image.BOX), X0, Y0, cols, rows


def cells(recording, grid, threshold=0.5):
    """Set of lit cells (col, row) in grid units from the origin, y up."""
    cov = coverage(recording, grid)
    if cov is None:
        return set()
    small, X0, Y0, cols, rows = cov
    # strokes thinner than the threshold never light a cell on coarse grids,
    # so the cut-off follows the best-covered cell (a hairline keeps one pixel)
    thr = max(1, min(255, max(small.getdata())) * threshold)
    lit = set()
    for r in range(rows):
        for c in range(cols):
            if small.getpixel((c, r)) >= thr:
                lit.add((X0 // grid + c, Y0 // grid + (rows - 1 - r)))
    return lit


def outline(lit, grid):
    """Merge lit cells into rectilinear contours (lists of points)."""
    path = pathops.Path()
    pen = path.getPen()
    for row in sorted({r for _, r in lit}):
        cs = sorted(c for c, r in lit if r == row)
        start = prev = cs[0]
        for c in cs[1:] + [None]:
            if c is not None and c == prev + 1:
                prev = c
                continue
            xa, xb, ya, yb = start * grid, (prev + 1) * grid, row * grid, (row + 1) * grid
            pen.moveTo((xa, ya))
            pen.lineTo((xb, ya))
            pen.lineTo((xb, yb))
            pen.lineTo((xa, yb))
            pen.closePath()
            start = prev = c
    path.simplify(fix_winding=True)
    rec = RecordingPen()
    path.draw(rec)
    contours = []
    for poly in flatten(rec.value):
        pts = [(round(x), round(y)) for x, y in poly]
        if pts[0] == pts[-1]:
            pts = pts[:-1]
        clean = []
        for i, p in enumerate(pts):  # drop points in the middle of straight runs
            a, b = pts[i - 1], pts[(i + 1) % len(pts)]
            if (p[0] - a[0]) * (b[1] - p[1]) != (p[1] - a[1]) * (b[0] - p[0]):
                clean.append(p)
        if len(clean) > 2:
            contours.append(clean)
    return contours


def reference_sign(gs):
    polys = flatten(decomposed(gs, "H"))
    return 1 if area(max(polys, key=lambda p: abs(area(p)))) > 0 else -1


def bitmap_ufos():
    for ufo in sorted(glob.glob(os.path.join(SOURCES, "Redaction*-*.ufo"))):
        fam, style = os.path.basename(ufo)[:-4].split("-")
        grid = re.sub(r"\D", "", fam)
        if grid:
            yield ufo, style, int(grid)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("glyphs", nargs="+")
    ap.add_argument("--compare", action="store_true", help="report match with existing bitmap glyphs; write nothing")
    ap.add_argument("--threshold", type=float, default=0.5, help="cell coverage needed to light a pixel (default 0.5)")
    ap.add_argument("--styles", default="Regular,Bold,Italic", help="comma-separated styles to write, e.g. Regular,Bold")
    args = ap.parse_args()
    styles = set(args.styles.split(","))

    clean = {s: GlyphSet(os.path.join(SOURCES, f"Redaction-{s}.ufo", "glyphs")) for s in ("Regular", "Bold", "Italic")}
    for ufo, style, grid in bitmap_ufos():
        if style not in styles:
            continue
        gs = GlyphSet(os.path.join(ufo, "glyphs"))
        report = []
        for name in args.glyphs:
            src = clean[style]
            if name not in src:
                report.append(f"{name}: not in clean {style}")
                continue
            srcglyph = Obj()
            src.readGlyph(name, srcglyph)
            lit = cells(decomposed(src, name), grid, args.threshold)
            if args.compare:
                if name not in gs:
                    report.append(f"{name}: absent")
                    continue
                old = cells(decomposed(gs, name), grid, 0.5)
                union = len(lit | old) or 1
                report.append(f"{name}: {100 * len(lit & old) / union:.0f}% ({len(lit)} vs {len(old)} px)")
                continue
            contours = outline(lit, grid)
            if contours:
                sign = reference_sign(gs)
                biggest = max(contours, key=lambda p: abs(area(p)))
                if (1 if area(biggest) > 0 else -1) != sign:
                    contours = [list(reversed(c)) for c in contours]
            g = Obj()
            if name in gs:
                gs.readGlyph(name, g, RecordingPointPen())
            else:
                g.unicodes = list(getattr(srcglyph, "unicodes", None) or [])
                g.lib = {}
            g.width = max(grid, round(srcglyph.width / grid) * grid)

            def draw(pointPen, contours=contours):
                for c in contours:
                    pointPen.beginPath()
                    for p in c:
                        pointPen.addPoint(p, "line")
                    pointPen.endPath()

            gs.writeGlyph(name, g, drawPointsFunc=draw)
            report.append(f"{name}: {len(lit)} px, width {g.width}")
        if not args.compare:
            gs.writeContents()
        print(f"{os.path.basename(ufo):26s} " + "  ".join(report))


if __name__ == "__main__":
    main()
