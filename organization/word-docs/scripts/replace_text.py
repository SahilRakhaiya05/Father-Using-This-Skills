#!/usr/bin/env python3
"""Find-and-replace in a .docx while keeping formatting.

Usage: replace_text.py IN.docx OUT.docx OLD NEW [OLD NEW ...]

Works in body paragraphs, tables (including nested), headers and footers.
When a match lies inside one run, only that run changes. When it spans runs,
the spanned text is moved into the first run of the match (its formatting wins).
"""
import sys
from docx import Document


def replace_in_paragraph(p, old, new):
    count = 0
    while True:
        runs = p.runs
        full = "".join(r.text for r in runs)
        idx = full.find(old)
        if idx < 0 or not old:
            return count
        # locate the run span covering [idx, idx+len(old))
        pos, start_run, end_run = 0, None, None
        start_off = end_off = 0
        for i, r in enumerate(runs):
            nxt = pos + len(r.text)
            if start_run is None and idx < nxt:
                start_run, start_off = i, idx - pos
            if start_run is not None and idx + len(old) <= nxt:
                end_run, end_off = i, idx + len(old) - pos
                break
            pos = nxt
        first = runs[start_run]
        if start_run == end_run:
            t = first.text
            first.text = t[:start_off] + new + t[end_off:]
        else:
            last = runs[end_run]
            first.text = first.text[:start_off] + new
            for r in runs[start_run + 1:end_run]:
                r.text = ""
            last.text = last.text[end_off:]
        count += 1


def walk_paragraphs(container):
    for p in container.paragraphs:
        yield p
    for t in getattr(container, "tables", []):
        for row in t.rows:
            for cell in row.cells:
                yield from walk_paragraphs(cell)


def main():
    if len(sys.argv) < 5 or (len(sys.argv) - 3) % 2:
        sys.exit(__doc__)
    src, dst, pairs = sys.argv[1], sys.argv[2], sys.argv[3:]
    doc = Document(src)
    containers = [doc]
    for s in doc.sections:
        containers += [s.header, s.footer, s.first_page_header, s.first_page_footer]
    total = 0
    for old, new in zip(pairs[::2], pairs[1::2]):
        n = 0
        seen = set()
        for c in containers:
            for p in walk_paragraphs(c):
                if id(p._p) in seen:
                    continue
                seen.add(id(p._p))
                n += replace_in_paragraph(p, old, new)
        print(f"{old!r} -> {new!r}: {n} replacement(s)")
        total += n
    doc.save(dst)
    print(f"saved {dst} ({total} total)")


if __name__ == "__main__":
    main()
