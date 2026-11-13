#!/usr/bin/env python3
"""Automated QA for a .pptx — finds the problems people notice first, with slide numbers.

Usage: deck_qa.py DECK.pptx [--min-pt 12] [--json]

ERROR  text overflows its box (measured with real font metrics)     ERROR  shape outside the slide
ERROR  two text boxes overlap                                        ERROR  text below 10 pt
ERROR  leftover placeholder text (lorem, TODO, XXX, "Click to add")
WARN   text below --min-pt (default 12)      WARN  low contrast text (WCAG ratio < 4.5, or < 3 for large text)
WARN   text partly covering a picture/chart   WARN  title moves between slides of the same kind
WARN   empty placeholder                      WARN  content closer than 0.3 in to the slide edge
INFO   picture without alt text               INFO  3+ text-only slides in a row
INFO   font whose preview here is approximate (fit checks less reliable)
Exit code 1 if any ERROR.
"""
import json
import re
import sys
from collections import Counter

from lxml import etree
from pptx import Presentation
from pptx.enum.dml import MSO_COLOR_TYPE
from pptx.enum.shapes import MSO_SHAPE_TYPE, PP_PLACEHOLDER
from pptx.enum.text import MSO_AUTO_SIZE
from pptx.opc.constants import RELATIONSHIP_TYPE as RT
from pptx.util import Emu

import textfit

A = "http://schemas.openxmlformats.org/drawingml/2006/main"
LEFTOVER = re.compile(r"lorem|ipsum|\bTODO\b|\bTBD\b|\bX{3,}\b|click to (add|edit)|\[insert|placeholder text", re.I)
EMU = 914400


def inches(v):
    return (v or 0) / EMU


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def lum(rgb):
    def f(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = rgb
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)


def contrast(a, b):
    la, lb = lum(a), lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def adjust(rgb, brightness):
    if not brightness:
        return rgb
    if brightness > 0:
        return tuple(int(c + (255 - c) * brightness) for c in rgb)
    return tuple(int(c * (1 + brightness)) for c in rgb)


class Theme:
    def __init__(self, prs):
        part = prs.slide_master.part.part_related_by(RT.THEME)
        root = etree.fromstring(part.blob)
        ns = {"a": A}
        self.colors = {}
        for el in root.find(".//a:clrScheme", ns):
            name = etree.QName(el).localname
            c = el[0]
            self.colors[name] = (c.get("val") if etree.QName(c).localname == "srgbClr" else c.get("lastClr")) or "000000"
        self.major = root.find(".//a:majorFont/a:latin", ns).get("typeface")
        self.minor = root.find(".//a:minorFont/a:latin", ns).get("typeface")
        alias = {"bg1": "lt1", "tx1": "dk1", "bg2": "lt2", "tx2": "dk2"}
        self.colors.update({k: self.colors.get(v, "000000") for k, v in alias.items()})

    def font(self, name):
        if not name or name == "+mn-lt":
            return self.minor
        if name == "+mj-lt":
            return self.major
        return name

    def rgb(self, color_format, default="dk1"):
        try:
            t = color_format.type
        except Exception:
            t = None
        if t == MSO_COLOR_TYPE.RGB:
            base = hex_to_rgb(str(color_format.rgb))
        elif t == MSO_COLOR_TYPE.SCHEME:
            key = {1: "dk1", 2: "lt1", 3: "dk2", 4: "lt2", 5: "accent1", 6: "accent2", 7: "accent3", 8: "accent4",
                   9: "accent5", 10: "accent6", 11: "hlink", 12: "folHlink", 13: "dk1", 14: "lt1", 15: "dk1",
                   16: "lt1"}.get(int(color_format.theme_color), "dk1")
            base = hex_to_rgb(self.colors.get(key, "000000"))
        else:
            return hex_to_rgb(self.colors.get(default, "000000"))
        try:
            return adjust(base, color_format.brightness)
        except Exception:
            return base


def fill_rgb(shape, theme):
    try:
        f = shape.fill
        if f.type == 1:                       # solid
            return theme.rgb(f.fore_color)
    except Exception:
        pass
    return None


def box(sh):
    return (inches(sh.left), inches(sh.top), inches(sh.left) + inches(sh.width), inches(sh.top) + inches(sh.height))


def inter(a, b):
    w = min(a[2], b[2]) - max(a[0], b[0])
    h = min(a[3], b[3]) - max(a[1], b[1])
    return max(0, w) * max(0, h)


def contains(a, b, tol=0.02):
    return a[0] <= b[0] + tol and a[1] <= b[1] + tol and a[2] >= b[2] - tol and a[3] >= b[3] - tol


def area(b):
    return max(0, b[2] - b[0]) * max(0, b[3] - b[1])


def walk(shapes):
    for sh in shapes:
        if sh.shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from walk(sh.shapes)
        else:
            yield sh


def qa(path, min_pt=12):
    prs = Presentation(path)
    theme = Theme(prs)
    SW, SH = inches(prs.slide_width), inches(prs.slide_height)
    issues = []
    titles = []
    text_only_run = 0
    approx_fonts = set()

    def add(sev, slide, msg):
        issues.append({"severity": sev, "slide": slide, "message": msg})

    for si, slide in enumerate(prs.slides, 1):
        try:
            bg = theme.rgb(slide.background.fill.fore_color, "lt1") if slide.background.fill.type == 1 else \
                hex_to_rgb(theme.colors["lt1"])
        except Exception:
            bg = hex_to_rgb(theme.colors["lt1"])
        shapes = list(walk(slide.shapes))
        texts, visuals, fills = [], [], []
        for sh in shapes:
            b = box(sh)
            full_bleed = b[0] <= 0.01 and b[1] <= 0.01 and b[2] >= SW - 0.01 and b[3] >= SH - 0.01
            if sh.width is not None and not full_bleed:
                if b[0] < -0.02 or b[1] < -0.02 or b[2] > SW + 0.02 or b[3] > SH + 0.02:
                    add("ERROR", si, f"'{sh.name}' sticks out of the slide ({b[0]:.2f},{b[1]:.2f})–({b[2]:.2f},{b[3]:.2f}) in")
                elif sh.name != "Slide Number" and (b[0] < 0.3 or b[1] < 0.25 or b[2] > SW - 0.3 or b[3] > SH - 0.25):
                    if sh.has_text_frame and sh.text_frame.text.strip():
                        add("WARN", si, f"'{sh.name}' is closer than 0.3 in to the slide edge")
            if sh.shape_type == MSO_SHAPE_TYPE.PICTURE or getattr(sh, "has_chart", False) and sh.has_chart \
                    or getattr(sh, "has_table", False) and sh.has_table:
                visuals.append((sh, b))
                if sh.shape_type == MSO_SHAPE_TYPE.PICTURE and not sh._element.xpath(".//p:cNvPr/@descr"):
                    add("INFO", si, f"picture '{sh.name}' has no alt text")
            f = fill_rgb(sh, theme)
            if f is not None and not (sh.has_text_frame and sh.text_frame.text.strip()):
                fills.append((b, f))
            if sh.is_placeholder and sh.has_text_frame and not sh.text_frame.text.strip():
                add("WARN", si, f"empty placeholder '{sh.name}' (shows 'Click to add…' in PowerPoint)")
            if sh.has_text_frame and sh.text_frame.text.strip():
                texts.append((sh, b, f))
        big_type = any(r.font.size and r.font.size.pt >= 40 for sh, _, _ in texts for p in sh.text_frame.paragraphs
                       for r in p.runs)
        dark_slide = lum(bg) < 0.2
        if not visuals and texts and not any(f for _, _, f in texts) and not fills and not big_type and not dark_slide:
            text_only_run += 1
            if text_only_run == 3:
                add("INFO", si, "third text-only slide in a row: add a chart, picture, big number or cards")
        else:
            text_only_run = 0

        for sh, b, own_fill in texts:
            tf = sh.text_frame
            text = tf.text
            if LEFTOVER.search(text):
                add("ERROR", si, f"leftover placeholder text in '{sh.name}': {text.strip()[:50]!r}")
            sizes, fams = [], []
            for p in tf.paragraphs:
                for r in p.runs:
                    if r.font.size:
                        sizes.append(r.font.size.pt)
                    fams.append(theme.font(r.font.name))
            size = max(sizes) if sizes else 18
            fam = Counter(fams).most_common(1)[0][0] if fams else theme.minor
            if fam.lower() in textfit.UNRELIABLE:
                approx_fonts.add(fam)
            small = min(sizes) if sizes else 18
            if small < 10:
                add("ERROR", si, f"{small:g} pt text in '{sh.name}' is unreadable on a projector")
            elif small < min_pt and sh.name != "Slide Number":
                add("WARN", si, f"{small:g} pt text in '{sh.name}' (minimum {min_pt} pt)")
            # overflow
            if sh.width:
                ml = inches(tf.margin_left) if tf.margin_left is not None else 0.1
                mr = inches(tf.margin_right) if tf.margin_right is not None else 0.1
                mt = inches(tf.margin_top) if tf.margin_top is not None else 0.05
                mb = inches(tf.margin_bottom) if tf.margin_bottom is not None else 0.05
                avail_w = (b[2] - b[0]) - ml - mr - (0.35 if tf.paragraphs[0]._p.find(f"{{{A}}}pPr/{{{A}}}buChar") is not None else 0)
                need = 0
                for p in tf.paragraphs:
                    psz = max([r.font.size.pt for r in p.runs if r.font.size] or [size])
                    bold = any(r.font.bold for r in p.runs)
                    t = "".join(r.text for r in p.runs)
                    sa = p.space_after.pt if p.space_after is not None else 0
                    need += textfit.height_in(t or " ", avail_w if tf.word_wrap is not False else 99, fam, psz, bold, 1.2) + sa / 72
                avail_h = (b[3] - b[1]) - mt - mb
                too_tall = need > avail_h * 1.08 + 0.05
                if too_tall and tf.auto_size == MSO_AUTO_SIZE.SHAPE_TO_FIT_TEXT:
                    grown = (b[0], b[1], b[2], b[1] + need + mt + mb)       # the box will grow downwards
                    hit = [o.name for o, ob, _ in texts if o is not sh and inter(grown, ob) > 0.02 and not contains(ob, grown)]
                    hit += [v.name for v, vb in visuals if inter(grown, vb) > 0.02]
                    if grown[3] > SH:
                        add("ERROR", si, f"'{sh.name}' grows to fit its text and runs off the bottom of the slide")
                    elif hit:
                        add("ERROR", si, f"'{sh.name}' grows to fit its text and then covers {hit[:3]}")
                elif too_tall and tf.auto_size == MSO_AUTO_SIZE.TEXT_TO_FIT_SHAPE:
                    if need > avail_h * 1.6:
                        add("WARN", si, f"'{sh.name}' relies on shrink-to-fit by {need / avail_h:.1f}x; text will be tiny")
                elif too_tall:
                    add("ERROR", si, f"text overflows '{sh.name}': needs {need:.2f} in, box has {avail_h:.2f} in "
                                     f"({text.strip()[:40]!r})")
                if tf.word_wrap is False:
                    longest = max((textfit.width_in(l, fam, size) for l in text.split("\n")), default=0)
                    if longest > (b[2] - b[0]):
                        add("ERROR", si, f"unwrapped text runs past '{sh.name}' ({text.strip()[:40]!r})")
            # contrast: text colour vs the smallest filled shape behind it, else slide background
            behind = own_fill
            if behind is None:
                under = [(area(fb), col) for fb, col in fills if contains(fb, b, 0.05)]
                behind = min(under)[1] if under else bg
            for p in tf.paragraphs:
                for r in p.runs:
                    if not r.text.strip():
                        continue
                    try:
                        fg = theme.rgb(r.font.color) if r.font.color and r.font.color.type is not None else \
                            hex_to_rgb(theme.colors["dk1"])
                    except Exception:
                        fg = hex_to_rgb(theme.colors["dk1"])
                    ratio = contrast(fg, behind)
                    pt = r.font.size.pt if r.font.size else size
                    big = pt >= 18 or (bool(r.font.bold) and pt >= 14)        # WCAG "large text"
                    if ratio < (3 if big else 4.5):
                        add("WARN", si, f"low contrast ({ratio:.1f}:1) in '{sh.name}': {r.text.strip()[:30]!r}")
                        break
                else:
                    continue
                break
        # overlaps
        for i in range(len(texts)):
            for j in range(i + 1, len(texts)):
                a, b2 = texts[i][1], texts[j][1]
                if texts[i][0].name == "Slide Number" or texts[j][0].name == "Slide Number":
                    continue
                ov = inter(a, b2)
                if ov > 0.02 and ov > 0.05 * min(area(a), area(b2)) and not (contains(a, b2) or contains(b2, a)):
                    add("ERROR", si, f"text boxes overlap: '{texts[i][0].name}' and '{texts[j][0].name}'")
        for sh, b, _ in texts:
            for v, vb in visuals:
                if v is sh:
                    continue
                ov = inter(b, vb)
                if ov > 0.02 and not contains(vb, b) and not contains(b, vb):
                    add("WARN", si, f"'{sh.name}' partly covers '{v.name}'")
        # title of this slide: named Title / title placeholder / topmost large text
        cand = [t for t in texts if t[0].name == "Title" or (t[0].is_placeholder and
                t[0].placeholder_format.type in (PP_PLACEHOLDER.TITLE, PP_PLACEHOLDER.CENTER_TITLE))]
        if cand:
            sh, b, _ = cand[0]
            tsize = max([r.font.size.pt for p in sh.text_frame.paragraphs for r in p.runs if r.font.size] or [0])
            kind = (lum(bg) < 0.2, round(tsize))           # same background + same title size = same kind of slide
            titles.append((si, round(b[0], 2), round(b[1], 2), round(b[2] - b[0], 2), kind))

    groups = {}
    for si, x, y, w, dark in titles:
        groups.setdefault(dark, []).append((si, x, y, w))
    for dark, rows in groups.items():
        if len(rows) < 3:
            continue
        common = Counter((x, y) for _, x, y, _ in rows).most_common(1)[0][0]
        for si, x, y, _ in rows:
            if abs(x - common[0]) > 0.15 or abs(y - common[1]) > 0.15:
                add("WARN", si, f"title is at ({x}, {y}) in; other slides of this kind use {common}")
    for f in sorted(approx_fonts):
        add("INFO", 0, f"font '{f}' has no metric-compatible stand-in here: fit checks are approximate (leave ~10% slack)")
    return issues, len(prs.slides)


def main():
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    min_pt = float(a[a.index("--min-pt") + 1]) if "--min-pt" in a else 12
    issues, n = qa(a[0], min_pt)
    if "--json" in a:
        print(json.dumps(issues, indent=2, ensure_ascii=False))
    else:
        order = {"ERROR": 0, "WARN": 1, "INFO": 2}
        for i in sorted(issues, key=lambda x: (x["slide"], order[x["severity"]])):
            where = f"slide {i['slide']:>2}" if i["slide"] else "deck    "
            print(f"{i['severity']:5} {where}  {i['message']}")
        c = Counter(i["severity"] for i in issues)
        print(f"{'FAILED' if c['ERROR'] else 'OK'}: {n} slides — {c['ERROR']} error(s), {c['WARN']} warning(s), {c['INFO']} note(s)")
    sys.exit(1 if any(i["severity"] == "ERROR" for i in issues) else 0)


if __name__ == "__main__":
    main()
