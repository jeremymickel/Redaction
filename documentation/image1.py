# Renders documentation/image1.png with Pillow (no DrawBot needed).
# Run from the repository root:  python3 documentation/image1.py --output documentation/image1.png
import argparse

from PIL import Image, ImageDraw, ImageFont

parser = argparse.ArgumentParser()
parser.add_argument("--output", default="documentation/image1.png")
args = parser.parse_args()

W, H, M = 2048, 1024, 96
GAP = 64  # space between columns
FAMILIES = ["", "10", "20", "35", "50", "70", "100"]
STYLES = ["Regular", "Bold", "Italic"]
COLUMN = (W - 2 * M - GAP * (len(STYLES) - 1)) / len(STYLES)  # three equal columns


def label(fam, style):
    return f"Redaction {fam}".strip() + f" {style}"


def font(fam, style, size):
    return ImageFont.truetype(f"fonts/ttf/Redaction{fam}-{style}.ttf", size)


def widest(size):
    return max(font(f, s, size).getlength(label(f, s)) for f in FAMILIES for s in STYLES)


# largest size at which the longest label fills a column
size = 80
while size > 20 and widest(size) > COLUMN:
    size -= 1

img = Image.new("RGB", (W, H), "white")
d = ImageDraw.Draw(img)
d.text((M, M - 60), "Redaction", font=font("", "Regular", 280), fill="black")

top, bottom = M + 300, H - M
step = (bottom - top) / len(FAMILIES)
for row, fam in enumerate(FAMILIES):
    for col, style in enumerate(STYLES):
        x = M + col * (COLUMN + GAP)
        d.text((x, top + row * step), label(fam, style), font=font(fam, style, size), fill="black")

img.save(args.output)
print("wrote", args.output, "at size", size, "| column width", round(COLUMN), "| widest label", round(widest(size)))
