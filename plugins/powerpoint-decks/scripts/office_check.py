#!/usr/bin/env python3
"""Structural health check for .docx / .pptx / .xlsx (and their macro/template variants).

Usage: office_check.py FILE [--render]

Checks:
  * the zip opens, has no duplicate entries, [Content_Types].xml present
  * every XML part is well-formed
  * every part has a content type, every Override points at a real part
  * every internal relationship target exists
  * Word: revision/comment ids are unique and every comment reference has a comment;
          <w:zoom> carries the required percent attribute
  * PowerPoint: every slide in the slide list exists; notes/layout links resolve
  * Excel: every sheet in workbook.xml resolves; shared-string indexes are in range
  * the file opens with python-docx / python-pptx / openpyxl
  * --render: LibreOffice converts it to PDF (prints the page count)

Exit 0 = no errors (warnings allowed), 1 = errors.
"""
import os
import posixpath
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from collections import Counter

from lxml import etree

PR = "http://schemas.openxmlformats.org/package/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
P = "http://schemas.openxmlformats.org/presentationml/2006/main"
S = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
RNS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"

errors, warnings = [], []


def err(m):
    errors.append(m)


def warn(m):
    warnings.append(m)


def rels_path_for(part):
    d, f = posixpath.split(part)
    return posixpath.join(d, "_rels", f + ".rels")


def resolve_target(part, target):
    if target.startswith("/"):
        return target.lstrip("/")
    return posixpath.normpath(posixpath.join(posixpath.dirname(part), target))


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    path = sys.argv[1]
    ext = os.path.splitext(path)[1].lower()
    kind = {"docx": "word", "docm": "word", "dotx": "word", "pptx": "ppt", "pptm": "ppt", "potx": "ppt",
            "xlsx": "excel", "xlsm": "excel", "xltx": "excel"}.get(ext.lstrip("."))
    try:
        z = zipfile.ZipFile(path)
    except zipfile.BadZipFile:
        print(f"ERROR: not a zip/OOXML file: {path}")
        sys.exit(1)
    names = z.namelist()
    for n, c in Counter(names).items():
        if c > 1:
            err(f"duplicate zip entry: {n}")
    if "[Content_Types].xml" not in names:
        err("missing [Content_Types].xml")
        report(path)
    if names[0] != "[Content_Types].xml":
        warn("[Content_Types].xml is not the first zip entry (some tools are picky)")

    trees = {}
    for n in names:
        if n.endswith((".xml", ".rels", ".vml")) and not n.endswith("/"):
            try:
                trees[n] = etree.fromstring(z.read(n))
            except etree.XMLSyntaxError as e:
                err(f"malformed XML in {n}: {e}")

    # content types
    ct = trees.get("[Content_Types].xml")
    if ct is not None:
        defaults = {d.get("Extension", "").lower() for d in ct.findall(f"{{{CT}}}Default")}
        overrides = {o.get("PartName", "").lstrip("/"): o.get("ContentType") for o in ct.findall(f"{{{CT}}}Override")}
        for o in overrides:
            if o not in names:
                warn(f"content-type override for missing part: /{o} (harmless, but untidy)")
        for n in names:
            if n.endswith("/") or n == "[Content_Types].xml":
                continue
            e = n.rsplit(".", 1)[-1].lower() if "." in n else ""
            if n not in overrides and e not in defaults:
                err(f"part has no content type: {n}")

    # relationships
    for n, t in trees.items():
        if not n.endswith(".rels"):
            continue
        src = n.replace("_rels/", "").rsplit(".rels", 1)[0]
        if n == "_rels/.rels":
            src = ""
        ids = Counter()
        for r in t.findall(f"{{{PR}}}Relationship"):
            ids[r.get("Id")] += 1
            if r.get("TargetMode") == "External":
                continue
            tgt = resolve_target(src if src else "x", r.get("Target", "")) if src else r.get("Target", "").lstrip("/")
            if tgt not in names:
                err(f"{n}: relationship {r.get('Id')} -> missing part {tgt}")
        for i, c in ids.items():
            if c > 1:
                err(f"{n}: duplicate relationship id {i}")

    if kind == "word":
        check_word(trees)
    elif kind == "ppt":
        check_ppt(trees, names)
    elif kind == "excel":
        check_excel(trees, names)

    # library open
    try:
        if kind == "word":
            import docx
            d = docx.Document(path)
            print(f"opens in python-docx: {len(d.paragraphs)} paragraphs, {len(d.tables)} tables")
        elif kind == "ppt":
            import pptx
            p = pptx.Presentation(path)
            print(f"opens in python-pptx: {len(p.slides)} slides")
        elif kind == "excel":
            import openpyxl
            wb = openpyxl.load_workbook(path)
            print(f"opens in openpyxl: sheets {wb.sheetnames}")
    except Exception as e:
        err(f"library failed to open file: {e}")

    if "--render" in sys.argv:
        render(path)
    report(path)


def check_word(trees):
    doc = trees.get("word/document.xml")
    if doc is None:
        err("missing word/document.xml")
        return
    w = lambda t: f"{{{W}}}{t}"
    rev_ids = Counter()
    for part, t in trees.items():
        if not part.startswith("word/"):
            continue
        for tag in ("ins", "del"):
            for el in t.iter(w(tag)):
                rev_ids[el.get(w("id"))] += 1
    for i, c in rev_ids.items():
        if c > 1:
            err(f"tracked-change id {i} used {c} times")
    refs = {el.get(w("id")) for el in doc.iter(w("commentReference"))}
    starts = {el.get(w("id")) for el in doc.iter(w("commentRangeStart"))}
    ends = {el.get(w("id")) for el in doc.iter(w("commentRangeEnd"))}
    com = trees.get("word/comments.xml")
    have = {c.get(w("id")) for c in com.iter(w("comment"))} if com is not None else set()
    for r in refs - have:
        err(f"comment reference {r} has no comment in comments.xml")
    for r in starts ^ ends:
        warn(f"comment range {r} has a start without an end (or vice versa)")
    s = trees.get("word/settings.xml")
    if s is not None:
        for z in s.iter(w("zoom")):
            if z.get(w("percent")) is None:
                warn("settings.xml <w:zoom> lacks w:percent (run docx_tools.py fix)")
    for el in doc.iter(w("t")):
        if el.text and el.text != el.text.strip() and el.get("{http://www.w3.org/XML/1998/namespace}space") != "preserve":
            warn("text with leading/trailing spaces lacks xml:space=preserve (spaces may vanish)")
            break


def check_ppt(trees, names):
    pres = trees.get("ppt/presentation.xml")
    if pres is None:
        err("missing ppt/presentation.xml")
        return
    rels = trees.get("ppt/_rels/presentation.xml.rels")
    rmap = {r.get("Id"): r.get("Target") for r in rels.findall(f"{{{PR}}}Relationship")} if rels is not None else {}
    n = 0
    for s in pres.iter(f"{{{P}}}sldId"):
        n += 1
        rid = s.get(f"{{{RNS}}}id")
        tgt = rmap.get(rid)
        if not tgt or resolve_target("ppt/presentation.xml", tgt) not in names:
            err(f"slide list entry {s.get('id')} ({rid}) does not resolve to a slide")
    ids = Counter(s.get("id") for s in pres.iter(f"{{{P}}}sldId"))
    for i, c in ids.items():
        if c > 1:
            err(f"duplicate slide id {i}")
    listed = n
    actual = len([x for x in names if re.match(r"ppt/slides/slide\d+\.xml$", x)])
    if actual > listed:
        warn(f"{actual - listed} slide part(s) exist but are not in the slide list (orphans)")
    print(f"slides listed: {listed}")


def check_excel(trees, names):
    wb = trees.get("xl/workbook.xml")
    if wb is None:
        err("missing xl/workbook.xml")
        return
    rels = trees.get("xl/_rels/workbook.xml.rels")
    rmap = {r.get("Id"): r.get("Target") for r in rels.findall(f"{{{PR}}}Relationship")} if rels is not None else {}
    for sh in wb.iter(f"{{{S}}}sheet"):
        tgt = rmap.get(sh.get(f"{{{RNS}}}id"))
        if not tgt or resolve_target("xl/workbook.xml", tgt) not in names:
            err(f"sheet {sh.get('name')!r} does not resolve to a worksheet part")
    sst = trees.get("xl/sharedStrings.xml")
    n_sst = len(sst.findall(f"{{{S}}}si")) if sst is not None else 0
    for part, t in trees.items():
        if part.startswith("xl/worksheets/") and part.endswith(".xml"):
            for c in t.iter(f"{{{S}}}c"):
                if c.get("t") == "s":
                    v = c.find(f"{{{S}}}v")
                    if v is not None and v.text and int(v.text) >= n_sst:
                        err(f"{part} {c.get('r')}: shared string index {v.text} out of range ({n_sst})")
                if c.get("t") == "e":
                    v = c.find(f"{{{S}}}v")
                    warn(f"{part} {c.get('r')}: cached error value {v.text if v is not None else ''}")


def render(path):
    if not shutil.which("soffice"):
        warn("LibreOffice not installed; skipped render")
        return
    work = tempfile.mkdtemp()
    try:
        subprocess.run(["soffice", f"-env:UserInstallation=file://{work}/p", "--headless", "--convert-to", "pdf",
                        "--outdir", work, path], capture_output=True, timeout=180)
        pdf = os.path.join(work, os.path.splitext(os.path.basename(path))[0] + ".pdf")
        if not os.path.exists(pdf):
            err("LibreOffice could not render the file")
            return
        from pypdf import PdfReader
        print(f"renders: {len(PdfReader(pdf).pages)} page(s)")
    finally:
        shutil.rmtree(work, ignore_errors=True)


def report(path):
    for m in warnings:
        print(f"WARN: {m}")
    for m in errors:
        print(f"ERROR: {m}")
    print(f"{'OK' if not errors else 'FAILED'}: {path} ({len(errors)} error(s), {len(warnings)} warning(s))")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
