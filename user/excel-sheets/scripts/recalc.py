#!/usr/bin/env python3
"""Recalculate every formula in a workbook with LibreOffice and report error cells.

Usage: recalc.py FILE.xlsx [--timeout 120]

How it works:
  1. LibreOffice (headless) opens a copy, recalculates on load, and saves it.
  2. Computed values are read from that copy and written back into the ORIGINAL
     file as cached results next to each formula (the original keeps all of its
     Excel styling and features; only cached values change).
  3. Every cell holding an error value is listed with its formula.

Links to other workbooks ([1]Sheet!A1) are never recalculated: the linked file usually isn't here, so their
last saved values are kept exactly as they were (other tools wipe them to #REF!).

Exit code: 0 = no errors, 1 = error cells found, 2 = recalculation failed.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from xml.sax.saxutils import escape

from openpyxl import load_workbook

EXTERNAL = re.compile(r"\[\d+\]|\[[^\]]+\.xls[xmb]?\]", re.I)
ERROR_PREFIXES = ("#REF!", "#DIV/0!", "#VALUE!", "#NAME?", "#N/A", "#NUM!", "#NULL!", "Err:", "#ERR")


def libreoffice_recalc(path, timeout):
    """Return path to a recalculated copy inside a temp dir (caller removes the dir)."""
    work = tempfile.mkdtemp(prefix="recalc_")
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    filt = {"xlsx": "xlsx:Calc MS Excel 2007 XML", "xlsm": "xlsm:Calc MS Excel 2007 VBA XML"}.get(ext, ext)
    cmd = ["soffice", f"-env:UserInstallation=file://{work}/profile", "--headless", "--calc",
           "--convert-to", filt, "--outdir", f"{work}/out", path]
    subprocess.run(cmd, check=True, timeout=timeout, capture_output=True)
    out = os.path.join(work, "out", os.path.basename(path))
    if not os.path.exists(out):
        raise RuntimeError("LibreOffice produced no output")
    return work, out


def sheet_xml_paths(z):
    """Map worksheet XML path inside the zip -> sheet name."""
    wb = z.read("xl/workbook.xml").decode("utf8")
    rels = z.read("xl/_rels/workbook.xml.rels").decode("utf8")
    targets = {}
    for rel in re.findall(r"<Relationship\b[^>]*>", rels):
        rid = re.search(r'Id="([^"]+)"', rel)
        tgt = re.search(r'Target="([^"]+)"', rel)
        if rid and tgt:
            t = tgt.group(1).lstrip("/")
            targets[rid.group(1)] = t if t.startswith("xl/") else "xl/" + t
    result = {}
    for sh in re.findall(r"<sheet\b[^>]*>", wb):
        name = re.search(r'name="([^"]+)"', sh).group(1)
        rid = re.search(r'r:id="([^"]+)"', sh).group(1)
        result[targets.get(rid)] = (name.replace("&amp;", "&").replace("&lt;", "<")
                                    .replace("&gt;", ">").replace("&quot;", '"').replace("&apos;", "'"))
    return result


CELL_RE = re.compile(r"<c\b([^>]*)>(<f\b[^>]*/>|<f\b[^>]*>.*?</f>)(?:<v>.*?</v>)?(<is>.*?</is>)?</c>", re.S)


def inject_cached_values(path, computed):
    tmp = path + ".recalc.tmp"
    with zipfile.ZipFile(path) as z, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as out:
        sheets = sheet_xml_paths(z)
        for item in z.infolist():
            data = z.read(item.filename)
            name = sheets.get(item.filename)
            if name and name in computed.sheetnames:
                ws = computed[name]

                def fix(m):
                    attrs, formula = m.group(1), m.group(2)
                    if EXTERNAL.search(formula):
                        return m.group(0)          # link to another workbook: keep its cached value untouched
                    ref = re.search(r'\br="([A-Z]+\d+)"', attrs)
                    if not ref:
                        return m.group(0)
                    v = ws[ref.group(1)].value
                    attrs = re.sub(r'\s+t="[^"]*"', "", attrs)
                    if v is None:
                        return f"<c{attrs}>{formula}</c>"
                    if isinstance(v, bool):
                        return f'<c{attrs} t="b">{formula}<v>{int(v)}</v></c>'
                    if isinstance(v, (int, float)):
                        return f"<c{attrs}>{formula}<v>{repr(v) if isinstance(v, float) else v}</v></c>"
                    if hasattr(v, "isoformat"):            # dates come back as datetime; leave uncached
                        return f"<c{attrs}>{formula}</c>"
                    s = str(v)
                    t = "e" if s.startswith("#") else "str"
                    return f'<c{attrs} t="{t}">{formula}<v>{escape(s)}</v></c>'

                data = CELL_RE.sub(fix, data.decode("utf8")).encode("utf8")
            elif item.filename == "xl/workbook.xml":
                xml = data.decode("utf8")
                if "fullCalcOnLoad" not in xml:
                    if "<calcPr" in xml:
                        xml = re.sub(r"<calcPr\b", '<calcPr fullCalcOnLoad="1"', xml, count=1)
                    else:
                        xml = xml.replace("</workbook>", '<calcPr fullCalcOnLoad="1"/></workbook>')
                data = xml.encode("utf8")
            out.writestr(item, data)
    os.replace(tmp, path)


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    path = os.path.abspath(sys.argv[1])
    timeout = int(sys.argv[sys.argv.index("--timeout") + 1]) if "--timeout" in sys.argv else 120
    if not shutil.which("soffice"):
        print("LibreOffice (soffice) not found", file=sys.stderr)
        sys.exit(2)
    try:
        work, recalced = libreoffice_recalc(path, timeout)
    except Exception as e:
        print(f"recalculation failed: {e}", file=sys.stderr)
        sys.exit(2)
    try:
        computed = load_workbook(recalced, data_only=True)
        formulas_wb = load_workbook(path)
        problems, n_formulas, external = [], 0, []
        for ws in formulas_wb.worksheets:
            ws_v = computed[ws.title] if ws.title in computed.sheetnames else None
            for row in ws.iter_rows():
                for c in row:
                    if isinstance(c.value, str) and c.value.startswith("="):
                        n_formulas += 1
                        if EXTERNAL.search(c.value):
                            external.append(f"{ws.title}!{c.coordinate}")
                            continue
                        v = ws_v[c.coordinate].value if ws_v is not None else None
                        if isinstance(v, str) and v.startswith(ERROR_PREFIXES):
                            problems.append({"cell": f"{ws.title}!{c.coordinate}", "value": v, "formula": c.value})
        inject_cached_values(path, computed)
    finally:
        shutil.rmtree(work, ignore_errors=True)

    report = {"file": path, "formulas": n_formulas, "errors": len(problems), "error_cells": problems[:100]}
    if external:
        report["external_links_kept"] = external[:100]
        report["note"] = ("formulas linking to other workbooks were not recalculated; their last saved values "
                          "were kept so no data is lost")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
