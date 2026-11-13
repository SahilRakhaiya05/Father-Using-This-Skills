---
name: powerpoint-decks
description: Use when the user asks for a PowerPoint (.pptx) file, or wants to read, edit, restyle, fill a template, or extract content from an existing .pptx/.potx — pitch decks, reviews, training slides, reports as slides, speaker notes.
license: MIT. Complete terms in LICENSE.txt
---

# PowerPoint Decks (.pptx)

Tools in `scripts/`:

| Script | Job |
|---|---|
| `deck.py` | build decks: themed layouts (title, section, bullets, stats, big number, two-column, cards, timeline, table, chart, picture, closing), sections, slide numbers |
| `pptx_tools.py` | duplicate / move / delete slides, replace text, **restyle the whole deck** (`theme`), list sections |
| `deck_qa.py` | automated QA: overflow (real font metrics), off-slide, overlaps, tiny text, contrast, leftovers, title drift |
| `pptx_outline.py` | read any deck: text, tables, chart data, picture alt text, notes, layouts |
| `render.sh` | slides → PNGs + contact sheet for looking |
| `office_check.py` | package structure check |

## 1. Workflow

1. **Storyline first.** One message per slide, written as a headline sentence ("Churn fell 18% after the redesign"), not a label ("Churn"). Main point up front, then the evidence, then what to do next.
2. **Size it to the talk:** ~1.5–2 minutes per slide when presented; a pre-read can carry more words per slide than a live deck.
3. **Pick a palette** (section 2) or use the user's template (section 5).
4. **Build** with `deck.py` (section 3).
5. **QA**: `deck_qa.py` must report 0 errors, then render and look at every slide (section 6).

## 2. Look and feel

Palettes in `deck.PALETTES` (one dominant dark, a light panel tone, one sharp accent, chart accents):
`harbour` navy + coral · `monsoon` forest + mustard · `saffron` umber + orange · `indigo` indigo + amber · `graphite` black + red · `lagoon` deep teal + coral · `plum` aubergine + crimson · `terrace` brown + rose · `glacier` midnight + teal · `ember` ink + pink.
Choose one that suits the subject (finance → graphite/glacier; agriculture → monsoon; consumer brand → saffron/plum). Custom: pass any dict with `dark, text, bg, panel, accent, accent2…accent6, font_head, font_body`.

Everything `deck.py` draws uses **theme colours and theme fonts**, and the theme is written into the file. So:
- `python3 scripts/pptx_tools.py theme deck.pptx out.pptx monsoon --head Cambria` recolours every slide, chart and table in one step;
- in PowerPoint, Design ▸ Variants ▸ Colors/Fonts does the same.

Design rules:
- Dark title, section and closing slides; light content slides.
- Every content slide has one visual anchor: chart, table, big number, stat row, cards, timeline or picture. No more than two bullet slides in a row.
- Title 36 pt+, body 14–24 pt (never below 14 in a deck you create), captions 12 pt. 0.5 in margins; consistent gaps.
- Left-align body text; centre only big numbers and closing lines.
- **Never**: thin accent bars under titles, coloured stripes down a slide or card edge, icons/emoji on every bullet, gradients behind text, cream/beige backgrounds by default, a title ending in a full stop.
- Numbers on a timeline/process mean order; don't number things that aren't a sequence.
- Charts: keep them native (editable), one message per chart, data labels when ≤ 8 points, same label style on every chart.

**Fonts.** Your deck is shown in the viewer's PowerPoint, but checked here with LibreOffice. These render with identical widths in both, so fit checks are exact: **Calibri, Arial, Cambria, Times New Roman, Courier New**. A serif heading (Cambria) with a sans body (Calibri) gives character safely. Fonts like Georgia, Garamond, Trebuchet, Segoe, Aptos, Calibri Light are previewed approximately — `deck_qa.py` notes this; leave ~10% slack in those boxes.

## 3. Build with `deck.py`

```python
import sys; sys.path.insert(0, "scripts")
from deck import Deck, PALETTES

d = Deck(theme={**PALETTES["harbour"], "name": "Phoenix"}, numbers=True)   # 16:9, slide numbers on content slides
d.title_slide("Project Phoenix", "Q4 review · November 2026")
d.stats("The quarter in numbers", [("18%", "drop in monthly churn"), ("₹4.2 cr", "new annual revenue")])
d.section("Results", "What changed and why")             # divider slide + PowerPoint section
d.chart("Monthly active users (k)", ["Jul", "Aug", "Sep", "Oct"], {"2025": [40, 42, 45, 47], "2026": [48, 53, 59, 66]})
d.table("Revenue by region", [["Region", "Q3 (₹ cr)", "Q4 (₹ cr)"], ["North", "1.2", "1.5"], ["South", "0.9", "1.1"]])
d.timeline("Launch plan", [("Beta", "Nov: 200 users"), ("GA", "Jan: all users")])
d.bullets("Three things changed", ["Onboarding shipped", "Churn fell to 5.0%", "Tickets down 22%"], notes="Mention sample size.")
d.two_column("Before vs after", ["7-step signup"], ["3-step signup"], left_title="Before", right_title="After")
d.cards("What's next", [("Pricing", "Test annual plans"), ("Mobile", "Offline mode"), ("Hiring", "Two PMs by Jan")])
d.big_number("18%", "drop in monthly churn since the redesign")
d.image_slide("Our new dashboard", "screenshot.png", caption="October build", alt="Dashboard with usage chart")
d.closing("Thank you", "Questions: asha@example.com")
d.duplicate(5)                                  # deep copy (charts stay independent)
d.save("phoenix.pptx")                          # prints any text that couldn't fit
```

Text is auto-sized with real font measurements down to 14 pt (24 pt for titles); anything that still doesn't fit is reported at save — split the slide or cut words rather than shrinking further. Speaker notes go in `notes=`, never on the slide.

Need a layout that isn't there? Add a method to `deck.py`, keep to its 13.333 × 7.5 in grid, and colour with `set_color(..., "accent")` so restyling keeps working.

## 4. Read or edit an existing deck

```bash
python3 scripts/pptx_outline.py theirs.pptx --layouts      # text, tables, chart data, alt text, notes, layouts
python3 scripts/pptx_tools.py duplicate in.pptx out.pptx 4 --to 9
python3 scripts/pptx_tools.py delete    in.pptx out.pptx 2 7
python3 scripts/pptx_tools.py move      in.pptx out.pptx 8 3
python3 scripts/pptx_tools.py replace   in.pptx out.pptx "FY25" "FY26"
python3 scripts/pptx_tools.py sections  in.pptx
```

- Change text through `run.text`, never `text_frame.text = …` (that wipes formatting into one plain run).
- Do structural work (duplicate, delete, reorder) before editing slide content.
- A duplicated slide gets its own copy of every chart, so editing the copy never changes the original.
- Legacy `.ppt`: `soffice --headless --convert-to pptx file.ppt`. `.potx` templates: copy to a `.pptx` name to work on them, keep `.potx` for the output if a template was asked for.

## 5. Filling the user's template

1. `pptx_outline.py template.pptx --layouts` and `render.sh template.pptx` → see every layout and example slide.
2. Map each section of your content to the template slide that fits it best; vary them.
3. Duplicate those template slides in order, delete the unused originals, then replace text run by run.
4. More slots than content (4 team-member boxes, 3 people)? Delete the whole unused group — picture and text — not just the words.
5. Keep the template's fonts and sizes; don't apply a palette over a brand template unless asked.

## 6. QA — required before delivering

```bash
python3 scripts/deck_qa.py out.pptx        # must say OK (0 errors); fix warnings unless deliberate
python3 scripts/office_check.py out.pptx   # package structure
bash scripts/render.sh out.pptx            # out_slides/slide-NN.png + contact_sheet.png
```

`deck_qa.py` measures every text box with real font metrics and reports, per slide: overflow, shapes off the slide, overlapping text boxes, text partly over a picture/chart, text under 12 pt (error under 10), low contrast against the actual shape or background behind it, leftover "lorem/TODO/XXX/Click to add", empty placeholders, titles that jump position between slides of the same kind, pictures without alt text, runs of text-only slides.

Then look at the contact sheet and each slide image with fresh eyes. Things only a person catches: a number split from its unit across lines, uneven spacing, something that looks off-brand, a chart whose message isn't obvious. Fix, re-run QA, re-render only what changed.
