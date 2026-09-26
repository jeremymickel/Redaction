# Renders documentation/image1.png with Pillow (no DrawBot needed).
# Run from the repository root:  python3 documentation/image1.py --output documentation/image1.png
import argparse

from PIL import Image, ImageDraw, ImageFont

parser = argparse.ArgumentParser()
parser.add_argument("--output", default="documentation/image1.png")
args = parser.parse_args()

W, H, M = 2048, 1024, 96
FAMILIES = ["", "10", "20", "35", "50", "70", "100"]
img = Image.new("RGB", (W, H), "white")
d = ImageDraw.Draw(img)

big = ImageFont.truetype("fonts/ttf/Redaction-Regular.ttf", 280)
d.text((M, M - 60), "Redaction", font=big, fill="black")

y = M + 300
size = 72
for fam in FAMILIES:
    for i, style in enumerate(["Regular", "Bold", "Italic"]):
        f = ImageFont.truetype(f"fonts/ttf/Redaction{fam}-{style}.ttf", size)
        label = f"Redaction {fam}".strip() if i == 0 else style
        d.text((M + i * 640, y), label, font=f, fill="black")
    y += size + 12

img.save(args.output)
print("wrote", args.output)
