#!/usr/bin/env python3
"""Word (.docx) power tools: review comments, tracked changes, verification. Edits the XML directly,
so formatting is untouched. Run with no arguments for this help.

  fix      IN [OUT]                          schema tidy-up for python-docx/pandoc output (zoom percent,
                                             folder entries in the zip); in place by default
  merge    IN [OUT]                          merge adjacent runs with identical formatting (makes text findable)

  comment  IN OUT "anchor text" "note"       margin comment attached to the anchor text
  reply    IN OUT COMMENT_ID "note"          threaded reply to an existing comment
  resolve-comment IN OUT COMMENT_ID          mark a comment thread as done

  track         IN OUT "old" "new"           tracked replacement of every occurrence (redline)
  track-delete  IN OUT "text in paragraph"   tracked deletion of the whole paragraph containing the text
  track-insert  IN OUT "anchor" "new text" [--before]
                                             tracked insertion of a new paragraph after (or before) the anchor's
  accept   IN OUT                            accept every tracked change (Word semantics, incl. paragraph joins)
  reject   IN OUT                            reject every tracked change
  list     IN                                list tracked changes and comments (with thread structure)
  verify-redline ORIGINAL EDITED            prove every difference in EDITED is a tracked change

Common option: --author "Name" (default "Reviewer").
"""
import copy
import datetime as dt
import os
import random
import re
import shutil
import sys
import tempfile
import zipfile

from lxml import etree

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
W14 = "http://schemas.microsoft.com/office/word/2010/wordml"
W15 = "http://schemas.microsoft.com/office/word/2012/wordml"
PR = "http://schemas.openxmlformats.org/package/2006/relationships"
CT = "http://schemas.openxmlformats.org/package/2006/content-types"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"
REL_COMMENTS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments"
REL_COMMENTS_EX = "http://schemas.microsoft.com/office/2011/relationships/commentsExtended"
CT_COMMENTS = "application/vnd.openxmlformats-officedocument.wordprocessingml.comments+xml"
CT_COMMENTS_EX = "application/vnd.openxmlformats-officedocument.wordprocessingml.commentsExtended+xml"
STORY_RE = re.compile(r"word/(document|header\d*|footer\d*|footnotes|endnotes)\.xml$")


def w(tag):
    return f"{{{W}}}{tag}"


def now():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def para_id():
    return f"{random.randint(1, 0x7FFFFFFE):08X}"


# --------------------------------------------------------------------------- package
class Docx:
    def __init__(self, path):
        self.dir = tempfile.mkdtemp(prefix="docx_")
        with zipfile.ZipFile(path) as z:
            self.order = []
            for info in z.infolist():
                name = info.filename
                if name.endswith("/"):
                    continue                                  # folder entries upset some cloud editors
                if (info.external_attr >> 16) & 0o170000 == 0o120000:
                    continue                                  # never extract symlinks from untrusted files
                if name.startswith("/") or ".." in name.split("/"):
                    continue                                  # path traversal guard
                z.extract(info, self.dir)
                self.order.append(name)

    def read(self, part):
        p = os.path.join(self.dir, part)
        return etree.parse(p) if os.path.exists(p) else None

    def write(self, part, tree):
        p = os.path.join(self.dir, part)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        tree.write(p, xml_declaration=True, encoding="UTF-8", standalone=True)
        if part not in self.order:
            self.order.append(part)

    def save(self, out):
        tmp = out + ".tmp"
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
            for n in sorted(self.order, key=lambda n: n != "[Content_Types].xml"):
                p = os.path.join(self.dir, n)
                if os.path.isfile(p):
                    z.write(p, n)
        os.replace(tmp, out)
        self.close()

    def close(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def stories(self):
        return [n for n in self.order if STORY_RE.match(n)]

    def max_id(self, *trees):
        ids = [0]
        for t in trees:
            if t is None:
                continue
            for el in t.iter():
                v = el.get(w("id"))
                if v and v.lstrip("-").isdigit():
                    ids.append(int(v))
        return max(ids)

    def ensure_part(self, part, root_tag, nsmap, rel_type, content_type):
        tree = self.read(part)
        if tree is None:
            tree = etree.ElementTree(etree.Element(root_tag, nsmap=nsmap))
            ct = self.read("[Content_Types].xml")
            pname = "/" + part
            if not any(o.get("PartName") == pname for o in ct.getroot()):
                o = etree.SubElement(ct.getroot(), f"{{{CT}}}Override")
                o.set("PartName", pname)
                o.set("ContentType", content_type)
                self.write("[Content_Types].xml", ct)
            rels = self.read("word/_rels/document.xml.rels")
            target = part.split("/", 1)[1]
            if not any(r.get("Target") == target for r in rels.getroot()):
                nums = [int(re.sub(r"\D", "", r.get("Id")) or 0) for r in rels.getroot()]
                rel = etree.SubElement(rels.getroot(), f"{{{PR}}}Relationship")
                rel.set("Id", f"rId{max(nums + [0]) + 1}")
                rel.set("Type", rel_type)
                rel.set("Target", target)
                self.write("word/_rels/document.xml.rels", rels)
        return tree


# --------------------------------------------------------------------------- text helpers
def run_text(r):
    return "".join(t.text or "" for t in r.iter(w("t"), w("delText")))


def para_text(p, view="accepted"):
    out = []
    for r in p.iter(w("r")):
        anc = [a.tag for a in r.iterancestors()]
        if view == "accepted" and w("del") in anc:
            continue
        if view == "original" and w("ins") in anc:
            continue
        out.append(run_text(r))
    return "".join(out)


def new_text_run(rpr, text, deleted=False):
    r = etree.Element(w("r"))
    if rpr is not None:
        r.append(copy.deepcopy(rpr))
    t = etree.SubElement(r, w("delText") if deleted else w("t"))
    t.text = text
    t.set(XML_SPACE, "preserve")
    return r


def split_run(r, start, end):
    """Split run r so text[start:end] becomes its own run; returns that middle run."""
    text = run_text(r)
    rpr = r.find(w("rPr"))
    pieces = [(text[:start], False), (text[start:end], True), (text[end:], False)]
    parent, idx = r.getparent(), r.getparent().index(r)
    parent.remove(r)
    mid = None
    for seg, is_mid in pieces:
        if not seg:
            continue
        nr = new_text_run(rpr, seg)
        parent.insert(idx, nr)
        idx += 1
        if is_mid:
            mid = nr
    return mid


def merge_identical_runs(p):
    prev = None
    for r in list(p):
        if r.tag != w("r") or r.find(w("t")) is None or any(c.tag not in (w("rPr"), w("t")) for c in r):
            prev = None
            continue
        if prev is not None:
            a, b = prev.find(w("rPr")), r.find(w("rPr"))
            if (etree.tostring(a) if a is not None else b"") == (etree.tostring(b) if b is not None else b""):
                pt = prev.findall(w("t"))[-1]
                pt.text = (pt.text or "") + run_text(r)
                pt.set(XML_SPACE, "preserve")
                p.remove(r)
                continue
        prev = r


def merge_all(tree):
    for p in tree.getroot().iter(w("p")):
        merge_identical_runs(p)


def find_run(tree, needle, skip_tracked=True):
    for p in tree.getroot().iter(w("p")):
        for r in p.findall(w("r")):
            i = run_text(r).find(needle)
            if i >= 0:
                return p, r, i
    return None


def find_paragraph(tree, needle):
    for p in tree.getroot().iter(w("p")):
        if needle in para_text(p):
            return p
    return None


def mark(tag, rid, author, when):
    el = etree.Element(w(tag))
    el.set(w("id"), str(rid))
    el.set(w("author"), author)
    el.set(w("date"), when)
    return el


def ensure_ppr_rpr(p):
    ppr = p.find(w("pPr"))
    if ppr is None:
        ppr = etree.Element(w("pPr"))
        p.insert(0, ppr)
    rpr = ppr.find(w("rPr"))
    if rpr is None:
        rpr = etree.SubElement(ppr, w("rPr"))
    return rpr


# --------------------------------------------------------------------------- commands
def cmd_fix(src, dst=None):
    dst = dst or src
    d = Docx(src)
    s = d.read("word/settings.xml")
    n = 0
    if s is not None:
        for z in s.getroot().iter(w("zoom")):
            if z.get(w("percent")) is None:
                z.set(w("percent"), "100")
                n += 1
        d.write("word/settings.xml", s)
    d.save(dst)
    print(f"fixed {n} schema issue(s), removed folder entries -> {dst}")


def cmd_merge(src, dst=None):
    dst = dst or src
    d = Docx(src)
    for part in d.stories():
        t = d.read(part)
        before = len(list(t.getroot().iter(w("r"))))
        merge_all(t)
        d.write(part, t)
        print(f"{part}: {before} -> {len(list(t.getroot().iter(w('r'))))} runs")
    d.save(dst)


def comments_parts(d):
    com = d.ensure_part("word/comments.xml", w("comments"), {"w": W, "w14": W14}, REL_COMMENTS, CT_COMMENTS)
    ext = d.ensure_part("word/commentsExtended.xml", f"{{{W15}}}commentsEx", {"w15": W15}, REL_COMMENTS_EX,
                        CT_COMMENTS_EX)
    return com, ext


def add_comment_xml(com, ext, cid, author, text, parent_para=None):
    c = etree.SubElement(com.getroot(), w("comment"))
    c.set(w("id"), str(cid))
    c.set(w("author"), author)
    c.set(w("date"), now())
    c.set(w("initials"), "".join(x[0] for x in author.split())[:3].upper() or "R")
    p = etree.SubElement(c, w("p"))
    pid = para_id()
    p.set(f"{{{W14}}}paraId", pid)
    rr = etree.SubElement(p, w("r"))
    rpr = etree.SubElement(rr, w("rPr"))
    etree.SubElement(rpr, w("rStyle")).set(w("val"), "CommentReference")
    etree.SubElement(rr, w("annotationRef"))
    p.append(new_text_run(None, text))
    ex = etree.SubElement(ext.getroot(), f"{{{W15}}}commentEx")
    ex.set(f"{{{W15}}}paraId", pid)
    if parent_para:
        ex.set(f"{{{W15}}}paraIdParent", parent_para)
    ex.set(f"{{{W15}}}done", "0")
    return pid


def ref_run(cid):
    r = etree.Element(w("r"))
    rpr = etree.SubElement(r, w("rPr"))
    etree.SubElement(rpr, w("rStyle")).set(w("val"), "CommentReference")
    etree.SubElement(r, w("commentReference")).set(w("id"), str(cid))
    return r


def cmd_comment(src, dst, anchor, note, author):
    d = Docx(src)
    doc = d.read("word/document.xml")
    merge_all(doc)
    hit = find_run(doc, anchor)
    if not hit:
        d.close()
        sys.exit(f"anchor not found inside one formatting run: {anchor!r} (try a shorter phrase)")
    p, r, off = hit
    com, ext = comments_parts(d)
    cid = max([int(c.get(w("id"))) for c in com.getroot()] + [-1]) + 1
    mid = split_run(r, off, off + len(anchor))
    s = etree.Element(w("commentRangeStart")); s.set(w("id"), str(cid))
    e = etree.Element(w("commentRangeEnd")); e.set(w("id"), str(cid))
    mid.addprevious(s)
    mid.addnext(e)
    e.addnext(ref_run(cid))
    add_comment_xml(com, ext, cid, author, note)
    for part, t in (("word/comments.xml", com), ("word/commentsExtended.xml", ext), ("word/document.xml", doc)):
        d.write(part, t)
    d.save(dst)
    print(f"comment #{cid} on {anchor!r} -> {dst}")


def cmd_reply(src, dst, parent_id, note, author):
    d = Docx(src)
    doc = d.read("word/document.xml")
    com, ext = comments_parts(d)
    parent = next((c for c in com.getroot() if c.get(w("id")) == str(parent_id)), None)
    if parent is None:
        d.close()
        sys.exit(f"no comment with id {parent_id}")
    ppid = parent.find(w("p")).get(f"{{{W14}}}paraId")
    if not ppid:                                   # older comment without a paraId: give it one
        ppid = para_id()
        parent.find(w("p")).set(f"{{{W14}}}paraId", ppid)
        ex = etree.SubElement(ext.getroot(), f"{{{W15}}}commentEx")
        ex.set(f"{{{W15}}}paraId", ppid)
        ex.set(f"{{{W15}}}done", "0")
    cid = max(int(c.get(w("id"))) for c in com.getroot()) + 1
    root = doc.getroot()
    ps = next(el for el in root.iter(w("commentRangeStart")) if el.get(w("id")) == str(parent_id))
    pe = next(el for el in root.iter(w("commentRangeEnd")) if el.get(w("id")) == str(parent_id))
    s = etree.Element(w("commentRangeStart")); s.set(w("id"), str(cid))
    e = etree.Element(w("commentRangeEnd")); e.set(w("id"), str(cid))
    ps.addnext(s)
    pe.addnext(e)
    pref = next((r for r in root.iter(w("r")) if r.find(w("commentReference")) is not None
                 and r.find(w("commentReference")).get(w("id")) == str(parent_id)), e)
    pref.addnext(ref_run(cid))
    add_comment_xml(com, ext, cid, author, note, parent_para=ppid)
    for part, t in (("word/comments.xml", com), ("word/commentsExtended.xml", ext), ("word/document.xml", doc)):
        d.write(part, t)
    d.save(dst)
    print(f"reply #{cid} to comment #{parent_id} -> {dst}")


def cmd_resolve_comment(src, dst, cid):
    d = Docx(src)
    com, ext = comments_parts(d)
    c = next((c for c in com.getroot() if c.get(w("id")) == str(cid)), None)
    if c is None:
        d.close()
        sys.exit(f"no comment with id {cid}")
    pid = c.find(w("p")).get(f"{{{W14}}}paraId")
    hit = 0
    for ex in ext.getroot():
        if ex.get(f"{{{W15}}}paraId") == pid:
            ex.set(f"{{{W15}}}done", "1")
            hit += 1
    d.write("word/commentsExtended.xml", ext)
    d.save(dst)
    print(f"comment #{cid} marked {'done' if hit else 'done (no extended record found)'} -> {dst}")


def cmd_track(src, dst, old, new, author):
    d = Docx(src)
    doc = d.read("word/document.xml")
    merge_all(doc)
    nid = d.max_id(doc) + 1
    count = 0
    while True:
        hit = None
        for p in doc.getroot().iter(w("p")):
            for r in p.findall(w("r")):          # direct children only: never inside existing ins/del
                i = run_text(r).find(old)
                if i >= 0:
                    hit = (r, i)
                    break
            if hit:
                break
        if not hit:
            break
        r, off = hit
        mid = split_run(r, off, off + len(old))
        stamp = now()
        de = mark("del", nid, author, stamp)
        mid.addprevious(de)
        de.append(mid)
        for t in mid.findall(w("t")):
            t.tag = w("delText")
        if new:
            ins = mark("ins", nid + 1, author, stamp)
            ins.append(new_text_run(mid.find(w("rPr")), new))
            de.addnext(ins)
        nid += 2
        count += 1
    if not count:
        d.close()
        sys.exit(f"text not found inside one formatting run: {old!r}")
    d.write("word/document.xml", doc)
    d.save(dst)
    print(f"{count} tracked replacement(s) {old!r} -> {new!r} -> {dst}")


def cmd_track_delete(src, dst, needle, author):
    d = Docx(src)
    doc = d.read("word/document.xml")
    p = find_paragraph(doc, needle)
    if p is None:
        d.close()
        sys.exit(f"no paragraph contains {needle!r}")
    nid, stamp = d.max_id(doc) + 1, now()
    for r in [c for c in p if c.tag == w("r")]:
        de = mark("del", nid, author, stamp)
        nid += 1
        r.addprevious(de)
        de.append(r)
        for t in r.findall(w("t")):
            t.tag = w("delText")
    rpr = ensure_ppr_rpr(p)
    rpr.insert(0, mark("del", nid, author, stamp))      # deleted paragraph mark => joins with next on accept
    d.write("word/document.xml", doc)
    d.save(dst)
    print(f"tracked deletion of paragraph containing {needle!r} -> {dst}")


def cmd_track_insert(src, dst, anchor, text, author, before=False):
    d = Docx(src)
    doc = d.read("word/document.xml")
    p = find_paragraph(doc, anchor)
    if p is None:
        d.close()
        sys.exit(f"no paragraph contains {anchor!r}")
    nid, stamp = d.max_id(doc) + 1, now()
    newp = etree.Element(w("p"))
    ppr = p.find(w("pPr"))
    if ppr is not None:
        np_ = copy.deepcopy(ppr)
        for old in np_.findall(f"{w('rPr')}/{w('ins')}") + np_.findall(f"{w('rPr')}/{w('del')}"):
            old.getparent().remove(old)
        newp.append(np_)
    ensure_ppr_rpr(newp).insert(0, mark("ins", nid, author, stamp))   # inserted paragraph mark
    first_run = p.find(f".//{w('r')}")
    rpr = first_run.find(w("rPr")) if first_run is not None else None
    ins = mark("ins", nid + 1, author, stamp)
    ins.append(new_text_run(rpr, text))
    newp.append(ins)
    (p.addprevious if before else p.addnext)(newp)
    d.write("word/document.xml", doc)
    d.save(dst)
    print(f"tracked insertion {'before' if before else 'after'} paragraph with {anchor!r} -> {dst}")


def join_with_next(p):
    """Word semantics for a removed paragraph mark: this paragraph's content flows into the next paragraph."""
    nxt = p.getnext()
    while nxt is not None and nxt.tag != w("p"):
        nxt = nxt.getnext()
    content = [c for c in p if c.tag != w("pPr")]
    if nxt is None:
        rpr = p.find(f"{w('pPr')}/{w('rPr')}")
        if rpr is not None:
            for m in list(rpr):
                if m.tag in (w("ins"), w("del")):
                    rpr.remove(m)
        return
    nppr = nxt.find(w("pPr"))
    pos = 1 if nppr is not None else 0
    for c in content:
        nxt.insert(pos, c)
        pos += 1
    p.getparent().remove(p)


def resolve(src, dst, accept=True):
    d = Docx(src)
    keep_tag, drop_tag = (w("ins"), w("del")) if accept else (w("del"), w("ins"))
    n_keep = n_drop = n_join = 0
    for part in d.stories():
        t = d.read(part)
        root = t.getroot()
        # 1. paragraph marks (must run before generic ins/del handling)
        for p in list(root.iter(w("p"))):
            rpr = p.find(f"{w('pPr')}/{w('rPr')}")
            if rpr is None:
                continue
            marks = {m.tag: m for m in rpr if m.tag in (w("ins"), w("del"))}
            if drop_tag in marks:            # the paragraph break itself is undone -> join
                join_with_next(p)
                n_join += 1
            elif keep_tag in marks:
                rpr.remove(marks[keep_tag])
        # 2. run-level changes
        for el in list(root.iter(drop_tag)):
            if el.getparent() is not None and el.getparent().tag == w("rPr"):
                continue
            el.getparent().remove(el)
            n_drop += 1
        for el in list(root.iter(keep_tag)):
            parent = el.getparent()
            if parent is None or parent.tag == w("rPr"):
                continue
            idx = parent.index(el)
            for child in list(el):
                for dtx in child.iter(w("delText")):
                    dtx.tag = w("t")
                parent.insert(idx, child)
                idx += 1
            parent.remove(el)
            n_keep += 1
        # 3. moves and formatting changes
        for a, b in (("moveFrom", "moveTo"),):
            for el in list(root.iter(w(a if accept else b))):
                el.getparent().remove(el)
            for el in list(root.iter(w(b if accept else a))):
                parent, idx = el.getparent(), el.getparent().index(el)
                for child in list(el):
                    parent.insert(idx, child)
                    idx += 1
                parent.remove(el)
        for tag in ("rPrChange", "pPrChange", "sectPrChange", "tblPrChange", "trPrChange", "tcPrChange",
                    "tblGridChange", "numberingChange"):
            for el in list(root.iter(w(tag))):
                holder = el.getparent()
                if not accept:
                    old = el.find("*")
                    for c in list(holder):
                        if c is not el:
                            holder.remove(c)
                    if old is not None:
                        for c in list(old):
                            holder.append(c)
                holder.remove(el)
        for tag in ("moveFromRangeStart", "moveFromRangeEnd", "moveToRangeStart", "moveToRangeEnd"):
            for el in list(root.iter(w(tag))):
                el.getparent().remove(el)
        d.write(part, t)
    d.save(dst)
    print(f"{'accepted' if accept else 'rejected'}: kept {n_keep}, removed {n_drop}, joined {n_join} paragraph(s) -> {dst}")


def cmd_list(src):
    d = Docx(src)
    doc = d.read("word/document.xml")
    for el in doc.getroot().iter(w("ins"), w("del")):
        kind = "INSERT" if el.tag == w("ins") else "DELETE"
        if el.getparent().tag == w("rPr"):
            print(f"{kind} paragraph mark by {el.get(w('author'))}")
            continue
        txt = "".join(x.text or "" for x in el.iter(w("t"), w("delText")))
        print(f"{kind} by {el.get(w('author'))} {el.get(w('date'))}: {txt!r}")
    com = d.read("word/comments.xml")
    ext = d.read("word/commentsExtended.xml")
    exmap = {}
    if ext is not None:
        for ex in ext.getroot():
            exmap[ex.get(f"{{{W15}}}paraId")] = ex
    if com is not None:
        pid_to_id = {}
        for c in com.getroot():
            p = c.find(w("p"))
            pid_to_id[p.get(f"{{{W14}}}paraId") if p is not None else None] = c.get(w("id"))
        for c in com.getroot():
            p = c.find(w("p"))
            ex = exmap.get(p.get(f"{{{W14}}}paraId") if p is not None else None)
            parent = pid_to_id.get(ex.get(f"{{{W15}}}paraIdParent")) if ex is not None else None
            done = ex is not None and ex.get(f"{{{W15}}}done") == "1"
            txt = "".join(x.text or "" for x in c.iter(w("t")))
            print(f"{'  ↳ REPLY' if parent else 'COMMENT'} #{c.get(w('id'))}{f' to #{parent}' if parent else ''}"
                  f" by {c.get(w('author'))}{' [done]' if done else ''}: {txt!r}")
    d.close()


def paragraphs_view(path, view):
    d = Docx(path)
    doc = d.read("word/document.xml")
    out = [para_text(p, view) for p in doc.getroot().iter(w("p"))
           if not (view == "original" and p.find(f"{w('pPr')}/{w('rPr')}/{w('ins')}") is not None)]
    d.close()
    return out


def cmd_verify_redline(orig, edited):
    """Rejecting every change in EDITED must give back ORIGINAL's text exactly."""
    tmp = tempfile.mktemp(suffix=".docx")
    resolve_quiet = sys.stdout
    sys.stdout = open(os.devnull, "w")
    try:
        resolve(edited, tmp, accept=False)
    finally:
        sys.stdout.close()
        sys.stdout = resolve_quiet
    a = [t for t in paragraphs_view(orig, "accepted")]
    b = [t for t in paragraphs_view(tmp, "accepted")]
    os.unlink(tmp)
    import difflib
    diff = [l for l in difflib.unified_diff(a, b, "original", "edited with all changes rejected", lineterm="", n=0)
            if not l.startswith(("---", "+++", "@@"))]
    if diff:
        print("UNTRACKED EDITS FOUND (text changed without a tracked change):")
        for l in diff[:40]:
            print("  " + l)
        sys.exit(1)
    n = sum(1 for _ in Docx_iter_marks(edited))
    print(f"OK: every difference is a tracked change ({n} revision mark(s)); rejecting all restores the original")


def Docx_iter_marks(path):
    d = Docx(path)
    doc = d.read("word/document.xml")
    marks = list(doc.getroot().iter(w("ins"), w("del")))
    d.close()
    return marks


def main():
    a = sys.argv[1:]
    author = "Reviewer"
    if "--author" in a:
        i = a.index("--author")
        author = a[i + 1]
        del a[i:i + 2]
    before = "--before" in a
    a = [x for x in a if x != "--before"]
    if not a:
        sys.exit(__doc__)
    cmd, r = a[0], a[1:]
    table = {
        ("fix", 1): lambda: cmd_fix(*r), ("fix", 2): lambda: cmd_fix(*r),
        ("merge", 1): lambda: cmd_merge(*r), ("merge", 2): lambda: cmd_merge(*r),
        ("comment", 4): lambda: cmd_comment(*r, author),
        ("reply", 4): lambda: cmd_reply(*r, author),
        ("resolve-comment", 3): lambda: cmd_resolve_comment(*r),
        ("track", 4): lambda: cmd_track(*r, author),
        ("track-delete", 3): lambda: cmd_track_delete(*r, author),
        ("track-insert", 4): lambda: cmd_track_insert(*r, author, before),
        ("accept", 2): lambda: resolve(*r, accept=True),
        ("reject", 2): lambda: resolve(*r, accept=False),
        ("list", 1): lambda: cmd_list(*r),
        ("verify-redline", 2): lambda: cmd_verify_redline(*r),
    }
    fn = table.get((cmd, len(r)))
    if not fn:
        sys.exit(__doc__)
    fn()


if __name__ == "__main__":
    main()
