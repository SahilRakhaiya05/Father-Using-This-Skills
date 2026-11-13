---
name: excel-sheets
description: Use when a spreadsheet file is the input or output — create, read, edit, clean or analyze .xlsx, .xlsm, .csv or .tsv files; build models with formulas, budgets, trackers, charts, formatting; or convert between tabular formats.
license: MIT. Complete terms in LICENSE.txt
---

# Excel Sheets (.xlsx / .csv)

Tools: **pandas** (reading, cleaning, analysis), **openpyxl** (formulas, formatting, charts, editing workbooks), **LibreOffice** headless (recalculating formulas and catching errors via `scripts/recalc.py`).

## 1. Core rules

1. **Formulas, not pasted numbers.** Totals, growth rates, ratios → Excel formulas (`=SUM(B2:B13)`) so the sheet stays live. Only raw inputs are typed values.
2. **Inputs separate from calculations.** Assumptions live in labelled cells (or an `Inputs` sheet) and formulas point at them: `=B5*(1+Inputs!$B$2)`, never `=B5*1.18`.
3. **Follow the request literally.** Exact sheet names, column headers and the formula the user spelled out. A "better" design that computes something different is a wrong answer.
4. **Say where every number came from.** Typed figures get a source in an adjacent note cell or a cell comment ("Source: FY26 annual report, p. 45" or "Provided by user").
5. **Templates people fill in** get a one-line legend ("edit the yellow cells") and one realistic example row. Never add example rows to a file you were asked to edit.
6. **Editing their file: their conventions win** — fonts, number formats, colours, layout. Find the input cells (usually a distinct colour) and write only there; leave existing formulas alone.
7. **Lint, recalculate, verify** before delivering (section 6). Zero `#REF!`, `#DIV/0!`, `#VALUE!`, `#NAME?`, `#N/A`.
8. **Edit copies.** Never overwrite the user's original.

### Formulas that work everywhere
`scripts/formula_lint.py` enforces this; the reasons:
- Prefer the classic functions: `SUMIFS`, `COUNTIFS`, `INDEX`/`MATCH`, `IFERROR`, `SUMPRODUCT`, `VLOOKUP` with `FALSE`.
- Functions added after Excel 2007 (`TEXTJOIN`, `CONCAT`, `IFS`, `SWITCH`, `MAXIFS`, `MINIFS`, `IFNA`, `STDEV.S`…) are stored in the file as `_xlfn.NAME`. Written bare by Python they show `#NAME?` — the linter adds the prefix for you.
- Avoid dynamic-array functions (`XLOOKUP`, `FILTER`, `SORT`, `UNIQUE`, `SEQUENCE`, `LET`, `LAMBDA`…). Files written by Python lack the spill metadata, so you get `#NAME?` or only the first cell filled. Use `INDEX`/`MATCH`, or sort/filter/de-duplicate in Python and write the result.
- Quote sheet names with spaces or symbols: `='Sales Data'!B4` (the linter fixes this too).
- Guard divisions that can hit zero: `=IFERROR(B5/C5, 0)`.

### Conventions for financial models (unless the user or file says otherwise)
| Thing | Convention |
|---|---|
| Typed inputs / scenario levers | blue font `0000FF` |
| Formulas | black |
| Links to another sheet | green `008000`; links to another file: red |
| Key assumptions, cells for the user to fill | yellow fill `FFFF00` |
| Currency | unit in the header (`Revenue (₹ cr)`), format `#,##0;(#,##0);"-"` — negatives in brackets, zero as a dash |
| Percentages | stored as fractions (0.15) with format `0.0%`; storing 15 shows 1500% |
| Multiples | `0.0"x"` |
| Years | text (`"FY2026"`), never a number with a thousands separator |
| Projections | the same formula across every period; one edited cell mid-row is the most common silent error (the linter flags pattern breaks) |

## 2. Read and explore

```python
import pandas as pd
xl = pd.ExcelFile("data.xlsx")
print(xl.sheet_names)
df = pd.read_excel(xl, sheet_name=0)          # header=None if the header isn't on row 1
print(df.shape); print(df.head(10)); print(df.dtypes)
```

Messy files: look at the raw top rows first (`header=None, nrows=15`) to find where the real header starts, then re-read with `header=N` / `skiprows`. CSV encoding problems: try `encoding="utf-8-sig"` then `"cp1252"`.

To see formulas rather than values: `openpyxl.load_workbook(path)` (default) gives formulas; `data_only=True` gives last-saved values — **never save a workbook opened with data_only=True** (formulas are lost).

## 3. Build a workbook

```python
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

wb = Workbook(); ws = wb.active; ws.title = "Budget"

head = ["Month", "Income", "Expenses", "Savings", "Savings %"]
ws.append(head)
months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]
for i, m in enumerate(months, start=2):
    ws.append([m, 85000, 61000, f"=B{i}-C{i}", f"=IFERROR(D{i}/B{i},0)"])
last = len(months) + 1
ws.append(["Total", f"=SUM(B2:B{last})", f"=SUM(C2:C{last})", f"=SUM(D2:D{last})", f"=IFERROR(D{last+1}/B{last+1},0)"])

# Styling
hdr_fill = PatternFill("solid", fgColor="1F2937")
for c in ws[1]:
    c.font = Font(bold=True, color="FFFFFF"); c.fill = hdr_fill; c.alignment = Alignment(horizontal="center")
for row in ws.iter_rows(min_row=2, min_col=2, max_col=4):
    for c in row: c.number_format = '₹#,##0;[Red]-₹#,##0'
for c in ws["E"][1:]: c.number_format = "0.0%"
for c in ws[last + 1]: c.font = Font(bold=True); c.border = Border(top=Side(style="thin"))
for col, w in zip("ABCDE", (12, 14, 14, 14, 12)): ws.column_dimensions[col].width = w
ws.freeze_panes = "A2"

wb.save("budget.xlsx")
```

Indian grouping (12,34,567): `'[>=10000000]₹##\,##\,##\,##0;[>=100000]₹##\,##\,##0;₹##,##0'`.

### Useful extras

```python
# Excel table with filter buttons and banding
from openpyxl.worksheet.table import Table, TableStyleInfo
tab = Table(displayName="Expenses", ref=f"A1:E{last}")
tab.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True)
ws.add_table(tab)

# Dropdown list
from openpyxl.worksheet.datavalidation import DataValidation
dv = DataValidation(type="list", formula1='"Todo,Doing,Done"', allow_blank=True)
ws.add_data_validation(dv); dv.add("F2:F200")

# Conditional formatting
from openpyxl.formatting.rule import CellIsRule, ColorScaleRule
ws.conditional_formatting.add("D2:D7", CellIsRule(operator="lessThan", formula=["0"], font=Font(color="C00000")))
ws.conditional_formatting.add("E2:E7", ColorScaleRule(start_type="min", start_color="F8696B", end_type="max", end_color="63BE7B"))

# Native chart
from openpyxl.chart import BarChart, LineChart, Reference
ch = BarChart(); ch.title = "Income vs expenses"; ch.y_axis.title = "₹"
ch.add_data(Reference(ws, min_col=2, max_col=3, min_row=1, max_row=last), titles_from_data=True)
ch.set_categories(Reference(ws, min_col=1, min_row=2, max_row=last))
ch.width, ch.height = 18, 9
ws.add_chart(ch, "H2")
```

## 4. Big data: pandas → Excel, then format

```python
with pd.ExcelWriter("report.xlsx", engine="openpyxl") as xw:
    df.to_excel(xw, sheet_name="Data", index=False)
    summary.to_excel(xw, sheet_name="Summary")
# then reopen with openpyxl to add widths, formats, freeze panes, formulas
```

`scripts/autofit.py report.xlsx` sets sensible column widths, freezes the header row and bolds it on every sheet.

## 5. Edit an existing workbook

```python
import shutil; from openpyxl import load_workbook
shutil.copy("theirs.xlsx", "theirs_updated.xlsx")
wb = load_workbook("theirs_updated.xlsx")                  # keep_vba=True for .xlsm
ws = wb["Sheet1"]
ws.insert_rows(10)                                         # NOTE: openpyxl does not shift formula references
```

Inserting/deleting rows does **not** update references in other formulas or charts — prefer appending, or rewrite affected formulas explicitly and verify with recalc. Pivot tables, slicers and some chart formatting can be lost on save; warn the user if the file has them.

## 6. Lint, recalculate and verify

```bash
python3 scripts/formula_lint.py out.xlsx --fix out.xlsx   # auto-fixes prefixes and sheet quoting; lists the rest
python3 scripts/recalc.py out.xlsx                        # computes every formula, lists error cells
python3 scripts/office_check.py out.xlsx                  # structure check
```

It recalculates every formula through LibreOffice, saves the computed values into the file (so viewers that don't calculate still see numbers), and lists any error cells with their formulas. Links to other workbooks are never recalculated — their last saved values are kept (LibreOffice can't see the linked file, and recalculating would wipe the data to `#REF!`). Fix and rerun until it reports zero errors.

**A clean recalc proves formulas *evaluate*, not that they're *right*.** Build 2–3 formulas first and check they pick up the expected cells before filling a whole grid; an off-by-one range gives a tidy, error-free, wrong sheet. Then `python3 scripts/office_check.py out.xlsx` for a structural check (sheets resolve, shared strings in range, opens cleanly). Then spot-check: do totals equal the sum of parts? Are percentages between 0 and 100%? Do signs make sense?

### openpyxl traps
- `load_workbook(path)` gives formulas without values; `data_only=True` gives last-saved values without formulas — you need both loads to read a model.
- Never save a workbook opened with `data_only=True`: every formula becomes a fixed number.
- Right after openpyxl writes a file, `data_only=True` reads `None` for every formula — run `recalc.py` first.
- Merged cells: write only the top-left cell.
- `.xlsm`: pass `keep_vba=True` or the macros are lost.

## 7. CSV / format conversions

```python
pd.read_csv("in.csv").to_excel("out.xlsx", index=False)
pd.read_excel("in.xlsx", sheet_name=None)   # dict of all sheets → write each to CSV
```

CSV has one sheet and no formatting or formulas — say so when converting from Excel.
