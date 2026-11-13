---
name: pdf-tools
description: Use when the user wants to create, merge, split, rotate, watermark, compress, encrypt/decrypt, fill forms in, or OCR PDF files. For only reading or extracting content from a PDF, use pdf-reader instead.
license: MIT. Complete terms in LICENSE.txt
---

# PDF Tools

Tools: **pypdf** (page operations, forms, encryption), **reportlab** (drawing new PDFs), **qpdf** (repair, linearize, fast merges), **ocrmypdf / tesseract** (OCR), **LibreOffice** or **pandoc** (convert other documents to PDF).

## 1. Pick the route

| Task | Route |
|---|---|
| New PDF with designed layout | reportlab Platypus (section 2), or HTML → PDF via a headless browser |
| New PDF from Word/PowerPoint/Markdown | `soffice --headless --convert-to pdf file.docx` / `pandoc in.md -o out.pdf` |
| Merge, split, reorder, rotate | `scripts/pdfops.py` or qpdf |
| Watermark / stamp every page | `scripts/pdfops.py stamp` |
| Fill a form (fillable or flat) | `scripts/form_tools.py` (section 5) |
| Scanned PDF → searchable | `ocrmypdf in.pdf out.pdf` |
| Password protect / remove | section 6 |
| Shrink file size | section 7 |

Never modify the user's original; write a new file.

## 2. Create a PDF with reportlab

```python
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Built-in Helvetica can't draw ₹ or non-Latin text — register a Unicode TTF and use it everywhere
pdfmetrics.registerFont(TTFont("Body", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"))
pdfmetrics.registerFont(TTFont("Body-Bold", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"))

doc = SimpleDocTemplate("out.pdf", pagesize=A4,
                        leftMargin=20*mm, rightMargin=20*mm, topMargin=20*mm, bottomMargin=20*mm,
                        title="Invoice 1042", author="Acme")
ss = getSampleStyleSheet()
body = ParagraphStyle("body", parent=ss["BodyText"], fontName="Body", fontSize=10.5, leading=14)
title = ParagraphStyle("title", parent=ss["Title"], fontName="Body-Bold")

story = [Paragraph("Invoice #1042", title),
         Paragraph("Issued 5 Nov 2026 · Due 5 Dec 2026", body),
         Spacer(1, 8*mm)]

data = [["Item", "Qty", "Price"], ["Design work", "10 h", "₹25,000"], ["Hosting", "1", "₹2,000"]]
t = Table(data, colWidths=[100*mm, 25*mm, 35*mm])
t.setStyle(TableStyle([
    ("FONTNAME", (0, 0), (-1, -1), "Body"), ("FONTNAME", (0, 0), (-1, 0), "Body-Bold"),
    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
    ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f4f6")]),
    ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d1d5db")),
    ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
]))
story.append(t)

def footer(canvas, doc):
    canvas.setFont("Body", 8)
    canvas.drawRightString(A4[0] - 20*mm, 10*mm, f"Page {doc.page}")

doc.build(story, onFirstPage=footer, onLaterPages=footer)
```

Fonts: the built-in fonts (Helvetica, Times) cover basic Latin only — ₹ comes out as a wrong glyph. Always register a TTF as above (`fc-list` shows what's installed). Complex scripts (Devanagari, Arabic) need text shaping, which reportlab lacks — render HTML in a headless browser (`page.pdf()` in Playwright) instead.

## 3. Page operations — `scripts/pdfops.py`

```bash
python3 scripts/pdfops.py merge out.pdf a.pdf b.pdf c.pdf
python3 scripts/pdfops.py split in.pdf outdir/                 # one file per page
python3 scripts/pdfops.py extract in.pdf out.pdf 1-3,7,10-     # 1-based ranges
python3 scripts/pdfops.py rotate in.pdf out.pdf 90 2,4         # pages optional (default all)
python3 scripts/pdfops.py stamp in.pdf out.pdf "CONFIDENTIAL"  # diagonal text watermark
python3 scripts/pdfops.py info in.pdf
```

qpdf equivalents (fast, preserves everything):

```bash
qpdf --empty --pages a.pdf b.pdf -- merged.pdf
qpdf in.pdf --pages . 1-3,7 -- part.pdf
qpdf in.pdf --rotate=+90:2,4 out.pdf
```

## 4. Overlay content on existing pages

```python
from pypdf import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
import io

reader = PdfReader("in.pdf"); writer = PdfWriter()
for page in reader.pages:
    w, h = float(page.mediabox.width), float(page.mediabox.height)
    buf = io.BytesIO(); c = canvas.Canvas(buf, pagesize=(w, h))
    c.setFont("Helvetica", 9); c.drawString(36, 20, "Approved – 5 Nov 2026"); c.save()
    page.merge_page(PdfReader(buf).pages[0])
    writer.add_page(page)
writer.write("stamped.pdf")
```

## 5. Fill any form — `scripts/form_tools.py`

Works for both kinds of form and checks its own work.

**Step 1 — which kind is it?**
```bash
python3 scripts/form_tools.py fields form.pdf            # lists fillable fields, or says "flat form"
```

**Fillable form (has fields):**
```bash
python3 scripts/form_tools.py fields form.pdf --json fields.json      # names, types, allowed values
echo '{"full_name":"Asha Rao","agree":true,"state":"Karnataka","plan":"pro"}' > values.json
python3 scripts/form_tools.py fill form.pdf values.json filled.pdf     # validates every value, reads it back
```
Checkboxes take `true/false`; radio buttons and dropdowns are checked against their allowed values before anything is written, so a typo fails loudly instead of silently leaving a blank.

**Flat form (printed lines and boxes, no fields)** — most government, bank and school forms:
```bash
python3 scripts/form_tools.py layout form.pdf layout.json                 # finds every answer spot + its label
python3 scripts/form_tools.py preview form.pdf spots.png --layout layout.json   # LOOK at this before filling
# answers keyed by the spot's key, id (f3) or label text:
echo '{"full_name":"Asha Rao","date_of_birth":"14-02-1990","address":"Flat 4B, Baner Road, Pune 411045","savings":true}' > answers.json
python3 scripts/form_tools.py fill-flat form.pdf layout.json answers.json filled.pdf
python3 scripts/form_tools.py verify filled.pdf layout.json answers.json --original form.pdf
```

What `layout` detects: answer lines (drawn rules, thin rectangles, typed `______`), answer boxes (tall rectangles, with labels inside or beside them), checkboxes (small squares or ☐ glyphs) with the label to their right. Each spot gets a readable key from its label.

What `fill-flat` does: picks a font that actually contains your characters (₹, accented names, Hindi, Tamil, Arabic…), shapes Indian and Arabic scripts properly so letters join correctly, shrinks long answers to fit, wraps multi-line answers from the top of tall boxes, and ticks checkboxes with ✓.

What `verify` does: reads every box back and confirms the value is inside it (ignoring the form's own underscores), checks ticks, and for complex scripts compares ink against the blank form. Exit 1 names any misplaced answer.

When detection misses a spot (unusual layouts, scanned forms): open the preview image, then add the spot to `layout.json` by hand — `{"id":"f9","key":"pan","label":"PAN","page":1,"kind":"text","box":[x0, top, x1, bottom]}` in points from the top-left (rendered pixels ÷ (dpi/72)). For scanned forms run OCR first (section 8) so labels can be found.

Never invent answers: leave a spot empty and list it for the user when you don't have the information. Signatures: leave for the user unless they provide an image of their signature and ask you to place it.

## 6. Encrypt / decrypt

```python
w = PdfWriter(clone_from="in.pdf"); w.encrypt(user_password="open123", owner_password="admin456", algorithm="AES-256"); w.write("locked.pdf")
r = PdfReader("locked.pdf"); r.decrypt("open123"); PdfWriter(clone_from=r).write("unlocked.pdf")
```

Only remove a password the user says they own or know.

## 7. Compress / repair

```bash
qpdf --object-streams=generate --compress-streams=y --recompress-flate in.pdf smaller.pdf
qpdf in.pdf repaired.pdf                     # rewrites a damaged file
gs -sDEVICE=pdfwrite -dPDFSETTINGS=/ebook -o smaller.pdf in.pdf   # if ghostscript exists: downsamples images
```

## 8. OCR

```bash
ocrmypdf --skip-text -l eng in.pdf searchable.pdf        # add -l eng+hin for Hindi
```

Without ocrmypdf: `pdftoppm -r 300 -png in.pdf pg` then `tesseract pg-1.png out -l eng pdf` per page and merge.

## 8b. Less common jobs

| Job | How |
|---|---|
| Text with exact positions (for custom extraction) | `pdftotext -bbox-layout in.pdf out.html` (every word with its box) or `pdfplumber` `page.extract_words()` |
| Crop pages (remove margins, cut a region) | `page.cropbox.lower_left = (x0, y0)`; `page.cropbox.upper_right = (x1, y1)` with pypdf, then write |
| Pull out embedded pictures in original quality | `pdfimages -all in.pdf img` (JPEG stays JPEG); `pdfimages -list` first |
| Files attached inside a PDF | `pdfdetach -list in.pdf`; `pdfdetach -saveall -o outdir in.pdf` |
| Make a big PDF open fast on the web | `qpdf --linearize in.pdf out.pdf` |
| Split into groups of pages | `qpdf --split-pages=10 in.pdf out-%d.pdf` |
| Repair a damaged file | `qpdf in.pdf fixed.pdf` (rewrites structure); if that fails, print to PDF again through LibreOffice or a browser |
| Inspect structure when something is odd | `qpdf --check in.pdf`, `qpdf --show-encryption in.pdf` |
| Batches of files | loop with try/except per file, log failures, never stop the whole batch on one bad PDF |
| Very large PDFs | process page by page; render only the pages you need; use `pdftotext -f N -l M` |
| PDF from HTML with perfect fonts (Hindi, emoji, CSS layout) | Playwright `page.pdf(path=..., format="A4", print_background=True)` |

## 9. Verify

```bash
python3 scripts/pdfops.py info out.pdf
pdftoppm -png -r 60 -f 1 -l 3 out.pdf check      # look at check-1.png …
```

Check page count, orientation, that text is selectable where expected, and that nothing is clipped at the margins.
