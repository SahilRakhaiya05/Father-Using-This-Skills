---
name: google-files
description: Use before creating or changing a Google Doc, Sheet or Slides file through a Google Drive/Docs/Sheets/Slides connector or API — writing or formatting text, filling tables or cells, formulas, adding slides, renaming, copying, exporting. Covers connector checks, edit-conflict guards, Docs index maths, A1 ranges, Slides units and verifying the result. Not for read-only questions or for Word/Excel/PowerPoint files.
license: MIT. Complete terms in LICENSE.txt
---

# Google Docs, Sheets and Slides

Google's editing APIs take batches of precise requests ("insert at index 57", "format grid range 0–3"). Almost every failure is a wrong position, a stale read, or the wrong file. `scripts/gws_helpers.py` turns saved API JSON into short summaries and ready-made request batches so none of that maths is done by hand. Run `python3 scripts/gws_helpers.py` for the full command list.

## 0. Before the first edit

1. **Check the tools.** Drive can create, find, rename, copy, export and convert files; editing *inside* a file needs the matching Docs / Sheets / Slides tool. If tools are deferred, search for them first ("google docs update"); list all tools before concluding one is missing.
2. **A change goes into the same file.** "Update", "fix", "add a slide", "change it" all mean: same file, same link. If the editor tool for that app is missing, don't build a substitute file — say which connector to turn on (same file, same link once it's on), offer an alternative as an option, and wait for the user's choice. Creating a brand-new file with Drive alone is fine.
3. **Find the right file.** Use the link given; otherwise search Drive by name and confirm with the user when more than one matches. Page through all results.
4. **Never trash, share or change permissions** unless asked for exactly that.

## 1. The edit loop (all three apps)

```
read  →  helper builds the batch  →  send ONE batch per logical step  →  read again and verify  →  report with link
```

- **Edit-conflict guard.** Docs and Slides batches built from positions or object ids carry `writeControl.requiredRevisionId` from the read they were built on (the helpers add it automatically when the JSON has a `revisionId`). If the file changed since — someone else, or your own previous write — Google rejects the whole batch instead of writing in the wrong place. On rejection: read again, rebuild, resend. Never drop the guard to make it pass. Batches made only of `replaceAllText` need no guard. Sheets writes go without `writeControl`; re-read right before position-dependent writes.
- **Batches are atomic.** If one request is invalid nothing is applied — fix that request and resend the whole batch.
- **Verify** by reading again; a successful call doesn't prove the content is right.
- **Report** with the file's title as a link in the sentence that says what changed ("I added the table to [Hiring plan](link)"); mention the link is unchanged.

## 2. Google Docs

Indexes are **UTF-16 positions** (emoji count 2), starting at 1; every paragraph ends with a newline that counts; pending suggestions count until resolved; documents can have **tabs** (each with its own indexes — pass `tabId`).

```bash
python3 scripts/gws_helpers.py doc-outline doc.json             # revision, tabs, paragraphs, tables (#N), append index
python3 scripts/gws_helpers.py doc-find doc.json "₹48 lakh"     # exact range (+ tab, bold/italic)
python3 scripts/gws_helpers.py doc-replace map.json             # {"{{client}}": "Acme Ltd"} → replaceAllText (safest edit)
python3 scripts/gws_helpers.py doc-insert doc.json --at end --text "Next steps" --style HEADING_2
python3 scripts/gws_helpers.py doc-fill-table doc.json --table 1 --data rows.json --bold-header
```

- Prefer `replaceAllText` for wording changes — no positions involved.
- Several position edits in one batch: work from the **end of the document backwards** so earlier indexes stay valid (the helpers already do this).
- New table: insert it with `insertTable`, **read again**, then `doc-fill-table` (cell positions only exist after the table does).
- Headings with `updateParagraphStyle` → `namedStyleType: HEADING_1…`; lists with `createParagraphBullets`; never type "•".
- Suggestion mode ("suggest edits"): if the tool refuses suggestions, don't silently edit directly — offer to list the proposed changes in chat or to edit directly, and let the user choose.
- Read comments with the read call's comments option; if adding a comment isn't supported, put your notes in the reply instead.

## 3. Google Sheets

```bash
python3 scripts/gws_helpers.py a1 "'P&L 2026'!B4:D10" --meta meta.json     # → GridRange with numeric sheetId
python3 scripts/gws_helpers.py sheet-format spec.json --meta meta.json      # widths, freeze, bold, colours, number formats, borders
python3 scripts/gws_helpers.py sheet-errors grid.json                       # error cells with their formulas
```
(`meta.json` = spreadsheet read with fields `sheets.properties`; `grid.json` = read with grid data for the range.)

- Write values with `USER_ENTERED` so formulas and dates are understood. It also turns text like `1-2` or `00123` into dates/numbers — prefix with `'` to keep text, or use `RAW`.
- GridRanges are **0-based and end-exclusive** and use the numeric `sheetId`, never the tab name — use `a1`.
- Field masks: full paths, comma-separated, no parentheses (`userEnteredFormat.numberFormat,userEnteredFormat.textFormat.bold`). `sheet-format` builds them for you.
- Colours are 0–1 floats, not hex — the helper converts.
- Same modelling rules as **excel-sheets**: formulas not pasted results, inputs in labelled cells, no hard-coded constants inside formulas.
- Verify: read back with formatted values and run `sheet-errors`.

## 4. Google Slides

Positions are **EMU** (914,400 per inch); an element's real size is `size × scale` from its transform; default page is 10 × 5.625 in. **Slides never shrinks text to fit** — overflow stays visible.

```bash
python3 scripts/gws_helpers.py slides-outline deck.json                    # real sizes in inches; flags OFF-PAGE, overlap,
                                                                           # empty placeholders, likely overflow, small text
python3 scripts/gws_helpers.py slides-build spec.json --revision REV       # slides + text boxes + shapes + images from inches
python3 scripts/gws_helpers.py emu 1.5in
```

- Reads of a whole deck are large: ask for only the fields you need, or one page at a time.
- Give your new objects your own ids (5–50 chars) so later requests in the same batch can refer to them; `slides-build` does this.
- Use the deck's own layouts when it has a template, so the branding carries over.
- Slides only pulls images from a public web address. For a local file or a chat upload, suggest building a .pptx instead, or have the user drop the picture in themselves.
- Charts: create them in a Sheet first, then embed the Sheets chart.
- After a write, if the deck still looks the same to the user, have them refresh the browser tab before you try again.
- Same design rules as **powerpoint-decks** (one message per slide, ≥ 14 pt body, no decorative stripes).

## 5. Drive

Create (an empty Google file of the right type, or convert an uploaded HTML, CSV, .docx, .xlsx or .pptx), rename (the link stays the same), copy, move, export. To get the gist of a file, start with Drive's plain-text export, which is cheap; switch to the editor's structured read only when you need exact positions. For a visual check, export a PDF:

```bash
python3 scripts/gws_helpers.py export-images export.json pages/ --pages 1-3    # then look at pages/page-N.jpg
```

## 6. Common failures

| Symptom | Cause → fix |
|---|---|
| "No such tool" | tool is deferred or named differently → search/list tools |
| 400 revision mismatch | file changed since your read → read again, rebuild, resend with the new revision |
| Whole batch failed | one bad request → fix it, resend everything |
| Text landed in the wrong place | stale indexes or a different tab → re-read, use `doc-find`, pass `tabId` |
| Number/date appeared instead of text in Sheets | `USER_ENTERED` parsing → prefix `'` or use `RAW` |
| Formatting call rejected | wrong field mask or sheet name instead of `sheetId` → use `sheet-format` / `a1 --meta` |
| An extra copy of the file appeared | the change was saved as a new file instead of editing the original → say so, and keep both until the user picks one |
| A file you created a moment ago won't open | it was moved to Drive's bin → the user can recover it there; ask them to |
