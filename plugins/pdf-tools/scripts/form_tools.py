#!/usr/bin/env python3
"""Fill any PDF form — with or without fillable fields — and prove every answer landed in the right place.

Fillable forms (AcroForm):
  fields    IN [--json OUT.json]          list fields: name, type, page, box, allowed values, current value
  fill      IN VALUES.json OUT            fill by field name; checkboxes accept true/false/yes/no

Flat forms (printed lines, boxes, no fields):
  layout    IN OUT.json [--pages 1-3]     find labels and where each answer goes (lines, boxes, checkboxes)
  fill-flat IN LAYOUT.json ANSWERS.json OUT
                                          ANSWERS = {"field id or label": "value", ...}; checkboxes true/false
Both:
  preview   IN OUT.png [--page N] [--layout LAYOUT.json]
                                          render a page with every detected answer box drawn and numbered
  verify    FILLED.pdf LAYOUT.json ANSWERS.json [--original BLANK.pdf]
                                          read the filled page back and confirm each value sits inside its box

Coordinates in LAYOUT.json: "box" = [x0, top, x1, bottom] in points from the TOP-left (as pdfplumber and
images see it). Converting to PDF space: y_pdf = page_height - top.
"""
import io
import json
import os
import re
import sys

FONT_PATHS = ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
              "/Library/Fonts/Arial Unicode.ttf", "C:/Windows/Fonts/arial.ttf"]
DEVANAGARI = ["/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
              "/usr/share/fonts/opentype/noto/NotoSansDevanagari-Regular.otf"]


# ----------------------------------------------------------------------------- fillable forms
def field_page_map(reader):
    out = {}
    for pi, page in enumerate(reader.pages, 1):
        for a in page.get("/Annots") or []:
            a = a.get_object()
            if a.get("/Subtype") != "/Widget":
                continue
            name = a.get("/T")
            parent = a.get("/Parent")
            if name is None and parent is not None:
                name = parent.get_object().get("/T")
            if name is None:
                continue
            ph = float(page.mediabox.height)
            x0, y0, x1, y1 = [float(v) for v in a.get("/Rect")]
            states = []
            ap = a.get("/AP")
            if ap and "/N" in ap.get_object():
                n = ap.get_object()["/N"]
                if hasattr(n, "keys"):
                    states = [k for k in n.keys() if k != "/Off"]
            out.setdefault(str(name), []).append({"page": pi, "box": [round(x0, 1), round(ph - y1, 1), round(x1, 1),
                                                                   round(ph - y0, 1)], "on_states": states})
    return out


def cmd_fields(src, out=None):
    from pypdf import PdfReader
    r = PdfReader(src)
    fields = r.get_fields() or {}
    pages = field_page_map(r)
    rows = []
    for name, f in fields.items():
        ft = {"/Tx": "text", "/Btn": "button", "/Ch": "choice", "/Sig": "signature"}.get(f.get("/FT"), str(f.get("/FT")))
        widgets = pages.get(name, [])
        states = sorted({s for wd in widgets for s in wd["on_states"]})
        kind = ft
        if ft == "button":
            kind = "radio" if len(widgets) > 1 or (f.get("/Ff", 0) & (1 << 15)) else "checkbox"
        row = {"name": name, "type": kind, "value": str(f.get("/V")) if f.get("/V") is not None else None,
               "pages": sorted({wd["page"] for wd in widgets}), "box": widgets[0]["box"] if widgets else None}
        if kind in ("checkbox", "radio"):
            row["allowed"] = states + ["/Off"]
        if ft == "choice":
            row["allowed"] = [o if isinstance(o, str) else o[1] for o in (f.get("/Opt") or [])]
        rows.append(row)
    if not rows:
        print("no fillable fields — this is a flat form: use `layout` then `fill-flat`")
    for r_ in rows:
        extra = f" allowed={r_['allowed']}" if r_.get("allowed") else ""
        print(f"{r_['name']!r:28} {r_['type']:9} page {r_['pages']} value={r_['value']}{extra}")
    if out:
        json.dump(rows, open(out, "w"), indent=2)
        print(f"-> {out}")
    return rows


def cmd_fill(src, values_path, out):
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import NameObject
    values = json.load(open(values_path))
    r = PdfReader(src)
    info = {f["name"]: f for f in cmd_fields_quiet(r)}
    unknown = [k for k in values if k not in info]
    if unknown:
        sys.exit(f"unknown field(s): {unknown}. Run `fields` to see the names.")
    resolved = {}
    for k, v in values.items():
        f = info[k]
        if f["type"] in ("checkbox", "radio"):
            on = [s for s in f.get("allowed", []) if s != "/Off"]
            if isinstance(v, bool) or str(v).lower() in ("yes", "no", "true", "false", "on", "off", "1", "0", "x", ""):
                truthy = v is True or str(v).lower() in ("yes", "true", "on", "1", "x")
                v = (on[0] if on else "/Yes") if truthy else "/Off"
            elif not str(v).startswith("/"):
                v = "/" + str(v)
            if v not in f.get("allowed", [v]):
                sys.exit(f"{k}: {v} is not allowed; choose from {f['allowed']}")
        elif f["type"] == "choice" and f.get("allowed") and v not in f["allowed"]:
            sys.exit(f"{k}: {v!r} is not one of {f['allowed']}")
        resolved[k] = v
    w = PdfWriter(clone_from=r)
    for page in w.pages:
        w.update_page_form_field_values(page, resolved, auto_regenerate=False)
    w.set_need_appearances_writer(True)
    w.write(out)
    back = {k: v.get("/V") for k, v in (PdfReader(out).get_fields() or {}).items()}
    bad = {k: (resolved[k], back.get(k)) for k in resolved if str(back.get(k)) != str(resolved[k])}
    if bad:
        sys.exit(f"some values did not stick: {bad}")
    print(f"filled {len(resolved)} field(s), all verified -> {out}")


def cmd_fields_quiet(reader):
    import contextlib
    tmp = io.StringIO()
    with contextlib.redirect_stdout(tmp):
        from pypdf import PdfReader  # noqa
        rows = []
        fields = reader.get_fields() or {}
        pages = field_page_map(reader)
        for name, f in fields.items():
            ft = {"/Tx": "text", "/Btn": "button", "/Ch": "choice"}.get(f.get("/FT"), "other")
            widgets = pages.get(name, [])
            kind = ft
            row = {"name": name}
            if ft == "button":
                kind = "radio" if len(widgets) > 1 or (f.get("/Ff", 0) & (1 << 15)) else "checkbox"
                row["allowed"] = sorted({s for wd in widgets for s in wd["on_states"]}) + ["/Off"]
            if ft == "choice":
                row["allowed"] = [o if isinstance(o, str) else o[1] for o in (f.get("/Opt") or [])]
            row["type"] = kind
            rows.append(row)
    return rows


# ----------------------------------------------------------------------------- flat forms
def parse_pages(spec, n):
    if not spec:
        return list(range(1, n + 1))
    out = []
    for part in spec.split(","):
        a, _, b = part.partition("-")
        out += list(range(int(a), int(b or a) + 1)) if "-" in part else [int(a)]
    return [p for p in out if 1 <= p <= n]


def text_lines(words, tol=3):
    lines = []
    for wd in sorted(words, key=lambda w: (round(w["top"]), w["x0"])):
        for ln in lines:
            if abs(ln["top"] - wd["top"]) <= tol and wd["x0"] - ln["x1"] < 40:
                ln["words"].append(wd)
                ln["x1"] = max(ln["x1"], wd["x1"])
                ln["bottom"] = max(ln["bottom"], wd["bottom"])
                break
        else:
            lines.append({"top": wd["top"], "bottom": wd["bottom"], "x0": wd["x0"], "x1": wd["x1"], "words": [wd]})
    for ln in lines:
        ln["text"] = " ".join(w["text"] for w in sorted(ln["words"], key=lambda w: w["x0"]))
    return lines


def cmd_layout(src, out, pages_spec=None):
    import pdfplumber
    fields = []
    with pdfplumber.open(src) as pdf:
        for pno in parse_pages(pages_spec, len(pdf.pages)):
            page = pdf.pages[pno - 1]
            words = page.extract_words(keep_blank_chars=False, use_text_flow=True)
            lines = text_lines([w for w in words if not re.fullmatch(r"_+", w["text"])])
            # entry lines: horizontal rules (lines or very thin rects) at least 30pt long
            rules = []
            for ln in page.lines:
                if abs(ln["top"] - ln["bottom"]) < 1.5 and (ln["x1"] - ln["x0"]) >= 30:
                    rules.append((ln["x0"], ln["top"], ln["x1"], None))
            for rc in page.rects:
                h, wd = rc["bottom"] - rc["top"], rc["x1"] - rc["x0"]
                if h < 1.5 and wd >= 30:
                    rules.append((rc["x0"], rc["top"], rc["x1"], None))
            # underscore runs typed as text: "Name: ________"
            for wd in words:
                m = re.search(r"_{4,}", wd["text"])
                if m:
                    cw = (wd["x1"] - wd["x0"]) / max(len(wd["text"]), 1)
                    hint = re.sub(r"[:\s]+$", "", wd["text"][:m.start()]).strip() or None
                    rules.append((wd["x0"] + m.start() * cw, wd["bottom"] - 1, wd["x0"] + m.end() * cw, hint))
            boxes, checks = [], []
            for rc in page.rects:
                h, wd = rc["bottom"] - rc["top"], rc["x1"] - rc["x0"]
                if 5 <= wd <= 22 and 5 <= h <= 22 and abs(wd - h) <= 4:
                    checks.append((rc["x0"], rc["top"], rc["x1"], rc["bottom"]))
                elif wd >= 40 and 10 <= h <= 220 and wd < float(page.width) * 0.95 and h < float(page.height) * 0.5:
                    boxes.append((rc["x0"], rc["top"], rc["x1"], rc["bottom"]))
            for ch in page.chars:                       # ☐ □ glyph checkboxes
                if ch["text"] in "☐□❏":
                    checks.append((ch["x0"], ch["top"], ch["x1"], ch["bottom"]))

            def label_left_of(x, top, bottom):
                cands = [ln for ln in lines if ln["x1"] <= x + 4 and ln["bottom"] >= top - 2 and ln["top"] <= bottom + 2
                         and not re.fullmatch(r"_+", ln["text"])]
                if not cands:
                    return None
                ln = max(cands, key=lambda l: l["x1"])
                return re.sub(r"[_\s:]+$", "", ln["text"]).strip()

            def label_above(x0, x1, top):
                cands = [ln for ln in lines if ln["bottom"] <= top + 1 and top - ln["bottom"] < 16
                         and ln["x0"] < x1 and ln["x1"] > x0]
                if not cands:
                    return None
                return re.sub(r"[_\s:]+$", "", max(cands, key=lambda l: l["bottom"])["text"]).strip()

            seen = set()
            for x0, y, x1, hint in sorted(rules, key=lambda r: (round(r[1]), r[0])):
                key = (round(x0), round(y))
                if key in seen:
                    continue
                seen.add(key)
                top = y - 14
                label = hint or label_left_of(x0, top, y) or label_above(x0, x1, top) or ""
                fields.append({"page": pno, "kind": "text", "label": label,
                               "box": [round(x0 + 2, 1), round(top, 1), round(x1 - 2, 1), round(y - 1, 1)]})
            for x0, top, x1, bottom in boxes:
                inside = [ln for ln in lines if ln["x0"] >= x0 and ln["x1"] <= x1 and ln["top"] >= top and ln["bottom"] <= bottom]
                label = (inside[0]["text"] if inside else None) or label_left_of(x0, top, bottom) or label_above(x0, x1, top) or ""
                inner_top = (inside[0]["bottom"] + 1) if inside else top + 2
                fields.append({"page": pno, "kind": "text", "label": re.sub(r"[:\s]+$", "", label),
                               "box": [round(x0 + 3, 1), round(inner_top, 1), round(x1 - 3, 1), round(bottom - 2, 1)]})
            for x0, top, x1, bottom in checks:
                right = [ln for ln in lines if ln["x0"] >= x1 - 1 and ln["x0"] - x1 < 60 and
                         ln["top"] <= bottom + 3 and ln["bottom"] >= top - 3]
                label = min(right, key=lambda l: l["x0"])["text"] if right else ""
                fields.append({"page": pno, "kind": "checkbox", "label": label,
                               "box": [round(x0, 1), round(top, 1), round(x1, 1), round(bottom, 1)]})
            fields_page = [f for f in fields if f["page"] == pno]
            for f in fields_page:
                f["page_height"] = float(page.height)
                f["page_width"] = float(page.width)
    for i, f in enumerate(fields, 1):
        f["id"] = f"f{i}"
        base = re.sub(r"[^a-z0-9]+", "_", (f["label"] or "").lower()).strip("_")[:40]
        f["key"] = base or f["id"]
    keys = {}
    for f in fields:
        keys[f["key"]] = keys.get(f["key"], 0) + 1
        if keys[f["key"]] > 1:
            f["key"] = f"{f['key']}_{keys[f['key']]}"
    json.dump(fields, open(out, "w"), indent=2, ensure_ascii=False)
    for f in fields:
        print(f"{f['id']:>4} p{f['page']} {f['kind']:8} key={f['key']!r:28} label={f['label']!r}")
    print(f"{len(fields)} answer spot(s) -> {out}  (check them with `preview` before filling)")


COMPLEX = re.compile(r"[֐-ࣿऀ-෿฀-໿က-႟]")   # Hebrew/Arabic, Indic, Thai/Lao, Myanmar
_font_cache = {}


def covers(path, text):
    try:
        from fontTools.ttLib import TTFont as FT
        key = ("cmap", path)
        if key not in _font_cache:
            f = FT(path, fontNumber=0, lazy=True)
            _font_cache[key] = set(f.getBestCmap() or {})
        cmap = _font_cache[key]
        return all(ord(ch) in cmap for ch in text if not ch.isspace())
    except Exception:
        return False


def font_file_for(text):
    """Find an installed font file that has every character of `text` (fontconfig + cmap check)."""
    import subprocess
    cands = [p for p in FONT_PATHS + DEVANAGARI if os.path.exists(p)]
    for ch in sorted({c for c in text if ord(c) > 127 and not c.isspace()}):
        try:
            out = subprocess.run(["fc-list", f":charset={ord(ch):04x}", "file"], capture_output=True, text=True,
                                 timeout=20).stdout
            files = [l.split(":")[0].strip() for l in out.splitlines() if l.strip()]
            files.sort(key=lambda f: (0 if "NotoSans" in f else 1 if "Noto" in f else 2, "Bold" in f or "Italic" in f, len(f)))
            cands += [f for f in files if f.endswith((".ttf", ".otf"))]
        except Exception:
            pass
    for f in cands:
        if covers(f, text):
            return f
    return None


def pick_font(text):
    """reportlab font name for simple scripts (Latin, Cyrillic, Greek, ₹, ✓ ...)."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    path = font_file_for(text)
    if not path or path.endswith(".otf"):
        path = next((p for p in FONT_PATHS if os.path.exists(p)), None)
    if not path:
        return "Helvetica"
    name = "F_" + re.sub(r"\W", "_", os.path.basename(path).rsplit(".", 1)[0])
    if name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(name, path))
    return name


def shaped_image(text, font_path, size_pt, scale=6):
    """Render complex-script text with real shaping (HarfBuzz via Pillow/raqm) to a transparent PNG."""
    from PIL import Image, ImageDraw, ImageFont, features
    engine = ImageFont.Layout.RAQM if features.check("raqm") else ImageFont.Layout.BASIC
    font = ImageFont.truetype(font_path, int(size_pt * scale), layout_engine=engine)
    l, t, r, b = font.getbbox(text)
    asc, desc = font.getmetrics()
    im = Image.new("RGBA", (max(1, r - min(l, 0) + 4), asc + desc + 4), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((2 - min(l, 0), 2), text, font=font, fill=(0, 0, 0, 255))
    return im, im.width / scale, im.height / scale, (asc + 2) / scale, engine == ImageFont.Layout.RAQM


def wrap(text, width_pt, fn, size):
    from reportlab.pdfbase import pdfmetrics
    lines, cur = [], ""
    for word in text.split():
        trial = (cur + " " + word).strip()
        if pdfmetrics.stringWidth(trial, fn, size) <= width_pt or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    return lines + ([cur] if cur else [])


def resolve_answers(layout, answers):
    by = {}
    for f in layout:
        for k in (f["id"], f["key"], f["label"]):
            if k:
                by.setdefault(k.lower(), f)
    out, missing = [], []
    for k, v in answers.items():
        f = by.get(str(k).lower())
        if not f:
            missing.append(k)
            continue
        out.append((f, v))
    if missing:
        sys.exit(f"no answer spot for: {missing}. Use an id, key or label from the layout file.")
    return out


def cmd_fill_flat(src, layout_path, answers_path, out):
    from pypdf import PdfReader, PdfWriter
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.lib.utils import ImageReader
    layout = json.load(open(layout_path))
    pairs = resolve_answers(layout, json.load(open(answers_path)))
    reader = PdfReader(src)
    writer = PdfWriter()
    by_page = {}
    for f, v in pairs:
        by_page.setdefault(f["page"], []).append((f, v))
    warnings = []
    for pno, page in enumerate(reader.pages, 1):
        if pno in by_page:
            pw, ph = float(page.mediabox.width), float(page.mediabox.height)
            buf = io.BytesIO()
            c = canvas.Canvas(buf, pagesize=(pw, ph))
            for f, v in by_page[pno]:
                x0, top, x1, bottom = f["box"]
                bw, bh = x1 - x0, bottom - top
                if f["kind"] == "checkbox":
                    if v is True or str(v).lower() in ("yes", "true", "x", "1", "on"):
                        fn = pick_font("✓")
                        size = bh * 0.95
                        c.setFont(fn, size)
                        tw = pdfmetrics.stringWidth("✓", fn, size)
                        c.drawString((x0 + x1) / 2 - tw / 2, ph - bottom + bh * 0.15, "✓")
                    continue
                text = str(v).strip()
                if not text:
                    continue
                size = min(11.0, max(6.0, bh * 0.8)) if bh < 26 else 10.5
                if COMPLEX.search(text):
                    path = font_file_for(text)
                    if not path:
                        warnings.append(f"{f['key']}: no installed font covers {text!r} (install a Noto font for that script)")
                        continue
                    im, w_pt, h_pt, asc_pt, shaped = shaped_image(text, path, size)
                    if w_pt > bw:                       # shrink to fit
                        k = bw / w_pt
                        w_pt, h_pt, asc_pt = w_pt * k, h_pt * k, asc_pt * k
                    base_y = ph - bottom + 2 if bh < 26 else ph - top - size * 1.1
                    c.drawImage(ImageReader(im), x0, base_y - (h_pt - asc_pt), width=w_pt, height=h_pt, mask="auto")
                    if not shaped:
                        warnings.append(f"{f['key']}: text shaping engine (raqm) missing; joined letters may look wrong")
                    continue
                fn = pick_font(text)
                if bh >= 26:                             # tall box: wrap from the top
                    lines = wrap(text, bw, fn, size)
                    while len(lines) * size * 1.25 > bh and size > 6:
                        size -= 0.5
                        lines = wrap(text, bw, fn, size)
                    c.setFont(fn, size)
                    for i, ln in enumerate(lines):
                        c.drawString(x0, ph - top - size * (1.1 + 1.25 * i), ln)
                    if len(lines) * size * 1.25 > bh:
                        warnings.append(f"{f['key']}: text overflows its box")
                    continue
                while size > 6 and pdfmetrics.stringWidth(text, fn, size) > bw:
                    size -= 0.5
                if pdfmetrics.stringWidth(text, fn, size) > bw:
                    warnings.append(f"{f['key']}: text too long for its box even at 6 pt")
                c.setFont(fn, size)
                c.drawString(x0, ph - bottom + 2, text)
            c.save()
            page.merge_page(PdfReader(buf).pages[0])
        writer.add_page(page)
    writer.write(out)
    print(f"wrote {len(pairs)} answer(s) -> {out}")
    for wmsg in warnings:
        print("WARN:", wmsg)


def cmd_preview(src, out, page_no=1, layout_path=None):
    import pdfplumber
    from PIL import ImageDraw, ImageFont
    with pdfplumber.open(src) as pdf:
        page = pdf.pages[page_no - 1]
        im = page.to_image(resolution=110).original.convert("RGB")
        s = im.width / float(page.width)
        d = ImageDraw.Draw(im, "RGBA")
        try:
            font = ImageFont.truetype(FONT_PATHS[0], 12)
        except Exception:
            font = ImageFont.load_default()
        spots = []
        if layout_path:
            spots = [f for f in json.load(open(layout_path)) if f["page"] == page_no]
        else:
            for name, ws in field_page_map(__import__("pypdf").PdfReader(src)).items():
                for wd in ws:
                    if wd["page"] == page_no:
                        spots.append({"id": name, "kind": "field", "box": wd["box"]})
        for f in spots:
            x0, top, x1, bottom = [v * s for v in f["box"]]
            col = (220, 38, 38) if f["kind"] == "checkbox" else (37, 99, 235)
            d.rectangle([x0, top, x1, bottom], outline=col + (255,), fill=col + (40,), width=2)
            d.text((x0 + 2, max(0, top - 13)), f.get("key") or f["id"], fill=col + (255,), font=font)
        im.save(out)
    print(f"{len(spots)} box(es) drawn on page {page_no} -> {out}")


def cmd_verify(filled, layout_path, answers_path, original=None):
    """Read each box back from the filled PDF. Text is compared ignoring the form's own underscores/dots;
    complex-script text (drawn as shaped images) is checked by comparing ink against the original page."""
    import pdfplumber
    layout = json.load(open(layout_path))
    pairs = resolve_answers(layout, json.load(open(answers_path)))
    norm = lambda s: re.sub(r"[\s_.…]+", "", s or "")
    ok, bad, visual = 0, [], []
    with pdfplumber.open(filled) as pdf:
        orig = pdfplumber.open(original) if original else None
        for f, v in pairs:
            page = pdf.pages[f["page"] - 1]
            x0, top, x1, bottom = f["box"]
            bbox = (max(0, x0 - 2), max(0, top - 4), min(float(page.width), x1 + 2), min(float(page.height), bottom + 3))
            got = page.crop(bbox).extract_text() or ""
            checked = v is True or str(v).lower() in ("yes", "true", "x", "1", "on")
            if f["kind"] == "checkbox":
                good = ("✓" in got) == checked
            elif COMPLEX.search(str(v)):
                latin = norm(re.sub(COMPLEX, "", str(v)))
                ink = None
                if orig:
                    a = page.crop(bbox).to_image(resolution=72).original.convert("L")
                    b = orig.pages[f["page"] - 1].crop(bbox).to_image(resolution=72).original.convert("L")
                    from PIL import ImageChops
                    ink = sum(1 for px in ImageChops.difference(a, b).getdata() if px > 60)
                good = (ink is None or ink > 20) and (not latin or latin in norm(got) or ink)
                visual.append(f["key"])
            else:
                good = norm(str(v)) in norm(got)
            if good:
                ok += 1
            else:
                bad.append(f"{f['key']}: expected {v!r} inside its box, found {got!r}")
        if orig:
            orig.close()
    for b in bad:
        print("MISPLACED:", b)
    if visual:
        print(f"note: {visual} drawn as shaped images (Indian/Arabic scripts) — confirm in `preview`")
    print(f"{'OK' if not bad else 'FAILED'}: {ok}/{len(pairs)} answers verified inside their boxes")
    sys.exit(1 if bad else 0)


def main():
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    opt = lambda k, d=None: a[a.index(k) + 1] if k in a else d
    pos = [x for i, x in enumerate(a) if not x.startswith("--") and (i == 0 or not a[i - 1].startswith("--"))]
    cmd = pos[0]
    if cmd == "fields" and len(pos) == 2:
        cmd_fields(pos[1], opt("--json"))
    elif cmd == "fill" and len(pos) == 4:
        cmd_fill(*pos[1:])
    elif cmd == "layout" and len(pos) == 3:
        cmd_layout(pos[1], pos[2], opt("--pages"))
    elif cmd == "fill-flat" and len(pos) == 5:
        cmd_fill_flat(*pos[1:])
    elif cmd == "preview" and len(pos) == 3:
        cmd_preview(pos[1], pos[2], int(opt("--page", 1)), opt("--layout"))
    elif cmd == "verify" and len(pos) == 4:
        cmd_verify(*pos[1:], original=opt("--original"))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
