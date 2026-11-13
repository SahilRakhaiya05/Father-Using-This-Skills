---
name: pdf-reader
description: Use when you need to read, inspect or extract content from a PDF — text, tables, images, form values, or a visual look at pages — and choose the right strategy for text-heavy, scanned, slide-style, form or data-heavy PDFs. Not for creating or modifying PDFs (use pdf-tools).
license: MIT. Complete terms in LICENSE.txt
---

# PDF Reader

Read the right amount, the right way. A 300-page PDF should not be dumped whole into context.

## 1. Take inventory first

```bash
python3 scripts/pdf_inventory.py file.pdf
```

Reports page count, page sizes, embedded fonts (none = image-only/scanned pages, so skip straight to OCR instead of getting an empty text result first), whether there's a text layer, characters per page, image count, form fields, and an outline (bookmarks) if present. Use it to choose a strategy:

| Inventory says | Document type | Strategy |
|---|---|---|
| Lots of text per page, outline present | Report / book / paper | Section 2 — text, guided by the outline |
| ~0 characters per page, 1 big image per page | Scanned | Section 4 — OCR |
| Little text, landscape pages | Slide deck | Section 5 — look at pages as images |
| Form fields > 0 | Fillable form | Section 6 |
| Many numbers in aligned columns | Statements, invoices, data tables | Section 3 — tables |

What the extra lines mean:
- **fonts … no Unicode map** → text will extract as gibberish; render those pages or OCR them instead.
- **raster images on pages […]** → photos and scanned figures live there. Charts drawn as vectors (Excel, matplotlib) are *not* listed — render the page to see them.
- **embedded files** → the PDF carries attachments (often the spreadsheet behind the tables): extract them and read the data directly.
- **reading cost** → plan before reading: text is cheap, page images are 10–50× more. Render only the pages a question needs; for a long document never render everything.

When precision matters (a table you'll compute from, a chart you'll describe), use **both** the text and the page image for that page: numbers from the text, structure from the picture.

## 2. Text

```bash
pdftotext -layout file.pdf - | head -200          # keeps column alignment
pdftotext -f 10 -l 15 -layout file.pdf out.txt    # page range only
```

Large documents: extract to a file, `grep -n` for the terms you need, then read only those regions. Use the outline from the inventory to jump to a chapter's pages.

Python alternative with per-page control:

```python
import pdfplumber
with pdfplumber.open("file.pdf") as pdf:
    for i, page in enumerate(pdf.pages[9:15], start=10):
        print(f"--- page {i} ---"); print(page.extract_text())
```

Multi-column layouts: if `-layout` interleaves columns, try plain `pdftotext` (no flag), or crop columns with `page.crop((x0, top, x1, bottom))` in pdfplumber.

## 3. Tables

```python
import pdfplumber, pandas as pd
with pdfplumber.open("statement.pdf") as pdf:
    frames = []
    for page in pdf.pages:
        for tbl in page.extract_tables():
            if len(tbl) > 1:
                frames.append(pd.DataFrame(tbl[1:], columns=tbl[0]))
df = pd.concat(frames, ignore_index=True)
```

If borders are missing, use text-based detection:
`page.extract_tables({"vertical_strategy": "text", "horizontal_strategy": "text"})`.
Always clean numbers (`₹`, commas, `(123)` = negative) before maths, and spot-check a few rows against the rendered page.

## 4. Scanned PDFs (OCR)

```bash
pdftoppm -r 300 -png -f 1 -l 3 file.pdf pg       # render pages
tesseract pg-1.png - -l eng                      # add +hin for Hindi, etc.
```

Or make the whole file searchable once: `ocrmypdf --skip-text file.pdf ocr.pdf`, then use section 2. OCR output has errors — double-check names, amounts and dates against the page image.

## 5. Look at pages

For slides, diagrams, charts, signatures, layout questions — or whenever text extraction looks wrong — render and view the page:

```bash
pdftoppm -png -r 80 -f 3 -l 3 file.pdf view      # view-3.png (or view-03.png)
```

Use ~80 dpi for a whole page, 150–200 dpi for fine print. Crop with `-x -y -W -H` (pixels at the chosen dpi) to zoom on a region.

## 6. Forms

```python
from pypdf import PdfReader
r = PdfReader("form.pdf")
for name, f in (r.get_fields() or {}).items():
    print(f"{name}: {f.get('/V')}")
```

## 7. Embedded images and attachments

```bash
pdfimages -list file.pdf            # what's inside
pdfimages -png -f 2 -l 2 file.pdf img   # extract from page 2
pdfdetach -list file.pdf; pdfdetach -saveall file.pdf   # attached files
```

## 8. Encrypted files

`pdftotext` fails with "Incorrect password": ask the user for it, then `qpdf --password=XXX --decrypt in.pdf open.pdf`.

## Reporting back

Lead with the answer, not the method ("The 28-page report puts Q3 revenue at ₹12.3 cr on p. 4", not "Let me check the PDF…"). Cite page numbers for every fact ("p. 14"). Quote exact figures rather than rounding. Say when a page was unreadable or OCR was uncertain.
