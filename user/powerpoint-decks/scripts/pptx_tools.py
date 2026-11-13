#!/usr/bin/env python3
"""Slide-level operations on an existing .pptx (indices are 1-based).

  duplicate IN OUT N [--to POS]   copy slide N (shapes, pictures, charts, background, notes)
  delete    IN OUT N [N ...]      remove slides
  move      IN OUT FROM TO        reorder
  replace   IN OUT "old" "new"    replace text in every slide and notes, keeping run formatting
  theme     IN OUT PALETTE|theme.json [--head FONT] [--body FONT]
                                  restyle the whole deck in one step (theme colours + fonts); palettes: see deck.PALETTES
  sections  IN                    list PowerPoint sections and their slides

Also importable: duplicate_slide(prs, n, to=None), delete_slide(prs, n), move_slide(prs, frm, to).
"""
import copy
import sys

from pptx import Presentation
from pptx.opc.constants import RELATIONSHIP_TYPE as RT
from pptx.opc.package import Part
from pptx.opc.packuri import PackURI

R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def _sld_ids(prs):
    return prs.slides._sldIdLst


def move_slide(prs, frm, to):
    lst = _sld_ids(prs)
    items = list(lst)
    el = items[frm - 1]
    lst.remove(el)
    lst.insert(to - 1, el)


def delete_slide(prs, n):
    lst = _sld_ids(prs)
    el = list(lst)[n - 1]
    rid = el.get(f"{{{R_NS}}}id")
    lst.remove(el)
    prs.part.drop_rel(rid)


def _copy_part(package, part, pattern):
    """Deep-copy a part (and, recursively, its own internal parts such as chart workbooks)."""
    new = type(part).load(PackURI(str(package.next_partname(pattern))), part.content_type, package, part.blob)
    rid_map = {}
    for rid, rel in part.rels.items():
        if rel.is_external:
            rid_map[rid] = new.relate_to(rel.target_ref, rel.reltype, is_external=True)
        elif "embeddings" in str(rel.target_part.partname):
            ext = str(rel.target_part.partname).rsplit(".", 1)[-1]
            child = _copy_part(package, rel.target_part, f"/ppt/embeddings/Microsoft_Excel_Worksheet%d.{ext}")
            rid_map[rid] = new.relate_to(child, rel.reltype)
        else:
            rid_map[rid] = new.relate_to(rel.target_part, rel.reltype)
    if hasattr(new, "_element"):
        for el in new._element.iter():
            for k, v in list(el.attrib.items()):
                if k.startswith(f"{{{R_NS}}}") and v in rid_map:
                    el.set(k, rid_map[v])
    return new


def duplicate_slide(prs, n, to=None):
    src = prs.slides[n - 1]
    new = prs.slides.add_slide(src.slide_layout)
    for shp in list(new.shapes):
        shp._element.getparent().remove(shp._element)
    # background
    src_bg = src._element.cSld.bg
    if src_bg is not None:
        new._element.cSld.insert(0, copy.deepcopy(src_bg))
    # shapes
    tree = new.shapes._spTree
    for el in src.shapes._spTree:
        if el.tag.endswith(("}nvGrpSpPr", "}grpSpPr")):
            continue
        tree.append(copy.deepcopy(el))
    # relationships used by the shapes (pictures, media, charts, hyperlinks)
    rid_map = {}
    pkg = prs.part.package
    for rid, rel in src.part.rels.items():
        if rel.reltype in (RT.SLIDE_LAYOUT, RT.NOTES_SLIDE):
            continue
        if rel.is_external:
            rid_map[rid] = new.part.relate_to(rel.target_ref, rel.reltype, is_external=True)
        elif rel.reltype == RT.CHART:
            chart_copy = _copy_part(pkg, rel.target_part, "/ppt/charts/chart%d.xml")
            rid_map[rid] = new.part.relate_to(chart_copy, rel.reltype)
        else:
            rid_map[rid] = new.part.relate_to(rel.target_part, rel.reltype)
    for el in tree.iter():
        for k, v in list(el.attrib.items()):
            if k.startswith(f"{{{R_NS}}}") and v in rid_map:
                el.set(k, rid_map[v])
    # notes
    if src.has_notes_slide:
        new.notes_slide.notes_text_frame.text = src.notes_slide.notes_text_frame.text
    total = len(prs.slides)
    target = to if to else n + 1
    if target != total:
        move_slide(prs, total, target)
    return new


def replace_text(prs, old, new):
    count = 0

    def frames(shapes):
        for sh in shapes:
            if sh.shape_type == 6:  # group
                yield from frames(sh.shapes)
            if sh.has_text_frame:
                yield sh.text_frame
            if getattr(sh, "has_table", False) and sh.has_table:
                for row in sh.table.rows:
                    for cell in row.cells:
                        yield cell.text_frame

    for slide in prs.slides:
        tfs = list(frames(slide.shapes))
        if slide.has_notes_slide:
            tfs.append(slide.notes_slide.notes_text_frame)
        for tf in tfs:
            for p in tf.paragraphs:
                full = "".join(r.text for r in p.runs)
                if old not in full:
                    continue
                for r in p.runs:
                    if old in r.text:
                        count += r.text.count(old)
                        r.text = r.text.replace(old, new)
                full = "".join(r.text for r in p.runs)
                if old in full and p.runs:          # match spans runs: collapse into first run
                    count += full.count(old)
                    p.runs[0].text = full.replace(old, new)
                    for r in p.runs[1:]:
                        r.text = ""
    return count


def list_sections(path):
    from lxml import etree
    prs = Presentation(path)
    ids = [s.slide_id for s in prs.slides]
    p14 = "http://schemas.microsoft.com/office/powerpoint/2010/main"
    secs = prs.part._element.findall(f".//{{{p14}}}section")
    if not secs:
        print("no sections")
    for s in secs:
        nums = [ids.index(int(x.get("id"))) + 1 for x in s.findall(f".//{{{p14}}}sldId") if int(x.get("id")) in ids]
        print(f"{s.get('name')!r}: slides {nums}")


def main():
    a = sys.argv[1:]
    head = body = None
    for flag in ("--head", "--body"):
        if flag in a:
            i = a.index(flag)
            if flag == "--head":
                head = a[i + 1]
            else:
                body = a[i + 1]
            del a[i:i + 2]
    if len(a) == 2 and a[0] == "sections":
        list_sections(a[1])
        return
    to = None
    if "--to" in a:
        i = a.index("--to")
        to = int(a[i + 1])
        del a[i:i + 2]
    if len(a) < 3:
        sys.exit(__doc__)
    cmd, src, dst, rest = a[0], a[1], a[2], a[3:]
    prs = Presentation(src)
    if cmd == "duplicate" and len(rest) == 1:
        duplicate_slide(prs, int(rest[0]), to)
        msg = f"duplicated slide {rest[0]}"
    elif cmd == "delete" and rest:
        for n in sorted({int(x) for x in rest}, reverse=True):
            delete_slide(prs, n)
        msg = f"deleted slide(s) {', '.join(rest)}"
    elif cmd == "move" and len(rest) == 2:
        move_slide(prs, int(rest[0]), int(rest[1]))
        msg = f"moved slide {rest[0]} -> {rest[1]}"
    elif cmd == "theme" and len(rest) >= 1:
        import json, os
        from deck import PALETTES, write_theme, Theme_from_prs
        spec = rest[0]
        base = Theme_from_prs(prs)
        if spec in PALETTES:
            base.update(PALETTES[spec])
            base["name"] = spec
        elif os.path.exists(spec):
            base.update(json.load(open(spec)))
        else:
            sys.exit(f"unknown palette {spec!r}; choose from {sorted(PALETTES)} or pass a theme.json")
        if head:
            base["font_head"] = head
        if body:
            base["font_body"] = body
        write_theme(prs, base)
        msg = f"theme set to {base.get('name', spec)} (fonts {base['font_head']} / {base['font_body']})"
    elif cmd == "replace" and len(rest) == 2:
        msg = f"replaced {replace_text(prs, rest[0], rest[1])} occurrence(s)"
    else:
        sys.exit(__doc__)
    prs.save(dst)
    print(f"{msg}; {len(prs.slides)} slides -> {dst}")


if __name__ == "__main__":
    main()
