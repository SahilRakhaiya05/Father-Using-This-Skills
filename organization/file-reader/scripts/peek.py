#!/usr/bin/env python3
"""One-command first look at any file: what it is, how big, its structure, and a small sample — never a flood.

Usage: peek.py FILE [--lines 40]

Handles: PDF, Word/ODT/RTF/EPUB, Excel/ODS/legacy XLS, PowerPoint, CSV/TSV, JSON/JSONL, notebooks, images,
archives (zip/tar/gz — listed, never extracted), audio/video, SQLite, text/code/logs, and unknown binaries.
Output is capped (default ~40 sample lines) so a 2 GB file costs the same to peek at as a 2 KB one.
"""
import json
import os
import shutil
import subprocess
import sys
import zipfile

LINES = 40


def sh(cmd, limit=None, timeout=60):
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout
    except Exception as e:
        return f"({cmd[0]} failed: {e})"
    lines = out.splitlines()
    if limit and len(lines) > limit:
        lines = lines[:limit] + [f"… ({len(lines) - limit} more lines)"]
    return "\n".join(lines)


def human(n):
    for u in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.0f} {u}" if u == "B" else f"{n:.1f} {u}"
        n /= 1024


def mime(path):
    return sh(["file", "--brief", "--mime-type", path]).strip() if shutil.which("file") else ""


def peek_pdf(p):
    info = sh(["pdfinfo", p])
    keep = ("Pages", "Page size", "Encrypted", "Title", "Author", "Form")
    print("\n".join(l for l in info.splitlines() if l.split(":")[0] in keep))
    fonts = sh(["pdffonts", p]).splitlines()[2:]
    print(f"fonts: {len(fonts)}" + ("  → no text layer: scanned/image PDF, use OCR or look at page images" if not fonts else ""))
    if fonts:
        print("--- page 1 text sample ---")
        print(sh(["pdftotext", "-f", "1", "-l", "1", "-layout", p, "-"], LINES))
    print("deeper: pdf-reader skill (pdf_inventory.py)")


def peek_doc(p):
    if shutil.which("extract-text"):
        out = sh(["extract-text", p], LINES)
        if out.strip():
            print(out)
            return
    print(sh(["pandoc", p, "-t", "markdown", "--wrap=none"], LINES))


def peek_xlsx(p):
    from openpyxl import load_workbook
    wb = load_workbook(p, read_only=True)
    print(f"sheets: {wb.sheetnames}")
    per = max(4, LINES // max(len(wb.sheetnames), 1))
    for ws in wb.worksheets[:6]:
        print(f"--- {ws.title} (dimension {ws.calculate_dimension() if hasattr(ws, 'calculate_dimension') else '?'}) ---")
        for i, row in enumerate(ws.iter_rows(values_only=True)):
            if i >= per:
                print("…")
                break
            print(" | ".join("" if v is None else str(v)[:30] for v in row[:12]))
    wb.close()
    wbf = load_workbook(p, read_only=True)
    n = sum(1 for ws in wbf.worksheets for row in ws.iter_rows(values_only=True) for v in row
            if isinstance(v, str) and v.startswith("="))
    print(f"formulas: {n}" + ("  (values above may be empty until recalculated)" if n else ""))


def peek_legacy_sheet(p, engine):
    import pandas as pd
    xl = pd.read_excel(p, sheet_name=None, nrows=8, engine=engine, header=None)
    for name, df in list(xl.items())[:6]:
        print(f"--- {name} ---")
        print(df.to_string(max_cols=10, max_colwidth=25))


def peek_pptx(p):
    from pptx import Presentation
    prs = Presentation(p)
    print(f"slides: {len(prs.slides)}")
    for i, s in enumerate(prs.slides, 1):
        shapes = [sh_ for sh_ in s.shapes if sh_.has_text_frame and sh_.text_frame.text.strip()
                  and sh_.name != "Slide Number" and sh_.text_frame.text.strip() not in ("‹#›", "<#>")]
        shapes.sort(key=lambda x: (x.name != "Title" and not (x.is_placeholder and "TITLE" in str(x.placeholder_format.type)),
                                   x.top or 0))
        texts = [x.text_frame.text.strip().replace("\n", " / ") for x in shapes]
        print(f"{i:>3}: {(texts[0] if texts else '(no text)')[:90]}")
        if i >= LINES:
            print("…")
            break


def peek_csv(p, sep=None):
    import csv
    import pandas as pd
    with open(p, newline="", encoding="utf-8", errors="replace") as f:
        head = f.read(20000)
    if sep is None:
        try:
            sep = csv.Sniffer().sniff(head.split("\n", 5)[0] if head else ",").delimiter
        except Exception:
            sep = ","
    n = sum(1 for _ in open(p, "rb"))
    df = pd.read_csv(p, sep=sep, nrows=8, encoding_errors="replace", engine="python")
    print(f"delimiter {sep!r}, ~{n - 1:,} data rows (line count; quoted line breaks can inflate it), {df.shape[1]} columns")
    print(df.to_string(max_cols=12, max_colwidth=25))
    print("--- column types (from first rows) ---")
    print(", ".join(f"{c}: {t}" for c, t in df.dtypes.astype(str).items()))


def peek_json(p):
    size = os.path.getsize(p)
    if size > 200 * 1024 * 1024:
        print("very large JSON: stream it (ijson / jq --stream) rather than loading")
        return
    d = json.load(open(p, encoding="utf-8", errors="replace"))

    def shape(o, depth=0):
        pad = "  " * depth
        if depth > 3:
            return
        if isinstance(o, dict):
            print(f"{pad}object with {len(o)} keys: {list(o)[:15]}")
            for k in list(o)[:5]:
                if isinstance(o[k], (dict, list)):
                    print(f"{pad}  .{k}:")
                    shape(o[k], depth + 2)
        elif isinstance(o, list):
            print(f"{pad}array of {len(o)}" + (f"; first item is {type(o[0]).__name__}" if o else ""))
            if o and isinstance(o[0], (dict, list)):
                shape(o[0], depth + 1)
        else:
            print(f"{pad}{type(o).__name__}: {str(o)[:80]}")
    shape(d)


def peek_jsonl(p):
    n = sum(1 for _ in open(p, "rb"))
    print(f"{n:,} lines")
    with open(p, encoding="utf-8", errors="replace") as f:
        for i, line in enumerate(f):
            if i >= 2:
                break
            try:
                o = json.loads(line)
                print(f"line {i + 1}: keys {list(o)[:15]}" if isinstance(o, dict) else f"line {i + 1}: {line[:150]}")
            except Exception:
                print(f"line {i + 1} (not JSON): {line[:150]}")


def peek_ipynb(p):
    nb = json.load(open(p, encoding="utf-8"))
    cells = nb.get("cells", [])
    print(f"notebook: {len(cells)} cells, kernel {nb.get('metadata', {}).get('kernelspec', {}).get('name')}")
    for c in cells[:12]:
        src = "".join(c.get("source", ""))[:160].replace("\n", " ⏎ ")
        print(f"[{c.get('cell_type')}] {src}")


def peek_image(p):
    from PIL import Image, ExifTags
    im = Image.open(p)
    print(f"{im.format} {im.size[0]}x{im.size[1]} {im.mode}" + (f", {getattr(im, 'n_frames', 1)} frames" if getattr(im, "n_frames", 1) > 1 else ""))
    try:
        ex = {ExifTags.TAGS.get(k, k): v for k, v in im.getexif().items()}
        keep = {k: ex[k] for k in ("DateTime", "Make", "Model", "Orientation", "Software") if k in ex}
        if keep:
            print(f"exif: {keep}")
    except Exception:
        pass
    print("look at it directly; for text in the image: tesseract FILE -")


def peek_archive(p):
    import tarfile
    if zipfile.is_zipfile(p):
        z = zipfile.ZipFile(p)
        infos = z.infolist()
        total = sum(i.file_size for i in infos)
        packed = os.path.getsize(p)
        risky = [i.filename for i in infos if i.filename.startswith("/") or ".." in i.filename.split("/")
                 or (i.external_attr >> 16) & 0o170000 == 0o120000]
        print(f"zip: {len(infos)} entries, {human(total)} uncompressed")
        for i in infos[:LINES]:
            print(f"  {human(i.file_size):>9}  {i.filename}")
        if len(infos) > LINES:
            print(f"  … {len(infos) - LINES} more")
    else:
        t = tarfile.open(p)
        infos = t.getmembers()
        total = sum(i.size for i in infos)
        packed = os.path.getsize(p)
        risky = [i.name for i in infos if i.name.startswith("/") or ".." in i.name.split("/") or i.issym() or i.islnk()]
        print(f"tar: {len(infos)} entries, {human(total)} uncompressed")
        for i in infos[:LINES]:
            print(f"  {human(i.size):>9}  {i.name}")
    if risky:
        print(f"WARNING: unsafe paths or links inside: {risky[:5]} — do not extract blindly")
    if packed and total / packed > 100:
        print(f"WARNING: expands {total / packed:.0f}x — possible zip bomb; extract single files only")
    print("extract only what you need (unzip -p FILE path/inside), into a new empty folder; never run what's inside")


def peek_media(p):
    print(sh(["ffprobe", "-v", "error", "-show_entries",
              "format=duration,size,bit_rate:stream=codec_type,codec_name,width,height,r_frame_rate,sample_rate,channels",
              "-of", "default=nw=1", p], LINES))


def peek_sqlite(p):
    import sqlite3
    con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    tables = [r[0] for r in con.execute("select name from sqlite_master where type='table'")]
    print(f"tables: {len(tables)}")
    for t in tables[:20]:
        cols = [r[1] for r in con.execute(f'pragma table_info("{t}")')]
        n = con.execute(f'select count(*) from "{t}"').fetchone()[0]
        print(f"  {t}: {n:,} rows, columns {cols[:12]}")


def peek_text(p, is_log=False):
    size = os.path.getsize(p)
    n = sum(1 for _ in open(p, "rb"))
    print(f"{n:,} lines, {human(size)}")
    with open(p, encoding="utf-8", errors="replace") as f:
        lines = f.readlines() if size < 50 * 1024 * 1024 else [next(f) for _ in range(LINES)]
    if size <= 20 * 1024 and not is_log:
        print("".join(lines), end="")
        return
    if is_log:
        print("--- last lines (logs: the end usually matters) ---")
        print("".join(lines[-LINES:]), end="")
        errs = [l for l in lines if any(k in l.lower() for k in ("error", "exception", "fatal", "traceback"))]
        print(f"--- {len(errs)} lines mention error/exception ---")
        print("".join(errs[-10:]), end="")
    else:
        print("".join(lines[:LINES - 10]), end="")
        print(f"… ({n - LINES} lines omitted; grep -n for what you need) …")
        print("".join(lines[-10:]), end="")


def main():
    global LINES
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    if "--lines" in a:
        LINES = int(a[a.index("--lines") + 1])
    p = a[0]
    if not os.path.exists(p):
        sys.exit(f"no such file: {p}")
    ext = os.path.splitext(p)[1].lower()
    m = mime(p)
    print(f"== {os.path.basename(p)}  {human(os.path.getsize(p))}  {m}")
    if m and ext in (".xlsx", ".docx", ".pptx", ".pdf") and m in ("text/plain", "text/html", "text/csv"):
        print(f"note: named {ext} but it is really {m}")
    if m in ("text/plain", "text/csv", "text/html") and ext in (".xlsx", ".xls", ".docx", ".pptx", ".pdf"):
        ext = ".csv" if m == "text/csv" or "," in open(p, errors="replace").readline() else ".txt"
    try:
        if ext == ".pdf" or m == "application/pdf":
            peek_pdf(p)
        elif ext in (".docx", ".docm", ".dotx", ".odt", ".rtf", ".epub", ".doc"):
            if ext == ".doc":
                print("legacy .doc: convert first → soffice --headless --convert-to docx FILE")
            else:
                peek_doc(p)
        elif ext in (".xlsx", ".xlsm", ".xltx"):
            peek_xlsx(p)
        elif ext == ".xls":
            peek_legacy_sheet(p, "xlrd")
        elif ext == ".ods":
            peek_legacy_sheet(p, "odf")
        elif ext in (".pptx", ".pptm", ".potx"):
            peek_pptx(p)
        elif ext == ".ppt":
            print("legacy .ppt: convert first → soffice --headless --convert-to pptx FILE")
        elif ext in (".csv", ".tsv") or m == "text/csv":
            peek_csv(p, "\t" if ext == ".tsv" else None)
        elif ext == ".json":
            peek_json(p)
        elif ext in (".jsonl", ".ndjson"):
            peek_jsonl(p)
        elif ext == ".ipynb":
            peek_ipynb(p)
        elif m.startswith("image/") or ext in (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tif", ".tiff", ".heic"):
            peek_image(p)
        elif ext in (".zip", ".tar", ".tgz", ".tbz2", ".txz") or p.endswith((".tar.gz", ".tar.bz2", ".tar.xz")) \
                or m in ("application/zip", "application/x-tar"):
            peek_archive(p)
        elif ext == ".gz":
            print("single gzip file — no listing exists; first lines:")
            print(sh(["bash", "-c", f"zcat -- {json.dumps(p)} | head -n {LINES}"]))
        elif m.startswith(("audio/", "video/")) or ext in (".mp3", ".wav", ".m4a", ".mp4", ".mov", ".mkv", ".webm"):
            peek_media(p)
        elif ext in (".db", ".sqlite", ".sqlite3") or m == "application/vnd.sqlite3":
            peek_sqlite(p)
        elif m.startswith("text/") or m in ("application/json", "application/xml", "application/javascript", "inode/x-empty") \
                or ext in (".md", ".txt", ".log", ".py", ".js", ".ts", ".html", ".xml", ".yaml", ".yml", ".sql", ".sh"):
            peek_text(p, is_log=ext == ".log" or "log" in os.path.basename(p).lower())
        else:
            print("unknown binary; magic bytes:")
            with open(p, "rb") as f:
                b = f.read(64)
            print(" ".join(f"{x:02x}" for x in b))
            print("ask the user what program made it before guessing")
    except Exception as e:
        print(f"could not read as {ext or m}: {e}")


if __name__ == "__main__":
    main()
