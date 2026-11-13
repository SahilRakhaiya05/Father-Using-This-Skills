---
name: shareable-docs
description: Use for any document people will keep, share, comment on, print or send — reports, proposals, plans, memos, resumes, cover letters, letters, policies, guides, how-tos, cheat sheets, SOPs. Write it once in clean Markdown, then export a polished web page, Word (.docx) and PDF from the same source.
license: MIT. Complete terms in LICENSE.txt
---

# Shareable Documents

Write the content once, in Markdown, then export to whatever the reader needs. Content and structure first; styling comes from the exporter, so every format looks consistent.

## 1. Start with the skeleton

Before researching or writing body text, put down:
- Title, a one-line subtitle (who it's for / date), and the author.
- Section headings, each with one line on what that section must achieve.

Show the skeleton early when the user is around — changing structure is cheap now and expensive later. Then fill section by section.

## 2. Write for the reader

- **Lead with the point.** First paragraph = the conclusion, decision or ask. Background later.
- Headings that say something ("Costs fall 20% in year two", not "Costs").
- Short paragraphs (2–4 sentences). Lists only for genuinely parallel items or steps.
- Tables for comparisons; numbers with units and dates; sources linked.
- Plain words, active voice, no filler ("It is important to note that…").
- Long docs (> 2 pages): add a 3–5 line summary at the top.

Templates by type:
| Type | Sections |
|---|---|
| Proposal / decision doc | Summary & ask · Problem · Options considered · Recommendation · Costs & risks · Next steps |
| Plan | Goal · Scope (in/out) · Timeline & owners · Risks · How we'll measure success |
| Report | Key findings · Detail per finding · Method & sources · Implications |
| SOP / how-to | Purpose · When to use · Prerequisites · Steps (numbered) · Troubleshooting |
| Resume | Name & contact · Summary (2 lines) · Experience (impact bullets with numbers) · Skills · Education |
| Cover letter / letter | Why you're writing · 2–3 specific points · Clear close and next step |
| Cheat sheet | Grouped tables of commands/terms, one page, no prose |

## 3. Export

```bash
python3 scripts/md_export.py doc.md --html --docx --pdf          # all three, next to doc.md
python3 scripts/md_export.py doc.md --pdf --page a4 --accent "#0f766e"
```

| Output | How | Notes |
|---|---|---|
| `.html` | pandoc → self-contained page with built-in styling, light & dark mode, readable on phones | best for sharing a link or publishing |
| `.docx` | pandoc with a clean reference style | editable in Word / Google Docs; real headings, lists, tables |
| `.pdf` | the HTML printed by headless Chromium | full Unicode (₹, Hindi, emoji), page numbers in the footer, A4 or Letter |

Front matter at the top of the Markdown sets the title block:

```markdown
---
title: Q4 Hiring Plan
subtitle: For the leadership team · November 2026
author: Asha Rao
---
```

## 4. Check before sharing

- Open the PDF pages as images (`pdftoppm -png -r 60 doc.pdf pg`) and look: headings, tables fit, no orphan headings at page bottoms.
- Run the **page-preview** skill on the HTML if it will be shared as a page.
- Re-read the first paragraph: does it alone tell a busy reader what they need?
- Every number has a source or a stated assumption; no `[TODO]` left.

## 5. Editing an existing document

Keep its format: a .docx comes back as .docx (use the **word-docs** skill, with tracked changes if they asked for suggestions), a Google Doc is edited through its connector (**google-files** skill). Only rebuild from Markdown when the user wants a fresh version.
