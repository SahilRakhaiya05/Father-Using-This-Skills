---
name: page-preview
description: Use after building an HTML page, web app, dashboard, slide page or email template — and before handing it over — to see it the way a person will (phone, tablet and desktop widths, light and dark mode), catch layout bugs, console errors, broken images, overflow and unreadable text, and fix them.
license: MIT. Complete terms in LICENSE.txt
---

# Page Preview

You can't judge a page from its source. Render it, look at it, fix what's wrong, render again. Budget: usually one or two fix rounds.

## 1. Run the checker

```bash
python3 scripts/preview_check.py page.html                 # or a URL, or a folder with index.html
python3 scripts/preview_check.py page.html --dark --full   # also dark mode; full-page screenshots
python3 scripts/preview_check.py page.html --click "#start" --wait 800   # interact before capturing
```

It opens the page in headless Chromium at **375 px (phone), 768 px (tablet), 1280 px (desktop)** and writes, per size, a screenshot plus a report (`preview_report.json`) of:

| Check | Why it matters |
|---|---|
| Console errors and uncaught exceptions | blank or half-working page |
| Failed requests (404s, blocked CDNs, fonts) | missing images, fallback fonts, broken scripts |
| Horizontal overflow (page wider than the screen) + the elements causing it | sideways scrolling on phones |
| Broken images (`naturalWidth == 0`) | empty boxes |
| Text smaller than 12 px | unreadable on phones |
| Low-contrast text (WCAG ratio < 4.5 for body text) | unreadable for many people |
| Clipped text (content cut off by `overflow:hidden`) | missing words |
| Overlapping interactive elements | taps hit the wrong button |
| Empty `<title>`, images without `alt` | sharing and accessibility |

## 2. Look at the screenshots yourself

The numbers don't catch everything. Open each screenshot and check:
- Is the most important thing visible without scrolling on a phone?
- Does anything look broken, misaligned, cramped or empty?
- In dark mode, is any text dark-on-dark, or any image with a white box around it?
- Does it look intentional — consistent spacing, one type scale, clear hierarchy?

## 3. Fix and re-check

Common fixes:
| Problem | Fix |
|---|---|
| Overflow on phone | `max-width:100%` on images/media, `min-width:0` on flex/grid children, `overflow-wrap:anywhere` on long words/URLs, wrap wide tables in a scroll container |
| Fonts failing to load | self-host or embed as base64 data URI, or use a system font stack |
| Low contrast | darken text / lighten background; don't put body text on mid-grey |
| Tiny text | body ≥ 16 px on phones; use `rem` |
| Dark mode broken | define colours as CSS variables and override them in `@media (prefers-color-scheme: dark)`; give `body` an explicit background |
| Console error from a CDN script | pin an exact version that exists; check the URL loads |

Re-run the checker after fixing; deliver when the report is clean (or remaining warnings are deliberate) and the screenshots look right.

## 4. Slides, documents and canvases built as HTML

- Fixed-size slides (e.g. 1280×720): run with `--size 1280x720` and `--full`; check each slide fits without scrollbars.
- Print/PDF pages: `--pdf` also saves a PDF via the browser's print engine — check page breaks.
- Interactive apps: use `--click` / `--type` steps to reach the important states, and capture each.

## Rules
- Test the file you will actually deliver, not a draft copy.
- Never call a page done from reading the code alone.
