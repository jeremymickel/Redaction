#!/usr/bin/env python3
"""Add a STAT table to the static Redaction fonts.

gftools-builder only generates STAT tables for variable fonts, but Fontbakery's
Google Fonts profile (opentype/STAT/ital_axis, STAT_in_statics) expects every
font in a family that has Italic styles to carry one, with exactly one axis
value per axis describing that font's own position. Each family here is
Regular / Bold / Italic, so:

    Regular  wght=400 (elidable, linked to 700)  ital=0 (elidable, linked to 1)
    Bold     wght=700                            ital=0 (elidable, linked to 1)
    Italic   wght=400 (elidable, linked to 700)  ital=1

Usage:  python3 scripts/add-stat.py fonts/ttf/*.ttf fonts/otf/*.otf fonts/webfonts/*.woff2
"""
import sys

from fontTools.otlLib.builder import buildStatTable
from fontTools.ttLib import TTFont

ELIDABLE = 0x2


def axes_for(font):
    weight = font["OS/2"].usWeightClass
    italic = bool(font["OS/2"].fsSelection & 0x1)
    if weight == 700:
        wght = dict(value=700, name="Bold")
    else:
        wght = dict(value=400, name="Regular", linkedValue=700, flags=ELIDABLE)
    if italic:
        ital = dict(value=1, name="Italic")
    else:
        ital = dict(value=0, name="Roman", linkedValue=1, flags=ELIDABLE)
    return [
        dict(tag="wght", name="Weight", values=[wght]),
        dict(tag="ital", name="Italic", values=[ital]),
    ]


for path in sys.argv[1:]:
    font = TTFont(path)
    buildStatTable(font, axes_for(font), elidedFallbackName=2)
    font.save(path)
    print("STAT added:", path)
