#!/usr/bin/env python3
"""Everyday PDF page operations with pypdf.

  merge   OUT IN1 IN2 ...
  split   IN OUTDIR
  extract IN OUT RANGES          e.g. 1-3,7,10-   (1-based, open-ended allowed)
  rotate  IN OUT DEGREES [RANGES]
  stamp   IN OUT TEXT            diagonal semi-transparent watermark
  info    IN
"""
import io
import os
import sys
from pypdf import PdfReader, PdfWriter


def parse_ranges(spec, n):
    pages = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            a, b = part.split("-", 1)
            a = int(a) if a else 1
            b = int(b) if b else n
            pages.extend(range(a, b + 1))
        else:
            pages.append(int(part))
    bad = [p for p in pages if p < 1 or p > n]
    if bad:
        sys.exit(f"page(s) out of range 1-{n}: {bad}")
    return [p - 1 for p in pages]


def merge(out, *ins):
    w = PdfWriter()
    for f in ins:
        w.append(f)
    w.write(out)
    print(f"merged {len(ins)} files -> {out} ({len(w.pages)} pages)")


def split(src, outdir):
    os.makedirs(outdir, exist_ok=True)
    r = PdfReader(src)
    base = os.path.splitext(os.path.basename(src))[0]
    for i, p in enumerate(r.pages, 1):
        w = PdfWriter()
        w.add_page(p)
        w.write(os.path.join(outdir, f"{base}-{i:03d}.pdf"))
    print(f"split into {len(r.pages)} files in {outdir}")


def extract(src, out, spec):
    r = PdfReader(src)
    w = PdfWriter()
    for i in parse_ranges(spec, len(r.pages)):
        w.add_page(r.pages[i])
    w.write(out)
    print(f"{len(w.pages)} pages -> {out}")


def rotate(src, out, deg, spec=None):
    r = PdfReader(src)
    w = PdfWriter(clone_from=r)
    targets = parse_ranges(spec, len(r.pages)) if spec else range(len(r.pages))
    for i in targets:
        w.pages[i].rotate(int(deg))
    w.write(out)
    print(f"rotated {len(list(targets))} page(s) by {deg} -> {out}")


def stamp(src, out, text):
    from reportlab.pdfgen import canvas
    from reportlab.lib.colors import Color
    r = PdfReader(src)
    w = PdfWriter()
    cache = {}
    for page in r.pages:
        wd, ht = float(page.mediabox.width), float(page.mediabox.height)
        key = (round(wd), round(ht))
        if key not in cache:
            buf = io.BytesIO()
            c = canvas.Canvas(buf, pagesize=(wd, ht))
            size = min(wd, ht) / max(len(text), 6) * 1.4
            c.setFont("Helvetica-Bold", size)
            c.setFillColor(Color(0.6, 0.1, 0.1, alpha=0.18))
            c.translate(wd / 2, ht / 2)
            c.rotate(35)
            c.drawCentredString(0, -size / 3, text)
            c.save()
            cache[key] = PdfReader(buf).pages[0]
        page.merge_page(cache[key])
        w.add_page(page)
    w.write(out)
    print(f"stamped {len(r.pages)} pages -> {out}")


def info(src):
    r = PdfReader(src)
    print(f"file: {src}")
    print(f"pages: {len(r.pages)}  encrypted: {r.is_encrypted}")
    meta = r.metadata or {}
    for k in ("/Title", "/Author", "/Producer"):
        if meta.get(k):
            print(f"{k[1:].lower()}: {meta[k]}")
    sizes = {}
    for p in r.pages:
        k = (round(float(p.mediabox.width)), round(float(p.mediabox.height)))
        sizes[k] = sizes.get(k, 0) + 1
    for (wd, ht), cnt in sizes.items():
        print(f"page size {wd}x{ht} pt ({wd/72*25.4:.0f}x{ht/72*25.4:.0f} mm): {cnt} page(s)")
    has_text = any((p.extract_text() or "").strip() for p in r.pages[:5])
    print(f"text layer (first 5 pages): {'yes' if has_text else 'no - probably scanned'}")
    fields = r.get_fields() or {}
    print(f"form fields: {len(fields)}")


CMDS = {"merge": merge, "split": split, "extract": extract, "rotate": rotate, "stamp": stamp, "info": info}

if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1] not in CMDS:
        sys.exit(__doc__)
    CMDS[sys.argv[1]](*sys.argv[2:])
