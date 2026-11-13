#!/usr/bin/env python3
"""Offline helpers for Google Docs / Sheets / Slides API work. They read saved API JSON and print short
summaries or ready-to-send request batches, so position and unit maths never happens by hand.

DOCS (input: documents.get JSON, with or without tabs)
  doc-outline DOC.json                       revision id, tabs, every paragraph/table with [start,end), styles,
                                             pending suggestions as [+ins]/[-del], body end and safe append index
  doc-find    DOC.json "text"                UTF-16 range of every match (per tab), with bold/italic state
  doc-replace MAP.json [--tab ID]            replaceAllText batch from {"{{token}}": "value", ...}
  doc-fill-table DOC.json --data ROWS.json --table N [--tab ID] [--bold-header]
                                             fill empty table N (from doc-outline) with ROWS (list of lists)
  doc-insert  DOC.json --at INDEX|end --text "..." [--style HEADING_2] [--tab ID]
                                             insert a paragraph and style it, guarded by the revision id
SHEETS
  a1          "Sheet!B2:D10" [--meta META.json]   A1 -> GridRange (0-based, end-exclusive; sheetId resolved)
  col         28 | AB                              column number <-> letters
  sheet-format SPEC.json --meta META.json          formatting batch from a short spec (see FORMAT SPEC)
  sheet-errors GRID.json                           error cells (#REF!, #DIV/0! ...) with their formulas
SLIDES (input: presentations.get JSON)
  slides-outline DECK.json                   per slide: elements with real size (size x scale) in inches, text,
                                             font size; flags off-page, overlaps, empty placeholders, likely overflow
  slides-build SPEC.json [--revision ID] [--page WxH, default 10x5.625]
                                             createSlide/createShape/insertText/style batch from an inch-based spec
DRIVE
  export-images EXPORT OUTDIR [--dpi 100] [--pages 1-3]
                                             decode a PDF export (JSON with base64 "content", raw base64, or .pdf)
                                             into page images to look at
UNITS
  utf16 "text" | emu 1.5in|18pt|2cm | selftest

Every batch that addresses positions or object ids is printed with writeControl.requiredRevisionId when the
input JSON carries a revisionId: if anyone (including you) changed the file since that read, Google rejects
the whole batch instead of writing into the wrong place. Re-read, rebuild, resend.

FORMAT SPEC (sheet-format):
  {"sheet": "Budget", "freeze_rows": 1, "freeze_cols": 0,
   "widths": {"A": 160, "B:D": 110},
   "ranges": [{"range": "A1:D1", "bold": true, "bg": "#1F2937", "fg": "#FFFFFF", "align": "CENTER"},
              {"range": "B2:D20", "number": "#,##,##0", "align": "RIGHT"},
              {"range": "E2:E20", "number": "0.0%"}],
   "borders": [{"range": "A1:D20", "style": "SOLID", "color": "#D1D5DB"}]}
SLIDES SPEC (slides-build):
  {"slides": [{"id": "s_intro", "layout": "BLANK", "background": "#0B2545",
     "elements": [{"type": "text", "x": 0.6, "y": 2.0, "w": 8.8, "h": 1.2, "text": "Q4 review",
                   "size": 40, "bold": true, "color": "#FFFFFF", "font": "Calibri", "align": "START"},
                  {"type": "rect", "x": 0.6, "y": 3.4, "w": 2, "h": 0.1, "fill": "#D1495B"},
                  {"type": "image", "url": "https://...", "x": 5, "y": 1, "w": 4, "h": 3}]}]}
"""
import base64
import json
import os
import re
import string
import subprocess
import sys

EMU_PER = {"in": 914400, "pt": 12700, "cm": 360000, "mm": 36000, "px": 9525}
EMU_IN = 914400
ALPHABET = string.ascii_uppercase
OID_CHARS = set(string.ascii_letters + string.digits + "_-:")


# ============================================================================ common
def load(path):
    with open(path, encoding="utf-8") as f:
        txt = f.read()
    data = json.loads(txt)
    # results saved by some apps wrap the API payload; unwrap common shapes
    for key in ("result", "data", "response", "content"):
        if isinstance(data, dict) and key in data and isinstance(data[key], (dict, str)) and len(data) <= 3:
            inner = data[key]
            if isinstance(inner, str):
                try:
                    inner = json.loads(inner)
                except Exception:
                    continue
            if isinstance(inner, dict):
                data = inner
    return data


def emit(requests, revision=None, extra=None):
    out = {"requests": requests}
    if revision:
        out["writeControl"] = {"requiredRevisionId": revision}
    if extra:
        out.update(extra)
    print(json.dumps(out, indent=1, ensure_ascii=False))


def utf16_len(s):
    """Length in UTF-16 code units, the unit Google Docs counts positions in."""
    return sum(2 if ord(ch) > 0xFFFF else 1 for ch in s)


def hex_rgb(code):
    """'#1F2937' -> Google's colour object, each channel between 0 and 1."""
    digits = code.strip().lstrip("#")
    if len(digits) != 6:
        raise ValueError(f"colour {code!r} must look like #RRGGBB")
    return dict(zip(("red", "green", "blue"), (int(digits[i:i + 2], 16) / 255 for i in (0, 2, 4))))


def to_emu(value):
    text = str(value).strip().lower()
    for unit, per_unit in EMU_PER.items():
        number = text[: -len(unit)].strip()
        if text.endswith(unit) and re.fullmatch(r"\d+(\.\d*)?|\.\d+", number):
            return round(float(number) * per_unit)
    raise ValueError("use e.g. 1.5in, 18pt, 2cm, 10mm, 96px")


# ============================================================================ docs
def doc_tabs(doc):
    """Yield (tab_id, title, body) for every tab (and child tab); a doc without tabs yields one (None, None, body)."""
    if doc.get("tabs"):
        def walk(tabs):
            for t in tabs:
                props = t.get("tabProperties", {})
                yield props.get("tabId"), props.get("title"), t.get("documentTab", {}).get("body", {})
                yield from walk(t.get("childTabs", []))
        yield from walk(doc["tabs"])
    else:
        yield None, None, doc.get("body", {})


def _elements(content, tables, depth=0):
    for se in content:
        if "paragraph" in se:
            yield ("p", se, depth)
        elif "table" in se:
            tables.append(se)
            yield ("t", se, depth)
            for r in se["table"].get("tableRows", []):
                for c in r.get("tableCells", []):
                    yield from _elements(c.get("content", []), tables, depth + 1)
        elif "tableOfContents" in se:
            yield ("toc", se, depth)
        elif "sectionBreak" in se:
            yield ("br", se, depth)


PLACEHOLDERS = (("inlineObjectElement", "[image]"), ("richLink", "[chip]"), ("person", "[chip]"))
SUGGESTION_MARKS = (("suggestedInsertionIds", "[+{}]"), ("suggestedDeletionIds", "[-{}]"))


def run_text(el, marks=True):
    """Text of one paragraph element; non-text elements become a short label."""
    run = el.get("textRun")
    if not run:
        return next((label for key, label in PLACEHOLDERS if key in el), "")
    content = run.get("content", "")
    if marks:
        for key, pattern in SUGGESTION_MARKS:
            if run.get(key):
                return pattern.format(content)
    return content


def para_text(se, marks=False):
    """Plain text of one paragraph structural element."""
    return "".join(run_text(part, marks) for part in se["paragraph"].get("elements", []))


def doc_paragraphs(doc):
    out = []
    for tab_id, _, body in doc_tabs(doc):
        tables = []
        for kind, se, depth in _elements(body.get("content", []), tables):
            if kind == "p":
                out.append({"tab": tab_id, "start": se.get("startIndex", 1), "end": se.get("endIndex"),
                            "style": se["paragraph"].get("paragraphStyle", {}).get("namedStyleType", ""),
                            "bullet": "bullet" in se["paragraph"], "text": para_text(se), "depth": depth,
                            "elements": se["paragraph"].get("elements", [])})
    return out


def cmd_doc_outline(path):
    doc = load(path)
    print(f"revisionId: {doc.get('revisionId')}")
    tables = []
    for tab_id, title, body in doc_tabs(doc):
        if tab_id is not None:
            print(f"\n=== tab {title!r} (tabId {tab_id}) ===")
        last_end = 1
        for kind, se, depth in _elements(body.get("content", []), tables):
            ind = "    " * depth
            if kind == "p":
                st = se["paragraph"].get("paragraphStyle", {}).get("namedStyleType", "")
                b = "• " if "bullet" in se["paragraph"] else ""
                txt = para_text(se, marks=True).rstrip("\n")
                print(f"{ind}[{se.get('startIndex', 1):>6},{se.get('endIndex'):>6}) {st:<12} {b}{txt[:100]!r}")
            elif kind == "t":
                t = se["table"]
                print(f"{ind}[{se.get('startIndex'):>6},{se.get('endIndex'):>6}) TABLE #{len(tables)} "
                      f"{t.get('rows')}x{t.get('columns')}")
            elif kind == "toc":
                print(f"{ind}[{se.get('startIndex'):>6},{se.get('endIndex'):>6}) TABLE OF CONTENTS")
            if depth == 0:
                last_end = max(last_end, se.get("endIndex") or 0)
        print(f"body end {last_end}: append by inserting at {last_end - 1} (the final newline must stay)")
    if any(e.get("textRun", {}).get("suggestedInsertionIds") or e.get("textRun", {}).get("suggestedDeletionIds")
           for p in doc_paragraphs(doc) for e in p["elements"]):
        print("note: pending suggestions present ([+..]/[-..]); their text counts in indexes until accepted/rejected")


def doc_find(doc, needle):
    hits = []
    for para in doc_paragraphs(doc):
        # build the paragraph's text from runs to keep exact indexes and per-run styles
        pos = para["start"]
        flat, styles = "", []
        for e in para["elements"]:
            t = run_text(e, marks=False)
            if "textRun" not in e:
                flat += "￼"
                styles.append((pos, pos + 1, {}))
                pos += 1
                continue
            flat += t
            styles.append((pos, pos + utf16_len(t), e["textRun"].get("textStyle", {})))
            pos += utf16_len(t)
        start = 0
        while True:
            i = flat.find(needle, start)
            if i < 0:
                break
            s = para["start"] + utf16_len(flat[:i])
            e_ = s + utf16_len(needle)
            st = [x[2] for x in styles if x[0] < e_ and x[1] > s]
            hits.append({"tab": para["tab"], "startIndex": s, "endIndex": e_,
                         "bold": all(x.get("bold") for x in st) if st else False,
                         "italic": all(x.get("italic") for x in st) if st else False})
            start = i + max(len(needle), 1)
    return hits


def cmd_doc_find(path, needle):
    doc = load(path)
    hits = doc_find(doc, needle)
    print(f"revisionId: {doc.get('revisionId')}")
    for h in hits:
        tab = f"tab {h['tab']}: " if h["tab"] else ""
        print(f"{tab}{h['startIndex']}-{h['endIndex']}  bold={h['bold']} italic={h['italic']}")
    if not hits:
        print("no match (a match must sit inside one paragraph and not span an image or chip)")


def cmd_doc_replace(map_path, tab=None):
    m = json.load(open(map_path))
    reqs = []
    for k, v in m.items():
        r = {"replaceAllText": {"containsText": {"text": k, "matchCase": True}, "replaceText": str(v)}}
        if tab:
            r["replaceAllText"]["tabsCriteria"] = {"tabIds": [tab]}
        reqs.append(r)
    emit(reqs)            # replaceAllText needs no index maths and no revision guard


def cmd_doc_fill_table(path, n, data_path, bold_header=False, tab=None):
    doc = load(path)
    rows = json.load(open(data_path))
    tables = []
    for tab_id, _, body in doc_tabs(doc):
        found = []
        for _ in _elements(body.get("content", []), found):
            pass
        tables += [(tab_id, tb) for tb in found]          # numbered across the whole document, like doc-outline
    if n < 1 or n > len(tables):
        sys.exit(f"table #{n} not found ({len(tables)} table(s)); see doc-outline")
    tab_id, t = tables[n - 1]
    trows = t["table"]["tableRows"]
    width = len(trows[0]["tableCells"])
    if len(rows) > len(trows) or any(len(r) > width for r in rows):
        widest = max(len(r) for r in rows)
        sys.exit(f"ROWS needs {len(rows)} row(s) by {widest} column(s); table #{n} has {len(trows)} by {width}")
    cells = []
    for ri, r in enumerate(rows):
        for ci, val in enumerate(r):
            cell = trows[ri]["tableCells"][ci]
            para = cell["content"][0]
            existing = para_text(para).strip()
            if existing:
                sys.exit(f"cell ({ri + 1},{ci + 1}) is not empty ({existing!r}); this fills empty tables only")
            cells.append((para["startIndex"], ri, str(val)))
    reqs = []
    loc = lambda i: {"index": i, **({"tabId": tab_id} if tab_id else {})}
    for idx, ri, val in sorted(cells, key=lambda x: -x[0]):      # last cell first: earlier indexes stay valid
        if val:
            reqs.append({"insertText": {"location": loc(idx), "text": val}})
    if bold_header:
        header = [(idx, val) for idx, ri, val in cells if ri == 0 and val]
        for idx, val in header:
            # after the inserts, this cell starts later by the length of every value inserted before it
            start = idx + sum(utf16_len(v) for other, _, v in cells if other < idx)
            span = dict(startIndex=start, endIndex=start + utf16_len(val))
            if tab_id:
                span["tabId"] = tab_id
            reqs.append({"updateTextStyle": dict(range=span, textStyle=dict(bold=True), fields="bold")})
    emit(reqs, doc.get("revisionId"))


def cmd_doc_insert(path, at, text, style=None, tab=None):
    doc = load(path)
    allp = doc_paragraphs(doc)
    if tab is None and allp and allp[0]["tab"] is not None:
        tab = allp[0]["tab"]                     # document has tabs: default to the first one
    paras = [p for p in allp if p["tab"] == tab]
    if at == "end":
        idx = max(p["end"] for p in paras if p["depth"] == 0) - 1
    else:
        idx = int(at)
    body = text if text.endswith("\n") else text + "\n"
    tabkw = {"tabId": tab} if tab else {}
    reqs = [{"insertText": {"location": {"index": idx, **tabkw}, "text": body}}]
    if style:
        reqs.append({"updateParagraphStyle": {"range": {"startIndex": idx, "endIndex": idx + utf16_len(body), **tabkw},
                                              "paragraphStyle": {"namedStyleType": style}, "fields": "namedStyleType"}})
    emit(reqs, doc.get("revisionId"))


# ============================================================================ sheets
def col_to_letters(n):
    """1 -> A, 26 -> Z, 27 -> AA (bijective base 26: there is no zero digit)."""
    n = int(n)
    if n < 1:
        raise ValueError("columns start at 1")
    letters = []
    while n > 0:
        n -= 1
        letters.append(ALPHABET[n % 26])
        n //= 26
    return "".join(reversed(letters))


def letters_to_col(s):
    """A -> 1, Z -> 26, AA -> 27."""
    if not s or any(ch not in ALPHABET for ch in s.upper()):
        raise ValueError(f"bad column {s!r}")
    total = 0
    for ch in s.upper():
        total = total * 26 + ALPHABET.index(ch) + 1
    return total


def a1_to_grid(a1, sheet_ids=None):
    sheet = None
    rng = a1
    if "!" in a1:
        sheet, rng = a1.rsplit("!", 1)
        sheet = sheet.strip("'").replace("''", "'")
    parts = rng.split(":")
    if len(parts) == 1:
        parts = parts * 2
    out = {"sheet": sheet}
    for k, p in enumerate(parts):
        m = re.fullmatch(r"\$?([A-Za-z]*)\$?(\d*)", p.strip())
        if not m or (not m.group(1) and not m.group(2)):
            raise ValueError(f"bad A1 range {a1!r}")
        col, row = m.group(1), m.group(2)
        if col:
            c = letters_to_col(col)
            out["startColumnIndex" if k == 0 else "endColumnIndex"] = c - 1 if k == 0 else c
        if row:
            r = int(row)
            out["startRowIndex" if k == 0 else "endRowIndex"] = r - 1 if k == 0 else r
    if sheet_ids is not None:
        name = out.pop("sheet")
        if name is None:
            if len(sheet_ids) != 1:
                raise ValueError("range has no sheet name and the spreadsheet has several sheets")
            name = next(iter(sheet_ids))
        if name not in sheet_ids:
            raise ValueError(f"no sheet named {name!r}; sheets: {list(sheet_ids)}")
        out = {"sheetId": sheet_ids[name], **out}
    return out


def sheet_ids_from_meta(meta_path):
    """Sheet title -> numeric sheetId, from a spreadsheets.get response."""
    ids = {}
    for sheet in load(meta_path).get("sheets", []):
        props = sheet["properties"]
        ids[props["title"]] = props["sheetId"]
    return ids


def cmd_sheet_format(spec_path, meta_path):
    spec = json.load(open(spec_path))
    ids = sheet_ids_from_meta(meta_path)
    sheet = spec.get("sheet") or next(iter(ids))
    sid = ids[sheet] if sheet in ids else int(sheet)
    reqs = []
    freeze_keys = (("freeze_rows", "frozenRowCount"), ("freeze_cols", "frozenColumnCount"))
    frozen = {api: spec[mine] for mine, api in freeze_keys if mine in spec}
    if frozen:
        mask = ",".join("gridProperties." + api for api in frozen)
        reqs.append({"updateSheetProperties": {"fields": mask,
                                               "properties": {"sheetId": sid, "gridProperties": frozen}}})
    for cols, px in (spec.get("widths") or {}).items():
        a, _, b = cols.partition(":")
        reqs.append({"updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": letters_to_col(a) - 1,
                      "endIndex": letters_to_col(b or a)}, "properties": {"pixelSize": px}, "fields": "pixelSize"}})
    for r in spec.get("ranges", []):
        grid = a1_to_grid(f"'{sheet}'!{r['range']}" if "!" not in r["range"] else r["range"], ids)
        fmt, fields = {}, []
        tf = {}
        if "bold" in r:
            tf["bold"] = r["bold"]
            fields.append("userEnteredFormat.textFormat.bold")
        if "italic" in r:
            tf["italic"] = r["italic"]
            fields.append("userEnteredFormat.textFormat.italic")
        if "fg" in r:
            tf["foregroundColor"] = hex_rgb(r["fg"])
            fields.append("userEnteredFormat.textFormat.foregroundColor")
        if "size" in r:
            tf["fontSize"] = r["size"]
            fields.append("userEnteredFormat.textFormat.fontSize")
        if tf:
            fmt["textFormat"] = tf
        if "bg" in r:
            fmt["backgroundColor"] = hex_rgb(r["bg"])
            fields.append("userEnteredFormat.backgroundColor")
        if "number" in r:
            kind = "PERCENT" if "%" in r["number"] else ("DATE" if re.search(r"[dmy]{2}", r["number"]) else "NUMBER")
            fmt["numberFormat"] = {"type": kind, "pattern": r["number"]}
            fields.append("userEnteredFormat.numberFormat")
        if "align" in r:
            fmt["horizontalAlignment"] = r["align"].upper()
            fields.append("userEnteredFormat.horizontalAlignment")
        if r.get("wrap"):
            fmt["wrapStrategy"] = "WRAP"
            fields.append("userEnteredFormat.wrapStrategy")
        reqs.append({"repeatCell": {"range": grid, "cell": {"userEnteredFormat": fmt}, "fields": ",".join(fields)}})
    for b in spec.get("borders", []):
        grid = a1_to_grid(f"'{sheet}'!{b['range']}", ids)
        side = {"style": b.get("style", "SOLID"), "color": hex_rgb(b.get("color", "#D1D5DB"))}
        reqs.append({"updateBorders": {"range": grid, **{k: side for k in ("top", "bottom", "left", "right",
                                                                             "innerHorizontal", "innerVertical")}}})
    emit(reqs)   # Sheets: send without writeControl; re-read before position-dependent writes


def cmd_sheet_errors(path):
    data = load(path)
    found = 0
    for s in data.get("sheets", []):
        title = s.get("properties", {}).get("title")
        for block in s.get("data", []):
            top, left = block.get("startRow", 0), block.get("startColumn", 0)
            for rnum, row in enumerate(block.get("rowData", []), start=top + 1):
                for cnum, cell in enumerate(row.get("values", []), start=left + 1):
                    ev = cell.get("effectiveValue", {})
                    fv = str(cell.get("formattedValue", ""))
                    if "errorValue" in ev or fv.startswith(("#REF!", "#DIV/0!", "#VALUE!", "#NAME?", "#N/A",
                                                             "#NUM!", "#ERROR!", "#NULL!")):
                        found += 1
                        formula = cell.get("userEnteredValue", {}).get("formulaValue", "")
                        msg = ev.get("errorValue", {}).get("message", "")
                        print(f"{title}!{col_to_letters(cnum)}{rnum}: {fv or ev.get('errorValue', {}).get('type')}"
                              f"  {formula}  {msg}")
    for vr in data.get("valueRanges", []) + ([data] if "values" in data else []):
        for ri, row in enumerate(vr.get("values", [])):
            for ci, v in enumerate(row):
                if str(v).startswith(("#REF!", "#DIV/0!", "#VALUE!", "#NAME?", "#N/A", "#NUM!", "#ERROR!")):
                    found += 1
                    print(f"{vr.get('range', '')} row {ri + 1} col {ci + 1}: {v}")
    print(f"{found} error cell(s)")
    sys.exit(1 if found else 0)


# ============================================================================ slides
def _el_box(el):
    size = el.get("size", {})
    tr = el.get("transform", {})
    sx, sy = tr.get("scaleX", 1), tr.get("scaleY", 1)
    w = size.get("width", {}).get("magnitude", 0) * sx
    h = size.get("height", {}).get("magnitude", 0) * sy
    unit = size.get("width", {}).get("unit", "EMU")
    k = 12700 if unit == "PT" else 1
    x, y = tr.get("translateX", 0), tr.get("translateY", 0)
    if tr.get("unit") == "PT":
        x, y = x * 12700, y * 12700
    return x / EMU_IN, y / EMU_IN, w * k / EMU_IN, h * k / EMU_IN


def _el_text(el):
    """(all text in a shape, list of font sizes used)."""
    elements = el.get("shape", {}).get("text", {}).get("textElements", [])
    runs = [part["textRun"] for part in elements if part.get("textRun")]
    sizes = [r.get("style", {}).get("fontSize", {}).get("magnitude") for r in runs]
    return "".join(r.get("content", "") for r in runs), [size for size in sizes if size]


def _outside(x, y, w, h, pw, ph, slack):
    """True when a box (inches) reaches past the page edges by more than `slack`."""
    return min(x, y) < -slack or x + w > pw + slack or y + h > ph + slack


def cmd_slides_outline(path):
    deck = load(path)
    pw = deck.get("pageSize", {}).get("width", {}).get("magnitude", 9144000) / EMU_IN
    ph = deck.get("pageSize", {}).get("height", {}).get("magnitude", 5143500) / EMU_IN
    slides = deck.get("slides", [])
    print(f"{len(slides)} slide(s), page {pw:.3f} by {ph:.3f} in, revisionId {deck.get('revisionId')}")
    for si, s in enumerate(deck.get("slides", []), 1):
        layout = s.get("slideProperties", {}).get("layoutObjectId", "")
        print(f"\n--- slide {si} id={s['objectId']} layout={layout}")
        boxes = []
        for el in s.get("pageElements", []):
            x, y, w, h = _el_box(el)
            kind = next((k for k in ("shape", "image", "table", "sheetsChart", "video", "line", "elementGroup") if k in el), "?")
            ph_ = el.get("shape", {}).get("placeholder", {}).get("type")
            txt, sizes = _el_text(el)
            fs = max(sizes) if sizes else None
            flags = []
            if _outside(x, y, w, h, pw, ph, 0.01):
                flags.append("OFF-PAGE")
            if ph_ and not txt.strip():
                flags.append("EMPTY PLACEHOLDER")
            if txt.strip() and fs and w > 0:
                cpl = max(1, int(w * 72 / (fs * 0.5)))
                lines = sum(max(1, -(-len(l) // cpl)) for l in txt.rstrip("\n").split("\n"))
                if lines * fs * 1.2 / 72 > h * 1.05:
                    flags.append(f"LIKELY OVERFLOW ({lines} lines at {fs:g}pt)")   # Slides never shrinks text
            if fs and fs < 12:
                flags.append(f"SMALL TEXT {fs:g}pt")
            boxes.append((el["objectId"], (x, y, x + w, y + h), bool(txt.strip())))
            label = f"{kind}{'/' + ph_ if ph_ else ''}"
            where = f"at ({x:.2f}, {y:.2f}) size {w:.2f}x{h:.2f} in"
            print(f"  {el['objectId']:<18} {label:<22} {where}"
                  f"{f' {fs:g}pt' if fs else ''} {txt.strip()[:60]!r} {' '.join(flags)}")
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                a, b = boxes[i][1], boxes[j][1]
                ov = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(0, min(a[3], b[3]) - max(a[1], b[1]))
                inside = (a[0] <= b[0] and a[1] <= b[1] and a[2] >= b[2] and a[3] >= b[3]) or \
                         (b[0] <= a[0] and b[1] <= a[1] and b[2] >= a[2] and b[3] >= a[3])
                if ov > 0.02 and boxes[i][2] and boxes[j][2] and not inside:
                    print(f"  OVERLAP: {boxes[i][0]} and {boxes[j][0]}")


def _oid(s):
    """Google object ids: 5-50 characters from letters, digits, _ - :, not starting with - or :."""
    if not 5 <= len(s) <= 50 or s[0] in "-:" or not set(s) <= OID_CHARS:
        raise ValueError(f"objectId {s!r} must be 5-50 chars of letters, digits, _ - :")
    return s


TEXT_STYLE_KEYS = (  # spec key, API field, value builder
    ("font", "fontFamily", lambda v: v),
    ("color", "foregroundColor", lambda v: {"opaqueColor": {"rgbColor": hex_rgb(v)}}),
    ("bold", "bold", bool),
    ("size", "fontSize", lambda v: {"magnitude": v, "unit": "PT"}),
)


def _placement(page_id, x, y, w, h):
    """elementProperties for a box given in inches."""
    def emu(inches):
        return int(round(inches * EMU_IN))
    dims = {name: {"magnitude": emu(v), "unit": "EMU"} for name, v in (("width", w), ("height", h))}
    move = {"translateX": emu(x), "translateY": emu(y), "scaleX": 1, "scaleY": 1, "unit": "EMU"}
    return {"pageObjectId": page_id, "size": dims, "transform": move}


def cmd_slides_build(spec_path, page="10x5.625", revision=None):
    spec = json.load(open(spec_path))
    pw, ph = (float(v) for v in page.lower().split("x"))
    reqs, seen, warns = [], set(), []
    for si, s in enumerate(spec["slides"], 1):
        sid = _oid(s.get("id") or f"slide_{si:03d}")
        if sid in seen:
            raise ValueError(f"duplicate objectId {sid}")
        seen.add(sid)
        layout = s.get("layout", "BLANK")
        new_slide = dict(objectId=sid, slideLayoutReference=dict(predefinedLayout=layout))
        position = s.get("index")
        if position is not None:
            new_slide["insertionIndex"] = position
        reqs.append(dict(createSlide=new_slide))
        if s.get("background"):
            reqs.append({"updatePageProperties": {"objectId": sid, "pageProperties": {"pageBackgroundFill": {
                "solidFill": {"color": {"rgbColor": hex_rgb(s["background"])}}}}, "fields": "pageBackgroundFill.solidFill.color"}})
        for ei, el in enumerate(s.get("elements", []), 1):
            eid = _oid(el.get("id") or f"{sid}_e{ei:02d}")
            if eid in seen:
                raise ValueError(f"duplicate objectId {eid}")
            seen.add(eid)
            x, y, w, h = el["x"], el["y"], el["w"], el["h"]
            if _outside(x, y, w, h, pw, ph, 1e-6):
                warns.append(f"{eid} goes outside the {pw}x{ph} in page")
            props = _placement(sid, x, y, w, h)
            t = el["type"]
            if t == "image":
                reqs.append({"createImage": {"objectId": eid, "url": el["url"], "elementProperties": props}})
                continue
            shape = {"text": "TEXT_BOX", "rect": "RECTANGLE", "round": "ROUND_RECTANGLE", "oval": "ELLIPSE"}[t]
            reqs.append({"createShape": {"objectId": eid, "shapeType": shape, "elementProperties": props}})
            if el.get("fill"):
                solid = {"solidFill": {"color": {"rgbColor": hex_rgb(el["fill"])}}}
                reqs.append({"updateShapeProperties": {
                    "objectId": eid,
                    "fields": "outline.propertyState,shapeBackgroundFill.solidFill.color",
                    "shapeProperties": {"outline": {"propertyState": "NOT_RENDERED"}, "shapeBackgroundFill": solid}}})
            if el.get("text"):
                reqs.append({"insertText": {"objectId": eid, "text": el["text"], "insertionIndex": 0}})
                style = {api: build(el[key]) for key, api, build in TEXT_STYLE_KEYS if key in el}
                if style:
                    reqs.append({"updateTextStyle": {"objectId": eid, "style": style, "textRange": {"type": "ALL"},
                                                     "fields": ",".join(style)}})
                if "align" in el:
                    reqs.append({"updateParagraphStyle": {"objectId": eid, "textRange": {"type": "ALL"},
                                                          "style": {"alignment": el["align"].upper()}, "fields": "alignment"}})
                size = el.get("size", 18)
                cpl = max(1, int(w * 72 / (size * 0.5)))
                lines = sum(max(1, -(-len(l) // cpl)) for l in el["text"].split("\n"))
                if lines * size * 1.2 / 72 > h:
                    warns.append(f"{eid}: text likely overflows ({lines} lines at {size}pt in {h} in) — Slides never shrinks text")
    for wmsg in warns:
        print("WARN:", wmsg, file=sys.stderr)
    emit(reqs, revision)


# ============================================================================ drive
def cmd_export_images(src, outdir, dpi="100", pages=None):
    os.makedirs(outdir, exist_ok=True)
    raw = open(src, "rb").read()
    pdf = None
    if raw[:5] == b"%PDF-":
        pdf = raw
    else:
        txt = raw.decode("utf-8", "ignore").strip()
        try:
            obj = json.loads(txt)

            def find_b64(o):
                if isinstance(o, dict):
                    for k in ("content", "data", "base64", "blob"):
                        if isinstance(o.get(k), str) and len(o[k]) > 100:
                            return o[k]
                    for v in o.values():
                        r = find_b64(v)
                        if r:
                            return r
                if isinstance(o, list):
                    for v in o:
                        r = find_b64(v)
                        if r:
                            return r
                return None
            txt = find_b64(obj) or ""
        except Exception:
            pass
        txt = re.sub(r"^data:[^,]+,", "", txt)
        pdf = base64.b64decode(txt + "=" * (-len(txt) % 4))
    if pdf[:5] != b"%PDF-":
        sys.exit("could not find a PDF in that export")
    out_pdf = os.path.join(outdir, "export.pdf")
    open(out_pdf, "wb").write(pdf)
    cmd = ["pdftoppm", "-jpeg", "-r", str(dpi)]
    if pages:
        a, _, b = pages.partition("-")
        cmd += ["-f", a, "-l", b or a]
    subprocess.run(cmd + [out_pdf, os.path.join(outdir, "page")], check=True)
    for f in sorted(os.listdir(outdir)):
        if f.startswith("page"):
            print(os.path.join(outdir, f))


# ============================================================================ tests + cli
def selftest():
    assert utf16_len("a😀b") == 4
    doc = {"revisionId": "r1", "body": {"content": [
        {"startIndex": 0, "endIndex": 1, "sectionBreak": {}},
        {"startIndex": 1, "endIndex": 14, "paragraph": {"paragraphStyle": {"namedStyleType": "HEADING_1"},
         "elements": [{"startIndex": 1, "endIndex": 14, "textRun": {"content": "Plan 😀 2026\n"}}]}},
        {"startIndex": 14, "endIndex": 28, "paragraph": {"paragraphStyle": {"namedStyleType": "NORMAL_TEXT"},
         "elements": [{"startIndex": 14, "endIndex": 28, "textRun": {"content": "Budget is 10\n", "textStyle": {"bold": True}}}]}},
    ]}}
    assert doc_find(doc, "2026")[0]["startIndex"] == 9
    h = doc_find(doc, "Budget")[0]
    assert h["startIndex"] == 14 and h["bold"] is True
    tabbed = {"revisionId": "r2", "tabs": [{"tabProperties": {"tabId": "t.0", "title": "Main"},
              "documentTab": {"body": doc["body"]}}]}
    assert doc_find(tabbed, "Budget")[0]["tab"] == "t.0"
    assert col_to_letters(703) == "AAA" and letters_to_col("AB") == 28
    assert a1_to_grid("'Q4 Budget'!B2:D10", {"Q4 Budget": 7}) == {"sheetId": 7, "startColumnIndex": 1, "startRowIndex": 1,
                                                                  "endColumnIndex": 4, "endRowIndex": 10}
    assert a1_to_grid("A:A") == {"sheet": None, "startColumnIndex": 0, "endColumnIndex": 1}
    assert to_emu("1in") == 914400 and to_emu("18pt") == 228600
    assert abs(_el_box({"size": {"width": {"magnitude": 3000000, "unit": "EMU"}, "height": {"magnitude": 1000000, "unit": "EMU"}},
                        "transform": {"scaleX": 2, "scaleY": 1, "translateX": 914400, "translateY": 0, "unit": "EMU"}})[2]
               - 6000000 / EMU_IN) < 1e-6
    print("selftest OK")


def main():
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    flags = {"--bold-header"}
    pos = [x for i, x in enumerate(a) if not x.startswith("--") and (i == 0 or not a[i - 1].startswith("--")
                                                                    or a[i - 1] in flags)]
    cmd = pos[0]
    try:
        if cmd == "selftest":
            selftest()
        elif cmd == "doc-outline":
            cmd_doc_outline(pos[1])
        elif cmd == "doc-find":
            cmd_doc_find(pos[1], pos[2])
        elif cmd == "doc-map":
            cmd_doc_outline(pos[1])
        elif cmd == "doc-replace":
            cmd_doc_replace(pos[1], opt("--tab"))
        elif cmd == "doc-fill-table":
            cmd_doc_fill_table(pos[1], int(opt("--table")), opt("--data"), "--bold-header" in a, opt("--tab"))
        elif cmd == "doc-insert":
            cmd_doc_insert(pos[1], opt("--at", "end"), opt("--text"), opt("--style"), opt("--tab"))
        elif cmd == "utf16":
            print(utf16_len(pos[1]))
        elif cmd == "a1":
            ids = sheet_ids_from_meta(opt("--meta")) if opt("--meta") else None
            print(json.dumps(a1_to_grid(pos[1], ids)))
        elif cmd == "col":
            print(col_to_letters(pos[1]) if pos[1].isdigit() else letters_to_col(pos[1]))
        elif cmd == "sheet-format":
            cmd_sheet_format(pos[1], opt("--meta"))
        elif cmd == "sheet-errors":
            cmd_sheet_errors(pos[1])
        elif cmd == "slides-outline":
            cmd_slides_outline(pos[1])
        elif cmd == "slides-build":
            cmd_slides_build(pos[1], opt("--page", "10x5.625"), opt("--revision"))
        elif cmd == "export-images":
            cmd_export_images(pos[1], pos[2], opt("--dpi", "100"), opt("--pages"))
        elif cmd == "emu":
            print(to_emu(pos[1]))
        else:
            sys.exit(__doc__)
    except (ValueError, KeyError) as e:
        sys.exit(f"error: {e}")


if __name__ == "__main__":
    main()
