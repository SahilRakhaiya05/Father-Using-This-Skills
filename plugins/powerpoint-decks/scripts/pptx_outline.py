#!/usr/bin/env python3
"""Print an outline of a .pptx: per slide, its text shapes, tables, charts, images and notes.

Usage: pptx_outline.py deck.pptx [--layouts]
"""
import sys
from pptx import Presentation
from pptx.util import Emu


def shape_desc(sh):
    kind = str(sh.shape_type).split(".")[-1].split(" ")[0] if sh.shape_type else "SHAPE"
    pos = f"@({Emu(sh.left).inches:.1f},{Emu(sh.top).inches:.1f}in)" if sh.left is not None else ""
    if sh.has_text_frame and sh.text_frame.text.strip():
        txt = " / ".join(l.strip() for l in sh.text_frame.text.splitlines() if l.strip())
        return f"  [{kind}{pos}] {txt[:160]}"
    if getattr(sh, "has_table", False) and sh.has_table:
        t = sh.table
        rows = [" | ".join(c.text for c in r.cells) for r in t.rows]
        return f"  [TABLE {len(t.rows)}x{len(t.columns)}{pos}]\n" + "\n".join("      " + r[:140] for r in rows[:15])
    if getattr(sh, "has_chart", False) and sh.has_chart:
        c = sh.chart
        lines = [f"  [CHART {str(c.chart_type).split('.')[-1]}{pos}]"]
        try:
            cats = [str(x) for x in c.plots[0].categories]
            lines.append(f"      categories: {cats[:20]}")
            for s in c.plots[0].series:
                lines.append(f"      {s.name}: {list(s.values)[:20]}")
        except Exception:
            pass
        return "\n".join(lines)
    if kind.startswith("PICTURE"):
        alt = sh._element.xpath(".//p:cNvPr/@descr")
        return f"  [PICTURE{pos}] alt={alt[0]!r}" if alt else f"  [PICTURE{pos}] (no alt text)"
    if kind.startswith("GROUP"):
        return f"  [GROUP{pos}] " + "; ".join(s.text_frame.text[:40] for s in sh.shapes if s.has_text_frame and s.text_frame.text.strip())
    return None


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    prs = Presentation(sys.argv[1])
    print(f"slide size: {Emu(prs.slide_width).inches:.2f} x {Emu(prs.slide_height).inches:.2f} in, {len(prs.slides)} slides")
    if "--layouts" in sys.argv:
        for i, lay in enumerate(prs.slide_layouts):
            phs = ", ".join(f"{ph.placeholder_format.idx}:{ph.placeholder_format.type}" for ph in lay.placeholders)
            print(f"layout {i}: {lay.name}  [{phs}]")
    for i, slide in enumerate(prs.slides, 1):
        print(f"\n--- slide {i} (layout: {slide.slide_layout.name})")
        for sh in slide.shapes:
            d = shape_desc(sh)
            if d:
                print(d)
        if slide.has_notes_slide:
            n = slide.notes_slide.notes_text_frame.text.strip()
            if n:
                print(f"  notes: {n[:200]}")


if __name__ == "__main__":
    main()
