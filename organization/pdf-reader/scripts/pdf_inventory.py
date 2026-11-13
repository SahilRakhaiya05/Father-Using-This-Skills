#!/usr/bin/env python3
"""Quick inventory of a PDF to choose a reading strategy.

Usage: pdf_inventory.py FILE.pdf [--sample N]
"""
import re
import sys
from collections import Counter
from pypdf import PdfReader


def outline_lines(reader, items, depth=0, out=None):
    out = [] if out is None else out
    for it in items:
        if isinstance(it, list):
            outline_lines(reader, it, depth + 1, out)
        else:
            try:
                pg = reader.get_destination_page_number(it) + 1
            except Exception:
                pg = "?"
            out.append(f"{'  ' * depth}- {it.title} (p. {pg})")
    return out


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    path = sys.argv[1]
    sample = 10
    if "--sample" in sys.argv:
        sample = int(sys.argv[sys.argv.index("--sample") + 1])
    r = PdfReader(path)
    if r.is_encrypted:
        try:
            r.decrypt("")
        except Exception:
            pass
        print("encrypted: yes (needs a password if text extraction fails)")
    n = len(r.pages)
    print(f"file: {path}\npages: {n}")

    sizes = Counter()
    for p in r.pages:
        w, h = float(p.mediabox.width), float(p.mediabox.height)
        if p.get("/Rotate", 0) in (90, 270):
            w, h = h, w
        sizes[(round(w), round(h), "landscape" if w > h else "portrait")] += 1
    for (w, h, o), c in sizes.most_common():
        print(f"page size: {w}x{h} pt, {o} - {c} page(s)")

    idx = sorted(set([int(i * (n - 1) / max(sample - 1, 1)) for i in range(min(sample, n))]))
    chars, imgs = [], []
    for i in idx:
        p = r.pages[i]
        try:
            chars.append(len((p.extract_text() or "").strip()))
        except Exception:
            chars.append(0)
        try:
            imgs.append(len(p.images))
        except Exception:
            imgs.append(0)
    avg = sum(chars) / len(chars) if chars else 0
    print(f"sampled pages: {[i + 1 for i in idx]}")
    print(f"chars/page (sampled): avg {avg:.0f}, min {min(chars)}, max {max(chars)}")
    print(f"images/page (sampled): avg {sum(imgs) / len(imgs):.1f}")

    fields = r.get_fields() or {}
    print(f"form fields: {len(fields)}")
    if r.attachments:
        print(f"attachments: {list(r.attachments)}")

    try:
        ol = outline_lines(r, r.outline)
    except Exception:
        ol = []
    if ol:
        print(f"outline ({len(ol)} entries, first 40):")
        print("\n".join(ol[:40]))

    # Fonts tell you before extracting whether a text layer exists (no fonts = image-only pages)
    import subprocess
    n_fonts = None
    try:
        out = subprocess.run(["pdffonts", path], capture_output=True, text=True, timeout=60).stdout
        rows = out.strip().splitlines()[2:]
        n_fonts = len(rows)
        base14 = re.compile(r"^(Helvetica|Times|Courier|Symbol|ZapfDingbats|Arial|TimesNewRoman)", re.I)
        cols = [r_.split() for r_ in rows if len(r_.split()) >= 7]
        not_emb = [c[0] for c in cols if c[-5] == "no" and not base14.match(c[0])]
        no_uni = [c[0] for c in cols if c[-3] == "no" and c[-6] not in ("WinAnsi", "MacRoman", "Standard", "Builtin")]
        print(f"fonts: {n_fonts}" + (f" | not embedded: {not_emb[:5]}" if not_emb else "")
              + (f" | no Unicode map (extracted text may be garbled): {no_uni[:5]}" if no_uni else ""))
    except Exception:
        pass
    # Raster images (vector charts drawn by Excel/matplotlib won't appear here — render the page to see them)
    try:
        out = subprocess.run(["pdfimages", "-list", path], capture_output=True, text=True, timeout=60).stdout
        rows = [r_.split() for r_ in out.strip().splitlines()[2:]]
        big = [r_ for r_ in rows if len(r_) > 4 and r_[3].isdigit() and int(r_[3]) >= 200 and int(r_[4]) >= 200]
        pages_with = sorted({int(r_[0]) for r_ in big})
        print(f"raster images: {len(rows)} ({len(big)} large, on pages {pages_with[:20]}{'…' if len(pages_with) > 20 else ''})")
    except Exception:
        pass
    # Embedded files (spreadsheets, data) are often the real source of the numbers
    try:
        out = subprocess.run(["pdfdetach", "-list", path], capture_output=True, text=True, timeout=60).stdout
        files = [l.split(":", 1)[1].strip() for l in out.splitlines()[1:] if ":" in l]
        if files:
            print(f"embedded files: {files[:10]}  -> pdfdetach -saveall -o outdir {path}")
    except Exception:
        pass
    # Rough reading cost so you can plan (image tokens ≈ width × height ÷ 750 for a rendered page)
    w0, h0, _ = next(iter(sizes))
    img_tokens = int((w0 / 72 * 100) * (h0 / 72 * 100) / 750)
    txt_tokens = int(avg / 4)
    print(f"reading cost (approx, per page): text ~{txt_tokens} tokens, page image at 100 dpi ~{img_tokens} tokens"
          f" -> whole document as text ~{txt_tokens * n:,}, as images ~{img_tokens * n:,}")

    landscape = sum(c for (w, h, o), c in sizes.items() if o == "landscape")
    if fields:
        guess = "FILLABLE FORM - read field values" + (" (pages are image-only: OCR for printed text)" if n_fonts == 0 else "")
    elif (n_fonts == 0) or (avg < 20 and sum(imgs) > 0):
        guess = "SCANNED - use OCR"
    elif landscape > n / 2 and avg < 800:
        guess = "SLIDE DECK - render pages and look at them"
    elif avg > 1500:
        guess = "TEXT-HEAVY - extract text, navigate by outline/grep"
    else:
        guess = "MIXED - extract text, render pages where layout matters"
    print(f"suggested strategy: {guess}")


if __name__ == "__main__":
    main()
