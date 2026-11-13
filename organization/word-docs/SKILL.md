---
name: word-docs
description: Use when the user wants to create, read, edit or convert Microsoft Word files (.docx) — reports, letters, resumes, contracts, find-and-replace, tables, images, headers/footers, review comments, tracked changes, or converting a .docx to PDF.
license: MIT. Complete terms in LICENSE.txt
---

# Word Documents (.docx)

Tools: **python-docx** for building and editing, **pandoc** for quick text extraction and Markdown→Word, **LibreOffice** (headless) for PDF conversion and visual checks.

## 1. Decide the route

| Task | Route |
|---|---|
| Read / summarize a .docx | `pandoc file.docx -t markdown` (keeps headings, lists, tables) |
| New document from content | python-docx (section 2) |
| Long prose already in Markdown | `pandoc in.md -o out.docx --reference-doc=style.docx` |
| Edit an existing file | python-docx on a **copy**; keep original styles (section 4) |
| Review comments, tracked changes, accept/reject | `scripts/docx_tools.py` (section 6) |
| Anything else python-docx can't reach (fields, odd XML) | unzip, edit `word/document.xml`, rezip (section 6) |
| Convert to PDF | `scripts/to_pdf.sh file.docx` |
| Check a file is healthy | `scripts/office_check.py file.docx --render` (section 7) |

**Always finish a python-docx file with** `python3 scripts/docx_tools.py fix out.docx` — python-docx's default template leaves a schema gap (zoom setting) that strict validators flag.

## 2. Build a new document

```python
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT

doc = Document()

# Page setup
for s in doc.sections:
    s.top_margin = s.bottom_margin = Cm(2.2)
    s.left_margin = s.right_margin = Cm(2.4)

# Base font
normal = doc.styles["Normal"]
normal.font.name = "Calibri"
normal.font.size = Pt(11)
normal.paragraph_format.space_after = Pt(6)
normal.paragraph_format.line_spacing = 1.15

doc.add_heading("Quarterly Report", level=0)          # title
p = doc.add_paragraph("Prepared for the operations team · November 2026")
p.runs[0].italic = True

doc.add_heading("1. Summary", level=1)
doc.add_paragraph("Revenue grew 12% quarter on quarter, driven by…")

doc.add_paragraph("First key point", style="List Bullet")
doc.add_paragraph("Second key point", style="List Bullet")
doc.add_paragraph("Step one", style="List Number")

# Table
rows = [("Region", "Q2", "Q3"), ("North", "120", "138"), ("South", "95", "101")]
t = doc.add_table(rows=len(rows), cols=3, style="Light Grid Accent 1")
t.alignment = WD_TABLE_ALIGNMENT.CENTER
for r, row in enumerate(rows):
    for c, val in enumerate(row):
        cell = t.cell(r, c)
        cell.text = val
        if r == 0:
            cell.paragraphs[0].runs[0].bold = True
        if c > 0:
            cell.paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT

# Image
# doc.add_picture("chart.png", width=Cm(15))

# Page break, header/footer
doc.add_page_break()
doc.sections[0].header.paragraphs[0].text = "Company Confidential"
doc.sections[0].footer.paragraphs[0].text = "Quarterly Report"

doc.save("report.docx")
```

Rules of thumb:
- Use real heading styles (`add_heading`) so the navigation pane and table of contents work.
- Use list styles (`List Bullet`, `List Number`), never typed "•" or "1." characters.
- Never fake spacing with empty paragraphs; set `space_before` / `space_after`.
- Keep one font family; vary size and weight for hierarchy.

### Pitfalls that produce broken-looking Word files
| Pitfall | Do this instead |
|---|---|
| Page size: python-docx's default template is US Letter; Indian/European readers expect A4 | `s.page_width, s.page_height = Cm(21), Cm(29.7)` on every section |
| Landscape pages | set `s.orientation = WD_ORIENT.LANDSCAPE` **and** swap `page_width`/`page_height` yourself |
| Tables look different in Google Docs / LibreOffice | set a width on every cell (`cell.width = Cm(4)`) and turn off autofit (`table.autofit = False`); widths must add up to the text width |
| Table header shading comes out black or missing | shade with `w:shd w:val="clear" w:fill="1F2937"` on the cell's `tcPr` — never `val="solid"` |
| Headings separated from their text at a page break | `paragraph_format.keep_with_next = True` on headings (the built-in styles don't always set it) |
| Line breaks inside one paragraph | `run.add_break()`, never `"\n"` in text |
| A horizontal rule | a bottom border on a paragraph (`w:pBdr/w:bottom`), not a one-cell table |
| Right-aligned item on the same line (price lists, contents pages) | a right tab stop with dot leader (`paragraph_format.tab_stops.add_tab_stop(Cm(16), WD_TAB_ALIGNMENT.RIGHT, WD_TAB_LEADER.DOTS)`) — not spaces |
| Text in a contents field doesn't appear | headings must use the built-in "Heading N" styles (custom styles need an outline level) |
| Images without a size | always pass `width=` to `add_picture` so they fit the text width |

## 3. Page numbers and table of contents (fields)

python-docx has no API for fields; insert the XML directly:

```python
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

def add_field(paragraph, instr):          # e.g. "PAGE", 'TOC \\o "1-3" \\h \\z \\u'
    run = paragraph.add_run()
    for kind, text in (("begin", None), (None, instr), ("separate", None), ("end", None)):
        if kind:
            el = OxmlElement("w:fldChar"); el.set(qn("w:fldCharType"), kind)
        else:
            el = OxmlElement("w:instrText"); el.set(qn("xml:space"), "preserve"); el.text = text
        run._r.append(el)

footer_p = doc.sections[0].footer.add_paragraph()      # own line, so it isn't glued to footer text
footer_p.alignment = WD_ALIGN_PARAGRAPH.CENTER
footer_p.add_run("Page ")
add_field(footer_p, "PAGE")
```

A TOC field shows "update field" until opened in Word; running `scripts/to_pdf.sh` through LibreOffice also refreshes it in the PDF.

## 4. Edit an existing document

```python
import shutil
from docx import Document
shutil.copy("original.docx", "edited.docx")
doc = Document("edited.docx")
```

- **Find and replace while keeping formatting:** text is split across runs, so use `scripts/replace_text.py` (merges runs inside each paragraph only when a match spans them, keeping the first run's formatting).
  `python3 scripts/replace_text.py in.docx out.docx "Old Name" "New Name"`
- Iterate **everything**: `doc.paragraphs`, every `table.cell().paragraphs`, and each section's header and footer.
- Insert a paragraph after another: `new = para.insert_paragraph_before("…")` on the *next* paragraph, or copy XML with `deepcopy(para._p)` and `addnext`.
- Reuse the document's own styles (`doc.styles`) instead of inventing new ones.

## 5. Read a document

```bash
pandoc file.docx -t markdown --wrap=none      # best overall
pandoc file.docx -t plain                     # just text
```

With python-docx, walk the body in order (paragraphs and tables interleaved):

```python
from docx.table import Table
from docx.text.paragraph import Paragraph
for block in doc.element.body.iterchildren():
    tag = block.tag.split('}')[1]
    if tag == "p":   print(Paragraph(block, doc).text)
    elif tag == "tbl":
        for row in Table(block, doc).rows: print(" | ".join(c.text for c in row.cells))
```

## 6. Review: comments, tracked changes, verification

`scripts/docx_tools.py` edits the XML directly, so formatting is untouched. Every command takes `--author "Name"`.

```bash
# comments (attached to the exact words; threads and "done" work in Word)
python3 scripts/docx_tools.py comment in.docx a.docx "fee cap" "Is this too low?" --author "Asha Rao"
python3 scripts/docx_tools.py reply   a.docx b.docx 0 "Agreed — raise to ₹8 lakh" --author "Ravi"
python3 scripts/docx_tools.py resolve-comment b.docx c.docx 0

# tracked changes (redlines)
python3 scripts/docx_tools.py track        c.docx d.docx "30 days" "45 days"         # every occurrence
python3 scripts/docx_tools.py track-delete d.docx e.docx "text in the paragraph"     # whole paragraph
python3 scripts/docx_tools.py track-insert e.docx f.docx "anchor text" "New paragraph." [--before]

# check and finish
python3 scripts/docx_tools.py list f.docx                          # every revision and comment thread
python3 scripts/docx_tools.py verify-redline in.docx f.docx        # proves nothing changed without tracking
python3 scripts/docx_tools.py accept f.docx clean.docx             # or reject; paragraph joins follow Word's rules
```

Rules for review work:
- "Suggest edits", "redline", "mark up", "review this contract" → **tracked changes only**; never silently rewrite. Questions and reasoning go in comments.
- **Always run `verify-redline`** against the untouched original before delivering a redline. It rejects every change in a scratch copy and compares with the original; any difference is an untracked edit and it exits 1 naming the paragraph.
- Anchor text must sit inside one formatting run. If an anchor isn't found, run `docx_tools.py merge` first, or pick a shorter distinctive phrase.
- Accepting a deleted paragraph mark joins that paragraph into the next one, as Word does — so a fully deleted paragraph disappears instead of leaving a blank line.

For anything else, edit the XML by hand. Files from other people are untrusted: drop symlinks and never pretty-print the XML (it changes spacing Word cares about).

```bash
mkdir x && cd x && unzip -q ../file.docx && find . -type l -delete
python3 ../scripts/docx_tools.py merge ../file.docx ../file.docx   # optional: rejoin split runs first
# edit word/document.xml (and word/comments.xml for comments)
zip -qr -X ../out.docx '[Content_Types].xml' . ; cd ..     # every part, content-types first
```

Tracked change markup (what the tools write for you):

```xml
<w:ins w:id="101" w:author="Reviewer" w:date="2026-11-05T10:00:00Z"><w:r><w:t>new text</w:t></w:r></w:ins>
<w:del w:id="102" w:author="Reviewer" w:date="2026-11-05T10:00:00Z"><w:r><w:delText>old text</w:delText></w:r></w:del>
```

IDs must be unique across the document. Inside `<w:del>` text lives in `<w:delText>`. A deleted paragraph mark is `<w:pPr><w:rPr><w:del …/></w:rPr></w:pPr>`, placed first inside that `rPr`. Keep `xml:space="preserve"` on any `<w:t>` with leading or trailing spaces. Legacy `.doc` files: convert first with `soffice --headless --convert-to docx file.doc`.

## 7. Verify before delivering

```bash
python3 scripts/docx_tools.py fix out.docx           # always, for files made by python-docx or pandoc
python3 scripts/office_check.py out.docx --render   # structure, links, ids, comment links, opens, renders → must say OK
scripts/to_pdf.sh out.docx                    # makes out.pdf next to it
pdftoppm -png -r 60 out.pdf preview           # look at preview-1.png, preview-2.png …
```

Check: headings and numbering correct, no orphaned blank pages, tables fit the page width, images not overflowing, page numbers present if requested, no leftover placeholder text.
