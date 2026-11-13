#!/usr/bin/env python3
"""Export one Markdown file to a styled HTML page, Word .docx and/or PDF.

Usage: md_export.py DOC.md [--html] [--docx] [--pdf] [--page a4|letter] [--accent "#2563eb"] [--outdir DIR]
       (no format flags = all three)

Needs pandoc. PDF uses Playwright's Chromium (full Unicode, page numbers in footer).
"""
import os
import re
import subprocess
import sys
import tempfile

CSS = """
:root{--bg:#ffffff;--fg:#1f2937;--muted:#6b7280;--line:#e5e7eb;--panel:#f9fafb;--accent:ACCENT}
@media (prefers-color-scheme:dark){:root:not(.print){--bg:#0f172a;--fg:#e5e7eb;--muted:#94a3b8;--line:#334155;--panel:#1e293b}}
*{box-sizing:border-box}
html{background:var(--bg)}
body{margin:0 auto;max-width:46rem;padding:2.5rem 1rem 4rem;background:var(--bg);color:var(--fg);
 font:16px/1.65 "Inter","Segoe UI",system-ui,-apple-system,"Noto Sans","Noto Sans Devanagari",sans-serif;
 overflow-wrap:anywhere}
header#title-block-header{margin-bottom:2rem;padding-bottom:1.25rem;border-bottom:1px solid var(--line)}
h1.title{font-size:2.1rem;line-height:1.2;margin:0 0 .35rem;letter-spacing:-.01em}
p.subtitle{font-size:1.1rem;color:var(--muted);margin:.2rem 0}
p.author,p.date{color:var(--muted);margin:.1rem 0;font-size:.95rem}
h1,h2,h3,h4{line-height:1.25;margin:2rem 0 .6rem;letter-spacing:-.005em}
h2{font-size:1.45rem} h3{font-size:1.15rem}
p,ul,ol,table,blockquote,pre{margin:0 0 1rem}
a{color:var(--accent)}
li{margin:.2rem 0}
blockquote{margin-left:0;padding:.6rem 1rem;border-left:3px solid var(--accent);background:var(--panel);color:var(--fg)}
code{font:.9em ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;background:var(--panel);padding:.1em .3em;border-radius:4px}
pre{background:var(--panel);padding:.9rem 1rem;border-radius:8px;overflow-x:auto}
pre code{background:none;padding:0}
.table-wrap{overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:.95rem}
th,td{border-bottom:1px solid var(--line);padding:.5rem .6rem;text-align:left;vertical-align:top}
th{font-weight:600;border-bottom:2px solid var(--fg)}
td:has(> :only-child:is(span.num)),td.num{text-align:right}
img{max-width:100%;height:auto}
hr{border:0;border-top:1px solid var(--line);margin:2rem 0}
@media print{body{max-width:none;padding:0;font-size:11pt}h2,h3{break-after:avoid}tr,img,pre,blockquote{break-inside:avoid}
 a{color:inherit}}
"""


def run(cmd, **kw):
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        sys.exit(f"failed: {' '.join(cmd)}\n{r.stderr[-1200:]}")
    return r


def to_html(md, out_html, accent, print_mode=False):
    with tempfile.NamedTemporaryFile("w", suffix=".css", delete=False) as f:
        f.write(CSS.replace("ACCENT", accent))
        css = f.name
    run(["pandoc", md, "-s", "--embed-resources", "--css", css, "-f", "markdown+smart",
         "--metadata", "lang=en", "-o", out_html])
    os.unlink(css)
    html = open(out_html, encoding="utf-8").read()
    if "<title>" not in html or re.search(r"<title>\s*</title>", html):
        first = re.search(r"<h[12][^>]*>(.*?)</h[12]>", html, re.S)
        t = re.sub("<[^>]+>", "", first.group(1)).strip() if first else os.path.splitext(os.path.basename(md))[0]
        html = re.sub(r"<title>.*?</title>", f"<title>{t}</title>", html, flags=re.S) if "<title>" in html \
            else html.replace("</head>", f"<title>{t}</title></head>", 1)
    html = re.sub(r"(<table.*?</table>)", r'<div class="table-wrap">\1</div>', html, flags=re.S)
    if '<meta name="viewport"' not in html:
        html = html.replace("<head>", '<head>\n<meta name="viewport" content="width=device-width, initial-scale=1">', 1)
    if print_mode:
        html = html.replace("<html", '<html class="print"', 1)
    with open(out_html, "w", encoding="utf-8") as f:
        f.write(html)


def reference_docx(path, accent):
    """Build a clean reference.docx: Calibri 11, tidy headings in the accent colour, simple tables."""
    from docx import Document
    from docx.shared import Pt, RGBColor
    run(["pandoc", "-o", path, "--print-default-data-file", "reference.docx"])
    d = Document(path)
    col = RGBColor.from_string(accent.lstrip("#").upper())
    for name in ("Normal", "Body Text", "First Paragraph", "Compact"):
        if name in d.styles:
            st = d.styles[name]
            st.font.name = "Calibri"
            st.font.size = Pt(11)
    for lvl, size in ((1, 18), (2, 15), (3, 13), (4, 12)):
        n = f"Heading {lvl}"
        if n in d.styles:
            st = d.styles[n]
            st.font.name = "Calibri"
            st.font.size = Pt(size)
            st.font.bold = True
            st.font.color.rgb = col if lvl <= 2 else RGBColor(0x1F, 0x29, 0x37)
    for n in ("Title",):
        if n in d.styles:
            d.styles[n].font.name = "Calibri"
            d.styles[n].font.size = Pt(26)
            d.styles[n].font.color.rgb = RGBColor(0x11, 0x18, 0x27)
    d.save(path)


def to_docx(md, out, accent):
    ref = tempfile.mktemp(suffix=".docx")
    reference_docx(ref, accent)
    run(["pandoc", md, "-f", "markdown+smart", "--reference-doc", ref, "-o", out])
    os.unlink(ref)
    # schema tidy-up (python-docx/pandoc zoom attr) if word-docs tools are around; harmless otherwise
    try:
        from docx import Document
        Document(out)
    except Exception as e:
        sys.exit(f"docx did not open: {e}")


def to_pdf(md, out, accent, page):
    from playwright.sync_api import sync_playwright
    tmp_html = tempfile.mktemp(suffix=".html")
    to_html(md, tmp_html, accent, print_mode=True)
    footer = ('<div style="font:9px sans-serif;color:#6b7280;width:100%;text-align:center">'
              '<span class="pageNumber"></span> / <span class="totalPages"></span></div>')
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page()
        pg.emulate_media(media="print", color_scheme="light")
        pg.goto("file://" + tmp_html, wait_until="load")
        pg.pdf(path=out, format="A4" if page == "a4" else "Letter", print_background=True,
               margin={"top": "18mm", "bottom": "18mm", "left": "18mm", "right": "18mm"},
               display_header_footer=True, header_template="<div></div>", footer_template=footer)
        b.close()
    os.unlink(tmp_html)


def main():
    a = sys.argv[1:]
    if not a or not a[0].endswith((".md", ".markdown", ".txt")):
        sys.exit(__doc__)
    md = a[0]
    accent = a[a.index("--accent") + 1] if "--accent" in a else "#2563eb"
    page = a[a.index("--page") + 1].lower() if "--page" in a else "a4"
    outdir = a[a.index("--outdir") + 1] if "--outdir" in a else os.path.dirname(os.path.abspath(md))
    os.makedirs(outdir, exist_ok=True)
    fmts = [f for f in ("html", "docx", "pdf") if f"--{f}" in a] or ["html", "docx", "pdf"]
    base = os.path.join(outdir, os.path.splitext(os.path.basename(md))[0])
    for f in fmts:
        out = f"{base}.{f}"
        {"html": lambda: to_html(md, out, accent), "docx": lambda: to_docx(md, out, accent),
         "pdf": lambda: to_pdf(md, out, accent, page)}[f]()
        print(f"wrote {out} ({os.path.getsize(out) // 1024} KB)")


if __name__ == "__main__":
    main()
