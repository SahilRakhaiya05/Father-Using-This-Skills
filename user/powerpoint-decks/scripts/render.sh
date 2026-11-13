#!/usr/bin/env bash
# Render a .pptx (or .docx/.pdf) to one PNG per slide plus a contact sheet.
# Usage: render.sh deck.pptx [DPI]
set -euo pipefail
f="$1"; dpi="${2:-60}"
base="$(basename "${f%.*}")"; dir="$(dirname "$f")"; out="$dir/${base}_slides"
mkdir -p "$out"
if [[ "$f" != *.pdf ]]; then
  profile="$(mktemp -d)"
  soffice -env:UserInstallation=file://"$profile" --headless --convert-to pdf --outdir "$out" "$f" >/dev/null 2>&1
  rm -rf "$profile"
  pdf="$out/$base.pdf"
else
  pdf="$f"
fi
pdftoppm -png -r "$dpi" "$pdf" "$out/slide"
python3 - "$out" <<'PY'
import sys, glob, math
from PIL import Image, ImageDraw
d = sys.argv[1]
files = sorted(glob.glob(f"{d}/slide-*.png"))
if not files: sys.exit("no slides rendered")
ims = [Image.open(f) for f in files]
tw = 400; th = int(ims[0].height * tw / ims[0].width)
cols = 4 if len(ims) > 4 else len(ims); rows = math.ceil(len(ims) / cols)
sheet = Image.new("RGB", (cols * (tw + 10) + 10, rows * (th + 30) + 10), "white")
dr = ImageDraw.Draw(sheet)
for i, im in enumerate(ims):
    x, y = 10 + (i % cols) * (tw + 10), 10 + (i // cols) * (th + 30)
    sheet.paste(im.convert("RGB").resize((tw, th)), (x, y + 20))
    dr.text((x, y + 4), f"{i+1}", fill="black")
sheet.save(f"{d}/contact_sheet.png")
print(f"{len(files)} slides -> {d}/ (contact_sheet.png)")
PY
