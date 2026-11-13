"""Layout helper on top of python-pptx for clean, restylable 16:9 decks.

Everything is coloured with THEME colours and set in THEME fonts, and the theme itself is written into
the file — so in PowerPoint, Design ▸ Variants ▸ Colors/Fonts (or `pptx_tools.py theme`) restyles the
whole deck in one step. Sections show up in PowerPoint's slide sorter.

    from deck import Deck, PALETTES
    d = Deck(theme=PALETTES["harbour"], numbers=True)
    d.title_slide("Title", "Subtitle"); d.section("Results"); d.chart(...); d.save("out.pptx")
"""
import copy
import re
import uuid

from lxml import etree
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_LABEL_POSITION
from pptx.enum.dml import MSO_THEME_COLOR
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR, MSO_AUTO_SIZE
from pptx.opc.constants import RELATIONSHIP_TYPE as RT
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt

import textfit

W, H = 13.333, 7.5          # slide size, inches
M = 0.6                     # outer margin
TITLE_TOP, TITLE_H = 0.45, 1.0
BODY_TOP = 1.75
BODY_H = H - BODY_TOP - 0.7

# Palettes: one dominant dark, a light panel tone, one sharp accent, supporting accents for charts.
PALETTES = {
    "harbour":   {"dark": "0B2545", "text": "1B263B", "bg": "FFFFFF", "panel": "EEF2F7", "accent": "D1495B",
                  "accent2": "13315C", "accent3": "8DA9C4", "accent4": "EDAE49", "accent5": "00798C", "accent6": "6C757D"},
    "monsoon":   {"dark": "1F3B2D", "text": "1E2A23", "bg": "FFFFFF", "panel": "EEF3EC", "accent": "2E8B57",
                  "accent2": "C9A227", "accent3": "6A994E", "accent4": "386641", "accent5": "A7C957", "accent6": "7F8C8D"},
    "saffron":   {"dark": "2B2118", "text": "2B2118", "bg": "FFFFFF", "panel": "FBF3E8", "accent": "E07A1F",
                  "accent2": "6B4226", "accent3": "F2B880", "accent4": "3D5A80", "accent5": "98C1D9", "accent6": "8D8D8D"},
    "indigo":    {"dark": "1E1B4B", "text": "1F2937", "bg": "FFFFFF", "panel": "EEF0FB", "accent": "4F46E5",
                  "accent2": "F59E0B", "accent3": "A5B4FC", "accent4": "0EA5E9", "accent5": "10B981", "accent6": "64748B"},
    "graphite":  {"dark": "111111", "text": "1A1A1A", "bg": "FFFFFF", "panel": "F2F2F2", "accent": "E63946",
                  "accent2": "457B9D", "accent3": "A8A8A8", "accent4": "1D3557", "accent5": "F4A261", "accent6": "6B6B6B"},
    "lagoon":    {"dark": "023E40", "text": "12302F", "bg": "FFFFFF", "panel": "E8F4F3", "accent": "0FA3B1",
                  "accent2": "F25F5C", "accent3": "B5E2DF", "accent4": "247BA0", "accent5": "FFE066", "accent6": "70798C"},
    "plum":      {"dark": "3C1642", "text": "2A1730", "bg": "FFFFFF", "panel": "F5EEF6", "accent": "A4243B",
                  "accent2": "D8973C", "accent3": "BD8B9C", "accent4": "273E47", "accent5": "6B9AC4", "accent6": "7E7E7E"},
    "terrace":   {"dark": "4A3728", "text": "2E2A24", "bg": "FFFFFF", "panel": "F1EDE6", "accent": "C1666B",
                  "accent2": "48A9A6", "accent3": "D4B483", "accent4": "4281A4", "accent5": "E4DFDA", "accent6": "7A7A7A"},
    "glacier":   {"dark": "0F1C2E", "text": "1C2B3A", "bg": "FFFFFF", "panel": "EDF4FA", "accent": "1F7A8C",
                  "accent2": "BFDBF7", "accent3": "E1E5F2", "accent4": "022B3A", "accent5": "FF7F51", "accent6": "8A9BA8"},
    "ember":     {"dark": "1A1A2E", "text": "16161D", "bg": "FFFFFF", "panel": "F3F1F5", "accent": "E94560",
                  "accent2": "0F3460", "accent3": "F9A826", "accent4": "533483", "accent5": "16C79A", "accent6": "6E6E7A"},
}
DEFAULT_THEME = {**PALETTES["harbour"], "font_head": "Calibri", "font_body": "Calibri", "name": "Deck"}

SLOT = {"text": MSO_THEME_COLOR.TEXT_1, "bg": MSO_THEME_COLOR.BACKGROUND_1, "dark": MSO_THEME_COLOR.TEXT_2,
        "panel": MSO_THEME_COLOR.BACKGROUND_2, "accent": MSO_THEME_COLOR.ACCENT_1, "accent2": MSO_THEME_COLOR.ACCENT_2,
        "accent3": MSO_THEME_COLOR.ACCENT_3, "accent4": MSO_THEME_COLOR.ACCENT_4}
SECTION_EXT = "{521415D9-36F7-43E2-AB2F-B90AF26B5E84}"
P14 = "http://schemas.microsoft.com/office/powerpoint/2010/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"


def norm_theme(t):
    t = {**DEFAULT_THEME, **(t or {})}
    t["font_head"] = t.get("font_head") or t.get("head_font") or "Calibri"
    t["font_body"] = t.get("font_body") or t.get("body_font") or "Calibri"
    return t


def write_theme(prs, theme):
    """Write colours and fonts into the deck's theme part (what PowerPoint's Design tab edits)."""
    t = norm_theme(theme)
    part = prs.slide_master.part.part_related_by(RT.THEME)
    root = etree.fromstring(part.blob)
    ns = {"a": A}
    root.set("name", t.get("name", "Deck"))
    cs = root.find(".//a:clrScheme", ns)
    cs.set("name", t.get("name", "Deck"))
    mapping = {"dk1": t["text"], "lt1": t["bg"], "dk2": t["dark"], "lt2": t["panel"], "accent1": t["accent"],
               "accent2": t["accent2"], "accent3": t["accent3"], "accent4": t["accent4"], "accent5": t["accent5"],
               "accent6": t["accent6"], "hlink": t["accent"], "folHlink": t["accent2"]}
    for slot, hexv in mapping.items():
        el = cs.find(f"a:{slot}", ns)
        for c in list(el):
            el.remove(c)
        etree.SubElement(el, f"{{{A}}}srgbClr").set("val", hexv.lstrip("#").upper())
    fs = root.find(".//a:fontScheme", ns)
    fs.set("name", t.get("name", "Deck"))
    for tag, fam in (("majorFont", t["font_head"]), ("minorFont", t["font_body"])):
        fs.find(f"a:{tag}/a:latin", ns).set("typeface", fam)
    part._blob = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def Theme_from_prs(prs):
    """Read the current theme colours/fonts of any deck into a theme dict."""
    part = prs.slide_master.part.part_related_by(RT.THEME)
    root = etree.fromstring(part.blob)
    ns = {"a": A}
    cs = root.find(".//a:clrScheme", ns)

    def col(slot):
        c = cs.find(f"a:{slot}", ns)[0]
        return c.get("val") if etree.QName(c).localname == "srgbClr" else (c.get("lastClr") or "000000")
    return {"text": col("dk1"), "bg": col("lt1"), "dark": col("dk2"), "panel": col("lt2"), "accent": col("accent1"),
            "accent2": col("accent2"), "accent3": col("accent3"), "accent4": col("accent4"), "accent5": col("accent5"),
            "accent6": col("accent6"), "font_head": root.find(".//a:majorFont/a:latin", ns).get("typeface"),
            "font_body": root.find(".//a:minorFont/a:latin", ns).get("typeface"), "name": cs.get("name")}


def set_color(color_format, slot, brightness=0.0):
    color_format.theme_color = SLOT[slot]
    if brightness:
        color_format.brightness = brightness


def add_slide_number(slide, x, y, w, h, size=11):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tb.name = "Slide Number"
    p = tb.text_frame.paragraphs[0]
    p.alignment = PP_ALIGN.RIGHT
    fld = etree.SubElement(p._p, qn("a:fld"))
    fld.set("id", "{" + str(uuid.uuid4()).upper() + "}")
    fld.set("type", "slidenum")
    rpr = etree.SubElement(fld, qn("a:rPr"))
    rpr.set("lang", "en-US")
    rpr.set("sz", str(size * 100))
    sf = etree.SubElement(rpr, qn("a:solidFill"))
    sc = etree.SubElement(sf, qn("a:schemeClr"))
    sc.set("val", "tx1")
    etree.SubElement(sc, qn("a:lumMod")).set("val", "55000")
    etree.SubElement(sc, qn("a:lumOff")).set("val", "45000")
    etree.SubElement(fld, qn("a:t")).text = "‹#›"
    return tb


def write_sections(prs, sections):
    """sections: list of (name, [slide element ids]) in order."""
    pres = prs.part._element
    ext_lst = pres.find(qn("p:extLst"))
    if ext_lst is None:
        ext_lst = etree.SubElement(pres, qn("p:extLst"))
    for ext in ext_lst.findall(qn("p:ext")):
        if ext.get("uri") == SECTION_EXT:
            ext_lst.remove(ext)
    ext = etree.SubElement(ext_lst, qn("p:ext"))
    ext.set("uri", SECTION_EXT)
    sl = etree.SubElement(ext, f"{{{P14}}}sectionLst", nsmap={"p14": P14})
    for name, ids in sections:
        s = etree.SubElement(sl, f"{{{P14}}}section")
        s.set("name", name)
        s.set("id", "{" + str(uuid.uuid4()).upper() + "}")
        lst = etree.SubElement(s, f"{{{P14}}}sldIdLst")
        for i in ids:
            etree.SubElement(lst, f"{{{P14}}}sldId").set("id", str(i))


class Deck:
    def __init__(self, theme=None, template=None, numbers=True, min_body_pt=14):
        self.t = norm_theme(theme)
        self.prs = Presentation(template) if template else Presentation()
        if not template:
            self.prs.slide_width, self.prs.slide_height = Inches(W), Inches(H)
            write_theme(self.prs, self.t)
        self.numbers = numbers
        self.min_body = min_body_pt
        self.n = 0
        self.sections = []          # [name, id of the section's first slide]
        self.head = "+mj-lt"        # theme heading font (resolves to font_head)
        self.body = "+mn-lt"        # theme body font
        self.warnings = []

    # ---------- primitives ----------
    def _blank(self, dark=False, numbered=True):
        layout = self.prs.slide_layouts[6] if len(self.prs.slide_layouts) > 6 else self.prs.slide_layouts[-1]
        s = self.prs.slides.add_slide(layout)
        for ph in list(s.placeholders):
            ph._element.getparent().remove(ph._element)
        bg = s.background.fill
        bg.solid()
        set_color(bg.fore_color, "dark" if dark else "bg")
        self.n += 1
        if not self.sections:
            self.sections.append(["Introduction", None])
        if self.sections[-1][1] is None:
            self.sections[-1][1] = s.slide_id
        if self.numbers and numbered and not dark:
            add_slide_number(s, W - M - 1.0, H - 0.5, 1.0, 0.35)
        return s

    def _measure_font(self, role):
        return self.t["font_head"] if role == "head" else self.t["font_body"]

    def _text(self, s, x, y, w, h, text, size=20, bold=False, color="text", align="left",
              anchor="top", role="body", min_size=None, brightness=0.0, name=None):
        min_size = min_size or self.min_body
        tb = s.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
        if name:
            tb.name = name
        tf = tb.text_frame
        tf.word_wrap = True
        tf.auto_size = MSO_AUTO_SIZE.NONE          # fixed box: we size the text ourselves, QA checks it exactly
        tf.margin_left = tf.margin_right = Inches(0.05)
        tf.margin_top = tf.margin_bottom = Inches(0.03)
        tf.vertical_anchor = {"top": MSO_ANCHOR.TOP, "middle": MSO_ANCHOR.MIDDLE, "bottom": MSO_ANCHOR.BOTTOM}[anchor]
        lines = text if isinstance(text, list) else [text]
        fam = self._measure_font(role)
        fitted = textfit.fit_size(lines, w - 0.1, h - 0.06, fam, size, min_size, bold, 1.2)
        if textfit.height_in("\n".join(lines), w - 0.1, fam, fitted, bold) > h - 0.06:
            self.warnings.append(f"slide {self.n}: text doesn't fit even at {fitted}pt: {lines[0][:40]!r}")
        for i, line in enumerate(lines):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.alignment = {"left": PP_ALIGN.LEFT, "center": PP_ALIGN.CENTER, "right": PP_ALIGN.RIGHT}[align]
            r = p.add_run()
            r.text = line
            f = r.font
            f.size = Pt(fitted)
            f.bold = bold
            f.name = self.head if role == "head" else self.body
            set_color(f.color, color, brightness)
        return tb

    def _rect(self, s, x, y, w, h, slot, shape=MSO_SHAPE.RECTANGLE, brightness=0.0):
        r = s.shapes.add_shape(shape, Inches(x), Inches(y), Inches(w), Inches(h))
        r.fill.solid()
        set_color(r.fill.fore_color, slot, brightness)
        r.line.fill.background()
        r.shadow.inherit = False
        return r

    def _title(self, s, title):
        self._text(s, M, TITLE_TOP, W - 2 * M, TITLE_H, title, size=36, bold=True, role="head",
                   anchor="bottom", min_size=24, name="Title")

    def _notes(self, s, notes):
        if notes:
            s.notes_slide.notes_text_frame.text = notes

    # ---------- layouts ----------
    def title_slide(self, title, subtitle="", notes=None):
        s = self._blank(dark=True, numbered=False)
        self._text(s, 1.0, 2.1, W - 2.0, 2.0, title, size=54, bold=True, color="bg", role="head",
                   anchor="bottom", min_size=32, name="Title")
        if subtitle:
            self._text(s, 1.0, 4.25, W - 2.0, 0.9, subtitle, size=22, color="bg", brightness=-0.25)
        self._notes(s, notes)
        return s

    def section(self, title, subtitle=None, notes=None):
        """Section divider slide that also starts a PowerPoint section."""
        self.sections.append([title, None])
        s = self._blank(dark=True, numbered=False)
        self._text(s, M + 0.4, 2.6, W - 2 * M - 0.8, 1.5, title, size=44, bold=True, color="bg", role="head",
                   anchor="bottom", name="Title")
        if subtitle:
            self._text(s, M + 0.4, 4.2, W - 2 * M - 0.8, 0.8, subtitle, size=20, color="bg", brightness=-0.25)
        self._notes(s, notes)
        return s

    def start_section(self, name):
        """Start a PowerPoint section without a divider slide."""
        self.sections.append([name, None])

    def bullets(self, title, items, notes=None):
        s = self._blank()
        self._title(s, title)
        bw, bh = W - 2 * M, BODY_H - 0.2
        fam = self.t["font_body"]
        size = textfit.fit_size(items, bw - 0.5, bh, fam, 24, self.min_body, False, 1.2, 0.5)
        tb = s.shapes.add_textbox(Inches(M), Inches(BODY_TOP + 0.2), Inches(bw), Inches(bh))
        tf = tb.text_frame
        tf.word_wrap = True
        tf.auto_size = MSO_AUTO_SIZE.NONE
        for i, item in enumerate(items):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            p.space_after = Pt(size * 0.5)
            pPr = p._p.get_or_add_pPr()
            pPr.set("marL", str(int(Inches(0.35))))
            pPr.set("indent", str(-int(Inches(0.35))))
            bu_clr = etree.SubElement(pPr, qn("a:buClr"))
            etree.SubElement(bu_clr, qn("a:schemeClr")).set("val", "accent1")
            etree.SubElement(pPr, qn("a:buFont")).set("typeface", "Arial")
            etree.SubElement(pPr, qn("a:buChar")).set("char", "•")
            r = p.add_run()
            r.text = item
            r.font.size = Pt(size)
            r.font.name = self.body
            set_color(r.font.color, "text")
        self._notes(s, notes)
        return s

    def big_number(self, number, caption, title=None, notes=None):
        s = self._blank()
        if title:
            self._title(s, title)
        self._text(s, M, 1.8, W - 2 * M, 2.7, number, size=140, bold=True, color="accent",
                   align="center", anchor="bottom", role="head", min_size=72)
        self._text(s, 2, 4.7, W - 4, 1.3, caption, size=26, color="text", brightness=0.35, align="center")
        self._notes(s, notes)
        return s

    def stats(self, title, items, notes=None):
        """2-4 stat callouts: items = [(value, label), ...]"""
        s = self._blank()
        self._title(s, title)
        n = len(items)
        gap = 0.4
        cw = (W - 2 * M - gap * (n - 1)) / n
        for i, (val, label) in enumerate(items):
            x = M + i * (cw + gap)
            self._text(s, x, BODY_TOP + 0.6, cw, 1.6, val, size=64, bold=True, color="accent", role="head",
                       anchor="bottom", min_size=36)
            self._text(s, x, BODY_TOP + 2.3, cw, 1.4, label, size=18, brightness=0.3)
        self._notes(s, notes)
        return s

    def two_column(self, title, left, right, left_title=None, right_title=None, notes=None):
        s = self._blank()
        self._title(s, title)
        gap = 0.4
        cw = (W - 2 * M - gap) / 2
        for i, (items, head) in enumerate(((left, left_title), (right, right_title))):
            x = M + i * (cw + gap)
            card = self._rect(s, x, BODY_TOP + 0.2, cw, BODY_H - 0.2, "panel", MSO_SHAPE.ROUNDED_RECTANGLE)
            card.adjustments[0] = 0.04
            y = BODY_TOP + 0.45
            if head:
                self._text(s, x + 0.3, y, cw - 0.6, 0.6, head, size=22, bold=True, role="head",
                           color="accent" if i else "text", brightness=0 if i else 0.35)
                y += 0.75
            self._text(s, x + 0.3, y, cw - 0.6, BODY_TOP + BODY_H - y - 0.2, ["•  " + t for t in items], size=20)
        self._notes(s, notes)
        return s

    def cards(self, title, cards, notes=None):
        """cards: list of (heading, text), 2-4 items."""
        s = self._blank()
        self._title(s, title)
        n = len(cards)
        gap = 0.35
        cw = (W - 2 * M - gap * (n - 1)) / n
        top, ch = BODY_TOP + 0.4, 3.9
        for i, (head, text) in enumerate(cards):
            x = M + i * (cw + gap)
            card = self._rect(s, x, top, cw, ch, "panel", MSO_SHAPE.ROUNDED_RECTANGLE)
            card.adjustments[0] = 0.05
            self._text(s, x + 0.3, top + 0.35, cw - 0.6, 0.95, head, size=24, bold=True, role="head")
            self._text(s, x + 0.3, top + 1.35, cw - 0.6, ch - 1.6, text, size=18, brightness=0.3)
        self._notes(s, notes)
        return s

    def timeline(self, title, steps, notes=None):
        """Process / timeline: steps = [(label, detail), ...] (2-6). Numbers here mean order."""
        s = self._blank()
        self._title(s, title)
        n = len(steps)
        span = W - 2 * M
        y = BODY_TOP + 1.2
        line = s.shapes.add_connector(MSO_CONNECTOR.STRAIGHT, Inches(M + span / (2 * n)), Inches(y),
                                      Inches(M + span - span / (2 * n)), Inches(y))
        set_color(line.line.color, "accent3")
        line.line.width = Pt(2.5)
        for i, (label, detail) in enumerate(steps):
            cx = M + span * (i + 0.5) / n
            dot = self._rect(s, cx - 0.32, y - 0.32, 0.64, 0.64, "accent", MSO_SHAPE.OVAL)
            tf = dot.text_frame
            tf.margin_left = tf.margin_right = 0
            p = tf.paragraphs[0]
            p.alignment = PP_ALIGN.CENTER
            r = p.add_run()
            r.text = str(i + 1)
            r.font.size = Pt(18)
            r.font.bold = True
            r.font.name = self.head
            set_color(r.font.color, "bg")
            cw = span / n - 0.2
            self._text(s, cx - cw / 2, y + 0.55, cw, 0.8, label, size=20, bold=True, align="center", role="head")
            self._text(s, cx - cw / 2, y + 1.35, cw, 1.9, detail, size=16, align="center", brightness=0.3)
        self._notes(s, notes)
        return s

    def table(self, title, rows, col_widths=None, notes=None, number_cols=None):
        """Native table; rows[0] is the header. Numeric columns are right-aligned."""
        s = self._blank()
        self._title(s, title)
        nr, nc = len(rows), len(rows[0])
        tw = W - 2 * M
        rh = min(0.55, (BODY_H - 0.2) / nr)
        gf = s.shapes.add_table(nr, nc, Inches(M), Inches(BODY_TOP + 0.2), Inches(tw), Inches(rh * nr))
        tbl = gf.table
        widths = col_widths or [tw / nc] * nc
        for j, wd in enumerate(widths):
            tbl.columns[j].width = Inches(wd)
        num = set(number_cols or [j for j in range(nc) if all(re.fullmatch(r"[-+₹$€£]?[\d,.]+%?[a-zA-Z]{0,3}",
                                                                           str(r[j]).strip()) for r in rows[1:])])
        tbl.first_row = True
        tbl.horz_banding = False
        for i, row in enumerate(rows):
            for j, val in enumerate(row):
                cell = tbl.cell(i, j)
                cell.text = str(val)
                cell.fill.solid()
                set_color(cell.fill.fore_color, "dark" if i == 0 else ("panel" if i % 2 == 0 else "bg"))
                cell.margin_left = cell.margin_right = Inches(0.12)
                for p in cell.text_frame.paragraphs:
                    p.alignment = PP_ALIGN.RIGHT if (j in num and i > 0) or (j in num and i == 0) else PP_ALIGN.LEFT
                    for r in p.runs:
                        r.font.size = Pt(16 if nr <= 8 else 14)
                        r.font.bold = i == 0
                        r.font.name = self.body
                        set_color(r.font.color, "bg" if i == 0 else "text")
        self._notes(s, notes)
        return s

    def chart(self, title, categories, series, kind="column", notes=None, number_format=None, labels=None):
        """series: {name: [values]}; kind: column | bar | line | pie | stacked. Colours come from the theme."""
        s = self._blank()
        self._title(s, title)
        cd = CategoryChartData()
        cd.categories = categories
        for name, vals in series.items():
            cd.add_series(name, vals)
        ct = {"column": XL_CHART_TYPE.COLUMN_CLUSTERED, "bar": XL_CHART_TYPE.BAR_CLUSTERED,
              "line": XL_CHART_TYPE.LINE_MARKERS, "pie": XL_CHART_TYPE.PIE,
              "stacked": XL_CHART_TYPE.COLUMN_STACKED}[kind]
        gf = s.shapes.add_chart(ct, Inches(M), Inches(BODY_TOP + 0.2), Inches(W - 2 * M),
                                Inches(BODY_H - 0.1), cd)
        ch = gf.chart
        ch.has_title = False                      # the slide title names the chart
        ch.font.size = Pt(14)
        ch.font.name = self.body
        set_color(ch.font.color, "text", 0.25)
        ch.has_legend = len(series) > 1 or kind == "pie"
        if ch.has_legend:
            ch.legend.position = XL_LEGEND_POSITION.BOTTOM
            ch.legend.include_in_layout = False
        plot = ch.plots[0]
        show_labels = labels if labels is not None else (len(categories) <= 8 and len(series) <= 2)
        if show_labels:
            plot.has_data_labels = True
            dl = plot.data_labels
            dl.font.size = Pt(12)
            if number_format:
                dl.number_format = number_format
                dl.number_format_is_linked = False
            if kind in ("column", "bar"):
                dl.position = XL_LABEL_POSITION.OUTSIDE_END
            elif kind == "stacked":
                dl.position = XL_LABEL_POSITION.CENTER
        if kind == "line":
            for ser in plot.series:
                ser.format.line.width = Pt(3)
                ser.smooth = False
        if kind != "pie":
            va = ch.value_axis
            va.has_major_gridlines = True
            va.major_gridlines.format.line.color.rgb = RGBColor(0xE5, 0xE7, 0xEB)
            va.format.line.fill.background()
            ch.category_axis.format.line.color.rgb = RGBColor(0xC8, 0xCC, 0xD2)
            if number_format:
                va.tick_labels.number_format = number_format
                va.tick_labels.number_format_is_linked = False
        self._notes(s, notes)
        return s

    def image_slide(self, title, path, caption=None, notes=None, alt=None):
        from PIL import Image
        s = self._blank()
        self._title(s, title)
        box_w, box_h = W - 2 * M, BODY_H - (0.6 if caption else 0.1)
        iw, ih = Image.open(path).size
        scale = min(box_w / iw, box_h / ih)
        w, h = iw * scale, ih * scale
        pic = s.shapes.add_picture(path, Inches(M + (box_w - w) / 2), Inches(BODY_TOP + 0.1), Inches(w), Inches(h))
        pic._element.nvPicPr.cNvPr.set("descr", alt or caption or title)     # alt text for screen readers
        if caption:
            self._text(s, M, H - 1.15, W - 2 * M, 0.45, caption, size=14, brightness=0.35, align="center",
                       min_size=12)
        self._notes(s, notes)
        return s

    def closing(self, title, subtitle=None, notes=None):
        s = self._blank(dark=True, numbered=False)
        self._text(s, 1.0, 2.6, W - 2.0, 1.5, title, size=48, bold=True, color="bg", role="head", anchor="bottom")
        if subtitle:
            self._text(s, 1.0, 4.2, W - 2.0, 1.0, subtitle, size=22, color="bg", brightness=-0.25)
        self._notes(s, notes)
        return s

    def duplicate(self, index, to=None):
        """Copy slide `index` (1-based) incl. pictures, charts (deep-copied) and notes; insert at `to`."""
        from pptx_tools import duplicate_slide
        duplicate_slide(self.prs, index, to)
        self.n += 1

    def save(self, path):
        starts = {sid: name for name, sid in self.sections if sid is not None}
        secs = []
        for s in self.prs.slides:                       # contiguous by construction
            if s.slide_id in starts or not secs:
                secs.append((starts.get(s.slide_id, "Introduction"), []))
            secs[-1][1].append(s.slide_id)
        if len(secs) > 1:
            write_sections(self.prs, secs)
        self.prs.save(path)
        print(f"saved {path} ({self.n} slides, {len(secs)} sections)")
        for wmsg in self.warnings:
            print("WARN:", wmsg)
