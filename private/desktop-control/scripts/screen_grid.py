#!/usr/bin/env python3
"""Overlay a labelled coordinate grid on a screenshot to read precise click positions.

Usage: screen_grid.py SHOT.png [--step 50] [--crop x,y,w,h] [--zoom 2] [--mark x,y ...] [--out OUT.png]

  --step   grid spacing in screenshot pixels (labels every 2 lines)
  --crop   only this region (coordinates stay in full-screen pixels on the labels)
  --zoom   enlarge the output (useful with --crop)
  --mark   draw a red cross at a planned click point to double-check it before clicking
"""
import sys

from PIL import Image, ImageDraw, ImageFont


def main():
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    src = a[0]
    step = int(a[a.index("--step") + 1]) if "--step" in a else 50
    zoom = float(a[a.index("--zoom") + 1]) if "--zoom" in a else 1.0
    out = a[a.index("--out") + 1] if "--out" in a else src.rsplit(".", 1)[0] + "_grid.png"
    marks = [tuple(int(v) for v in a[i + 1].split(",")) for i, x in enumerate(a) if x == "--mark"]
    im = Image.open(src).convert("RGB")
    ox = oy = 0
    if "--crop" in a:
        x, y, w, h = (int(v) for v in a[a.index("--crop") + 1].split(","))
        im = im.crop((x, y, x + w, y + h))
        ox, oy = x, y
    if zoom != 1:
        im = im.resize((int(im.width * zoom), int(im.height * zoom)), Image.LANCZOS)
    d = ImageDraw.Draw(im, "RGBA")
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", max(10, int(11 * zoom)))
    except Exception:
        font = ImageFont.load_default()
    first_x = ((ox + step - 1) // step) * step
    first_y = ((oy + step - 1) // step) * step
    for gx in range(first_x, ox + int(im.width / zoom) + 1, step):
        px = (gx - ox) * zoom
        major = (gx // step) % 2 == 0
        d.line([(px, 0), (px, im.height)], fill=(255, 0, 80, 110 if major else 50), width=1)
        if major:
            d.rectangle([px + 1, 1, px + 7 * len(str(gx)) * zoom / 1.4 + 4, 14 * zoom], fill=(255, 255, 255, 200))
            d.text((px + 2, 1), str(gx), fill=(200, 0, 60), font=font)
    for gy in range(first_y, oy + int(im.height / zoom) + 1, step):
        py = (gy - oy) * zoom
        major = (gy // step) % 2 == 0
        d.line([(0, py), (im.width, py)], fill=(0, 120, 255, 110 if major else 50), width=1)
        if major:
            d.rectangle([1, py + 1, 7 * len(str(gy)) * zoom / 1.4 + 4, py + 14 * zoom], fill=(255, 255, 255, 200))
            d.text((2, py + 1), str(gy), fill=(0, 80, 200), font=font)
    for mx, my in marks:
        px, py = (mx - ox) * zoom, (my - oy) * zoom
        r = 8 * zoom
        d.line([(px - r, py), (px + r, py)], fill=(255, 0, 0, 255), width=2)
        d.line([(px, py - r), (px, py + r)], fill=(255, 0, 0, 255), width=2)
        d.ellipse([px - r, py - r, px + r, py + r], outline=(255, 0, 0, 255), width=2)
    im.save(out)
    print(f"{out}: {im.width}x{im.height}, grid every {step}px"
          + (f", region from ({ox},{oy})" if (ox or oy) else "") + (f", {len(marks)} mark(s)" if marks else ""))


if __name__ == "__main__":
    main()
