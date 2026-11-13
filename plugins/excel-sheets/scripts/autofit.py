#!/usr/bin/env python3
"""Tidy every sheet: fit column widths to content, bold + freeze the header row, add autofilter.

Usage: autofit.py FILE.xlsx [OUT.xlsx] [--no-filter]
"""
import sys
from openpyxl import load_workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    src = args[0]
    dst = args[1] if len(args) > 1 else src
    wb = load_workbook(src)
    for ws in wb.worksheets:
        if ws.max_row < 1 or ws.max_column < 1:
            continue
        widths = {}
        for row in ws.iter_rows(min_row=1, max_row=min(ws.max_row, 2000)):
            for c in row:
                if c.value is None:
                    continue
                v = c.value
                if isinstance(v, str) and v.startswith("="):
                    n = 12
                elif isinstance(v, float):
                    n = len(f"{v:,.2f}")
                else:
                    n = max(len(l) for l in str(v).splitlines()) if str(v) else 0
                widths[c.column] = max(widths.get(c.column, 0), n)
        for col, n in widths.items():
            ws.column_dimensions[get_column_letter(col)].width = min(max(n + 2, 8), 60)
        if not ws.tables:
            for c in ws[1]:
                if c.value is not None:
                    c.font = Font(bold=True, color=c.font.color.rgb if c.font and c.font.color and isinstance(c.font.color.rgb, str) else None)
            if "--no-filter" not in sys.argv and ws.max_row > 1:
                ws.auto_filter.ref = ws.dimensions
        if ws.freeze_panes is None:
            ws.freeze_panes = "A2"
    wb.save(dst)
    print(f"tidied {len(wb.worksheets)} sheet(s) -> {dst}")


if __name__ == "__main__":
    main()
