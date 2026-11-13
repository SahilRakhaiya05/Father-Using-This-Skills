#!/usr/bin/env python3
"""Find formula problems before they become #NAME?, #REF! or silently wrong numbers — and fix the safe ones.

Usage: formula_lint.py BOOK.xlsx [--fix OUT.xlsx] [--json]

Checks every formula:
  ERROR  newer function written without its "_xlfn." storage prefix  -> #NAME? in Excel/LibreOffice   [auto-fixed]
  ERROR  dynamic-array / spill function (XLOOKUP, FILTER, SORT, UNIQUE, LET...) -> often #NAME? or only
         the top-left cell gets a value when written by openpyxl; use INDEX/MATCH or compute in Python
  ERROR  sheet name with spaces or symbols not quoted ( Sales Data!A1 )                              [auto-fixed]
  ERROR  reference to a sheet that doesn't exist                                                     -> #REF!
  WARN   link to another workbook ([1]Sheet!A1) - its cached value is the only copy of the data
  WARN   formula breaks the pattern of its neighbours in a row or column (classic copy-paste error)
  WARN   hard-coded number inside a formula (=B5*1.18) - move it to a labelled input cell
  INFO   division without a zero guard
Exit code: 1 if any ERROR remains (after --fix), else 0.
"""
import json
import re
import sys
from collections import defaultdict

from openpyxl import load_workbook
from openpyxl.formula import Tokenizer
from openpyxl.utils import column_index_from_string, get_column_letter

# Functions Excel stores with the _xlfn. prefix (added after Excel 2007). Written bare by a library, they fail.
XLFN = {
    "CONCAT", "TEXTJOIN", "IFS", "SWITCH", "MAXIFS", "MINIFS", "IFNA", "XOR", "DAYS", "ISOWEEKNUM",
    "STDEV.S", "STDEV.P", "VAR.S", "VAR.P", "PERCENTILE.INC", "PERCENTILE.EXC", "QUARTILE.INC", "QUARTILE.EXC",
    "MEDIAN.S", "MODE.SNGL", "MODE.MULT", "RANK.EQ", "RANK.AVG", "NORM.DIST", "NORM.INV", "NORM.S.DIST",
    "NORM.S.INV", "T.DIST", "T.INV", "T.TEST", "CHISQ.TEST", "F.TEST", "COVARIANCE.P", "COVARIANCE.S",
    "CEILING.MATH", "FLOOR.MATH", "CEILING.PRECISE", "FLOOR.PRECISE", "AGGREGATE", "NETWORKDAYS.INTL",
    "WORKDAY.INTL", "FORECAST.LINEAR", "FORECAST.ETS", "SHEET", "SHEETS", "FORMULATEXT", "ISFORMULA",
    "NUMBERVALUE", "UNICHAR", "UNICODE", "ENCODEURL", "BITAND", "BITOR", "BITXOR", "ACOT", "ARABIC",
    "BASE", "DECIMAL", "COMBINA", "PERMUTATIONA", "GAMMA", "PDURATION", "RRI", "IMSEC", "DAYS360",
}
XLFN.discard("DAYS360")  # old function, no prefix
# Spill / dynamic-array era functions: unreliable when written by openpyxl, unsupported by many readers.
DYNAMIC = {"XLOOKUP", "XMATCH", "FILTER", "SORT", "SORTBY", "UNIQUE", "SEQUENCE", "RANDARRAY", "LET", "LAMBDA",
           "MAP", "REDUCE", "SCAN", "BYROW", "BYCOL", "MAKEARRAY", "TAKE", "DROP", "VSTACK", "HSTACK", "TOCOL",
           "TOROW", "WRAPROWS", "WRAPCOLS", "CHOOSECOLS", "CHOOSEROWS", "EXPAND", "TEXTSPLIT", "TEXTBEFORE",
           "TEXTAFTER", "ARRAYTOTEXT", "VALUETOTEXT", "IMAGE", "GROUPBY", "PIVOTBY"}
ALT = {"XLOOKUP": "INDEX(return_range, MATCH(key, lookup_range, 0))", "XMATCH": "MATCH(key, range, 0)",
       "FILTER": "filter in Python and write the rows", "SORT": "sort in Python before writing",
       "SORTBY": "sort in Python before writing", "UNIQUE": "de-duplicate in Python before writing",
       "SEQUENCE": "write the numbers or =ROW()-ROW($A$1)", "LET": "helper cells for the intermediate values",
       "TEXTSPLIT": "split in Python, or MID/FIND", "TEXTBEFORE": "LEFT(text, FIND(delim, text)-1)",
       "TEXTAFTER": "MID(text, FIND(delim, text)+1, 999)"}
COMMON_CONSTANTS = {0, 1, 2, 7, 10, 12, 24, 52, 60, 100, 365, 1000}
CELL_RE = re.compile(r"(\$?)([A-Z]{1,3})(\$?)(\d+)")


def func_tokens(formula):
    try:
        tok = Tokenizer(formula)
    except Exception:
        return []
    return [t for t in tok.items if t.type == "FUNC" and t.subtype == "OPEN"]


def relative_pattern(formula, row, col):
    """Formula with relative refs rewritten as offsets, so copied formulas compare equal."""
    def sub(m):
        cabs, c, rabs, r = m.groups()
        cc = column_index_from_string(c)
        rr = int(r)
        cs = f"C{cc}" if cabs else f"C[{cc - col}]"
        rs = f"R{rr}" if rabs else f"R[{rr - row}]"
        return rs + cs
    out = []
    try:
        for t in Tokenizer(formula).items:
            if t.type == "OPERAND" and t.subtype == "RANGE":
                out.append(CELL_RE.sub(sub, t.value))
            else:
                out.append(t.value)
    except Exception:
        return formula
    return "".join(out)


def lint(path, fix_out=None):
    wb = load_workbook(path)
    sheets = set(wb.sheetnames)
    needs_quote = {s for s in sheets if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.]*", s)}
    issues = []
    fixed = 0

    def add(sev, ws, cell, msg, formula):
        issues.append({"severity": sev, "cell": f"{ws.title}!{cell}", "message": msg, "formula": formula})

    for ws in wb.worksheets:
        grid = {}
        for row in ws.iter_rows():
            for c in row:
                if not (isinstance(c.value, str) and c.value.startswith("=")):
                    continue
                f = c.value
                new = f
                # 1. unquoted sheet names with spaces/symbols
                for s in sorted(needs_quote, key=len, reverse=True):
                    pat = re.compile(r"(?<!['\w])" + re.escape(s) + r"!")
                    if pat.search(new):
                        new = pat.sub(f"'{s.replace(chr(39), chr(39) * 2)}'!", new)
                        add("ERROR", ws, c.coordinate, f"sheet name {s!r} must be quoted", f)
                # 2. references to missing sheets
                for m in re.finditer(r"(?:'((?:[^']|'')+)'|([A-Za-z_][\w.]*))!", new):
                    name = (m.group(1) or m.group(2)).replace("''", "'")
                    if name.startswith("[") or re.match(r"^\[\d+\]", name):
                        continue
                    if name not in sheets and not re.search(r"\[\d+\]", m.group(0)):
                        add("ERROR", ws, c.coordinate, f"refers to missing sheet {name!r} (#REF!)", f)
                # 3. functions
                for t in func_tokens(new):
                    name = t.value[:-1].upper()
                    bare = name.replace("_XLFN.", "").replace("_XLWS.", "")
                    if bare in DYNAMIC:
                        add("ERROR", ws, c.coordinate,
                            f"{bare} is a dynamic-array function; use {ALT.get(bare, 'older functions or Python')}", f)
                    elif bare in XLFN and not name.startswith("_XLFN."):
                        new = re.sub(rf"(?<![\w.]){re.escape(bare)}\(", f"_xlfn.{bare}(", new, flags=re.I)
                        add("ERROR", ws, c.coordinate, f"{bare} needs the _xlfn. prefix when written by a library", f)
                # 4. external workbooks
                if re.search(r"\[\d+\]|'?\[[^\]]+\.xls[xmb]?\]", new):
                    add("WARN", ws, c.coordinate, "links to another workbook: keep its cached value; don't recalc over it", f)
                # 5. hard-coded numbers
                try:
                    nums = [t.value for t in Tokenizer(new).items if t.type == "OPERAND" and t.subtype == "NUMBER"]
                except Exception:
                    nums = []
                odd = [n for n in nums if float(n) not in COMMON_CONSTANTS]
                if odd:
                    add("WARN", ws, c.coordinate, f"hard-coded number(s) {odd[:3]}: put assumptions in labelled input cells", f)
                # 6. unguarded division by a cell
                if re.search(r"/\s*\$?[A-Z]{1,3}\$?\d+", new) and "IFERROR" not in new.upper() and "IF(" not in new.upper():
                    add("INFO", ws, c.coordinate, "division by a cell without a zero guard (IFERROR or IF)", f)
                if new != f:
                    fixed += 1
                    c.value = new
                grid[(c.row, c.column)] = relative_pattern(new, c.row, c.column)
        # 7. pattern breaks: a cell that differs from both neighbours, which agree with each other
        for (r, col), pat in grid.items():
            for dr, dc, axis in ((0, 1, "row"), (1, 0, "column")):
                a, b = grid.get((r - dr, col - dc)), grid.get((r + dr, col + dc))
                if a and b and a == b and pat != a:
                    cell = f"{get_column_letter(col)}{r}"
                    add("WARN", ws, cell, f"breaks the {axis} pattern of its neighbours (copy-paste error?)",
                        ws[cell].value)
    if fix_out:
        wb.save(fix_out)
    return issues, fixed


def main():
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    fix_out = a[a.index("--fix") + 1] if "--fix" in a else None
    issues, fixed = lint(a[0], fix_out)
    if "--json" in a:
        print(json.dumps({"issues": issues, "fixed": fixed}, indent=2, ensure_ascii=False))
    else:
        order = {"ERROR": 0, "WARN": 1, "INFO": 2}
        for i in sorted(issues, key=lambda x: (order[x["severity"]], x["cell"])):
            print(f"{i['severity']:5} {i['cell']:16} {i['message']}   [{i['formula'][:70]}]")
        counts = defaultdict(int)
        for i in issues:
            counts[i["severity"]] += 1
        print(f"{counts['ERROR']} error(s), {counts['WARN']} warning(s), {counts['INFO']} note(s)"
              + (f"; auto-fixed {fixed} formula(s) -> {fix_out}" if fix_out else ""))
    remaining = issues
    if fix_out:
        remaining, _ = lint(fix_out)
        left = [i for i in remaining if i["severity"] == "ERROR"]
        if not left:
            print("after fix: no errors left")
        else:
            print(f"after fix: {len(left)} error(s) need a different formula (see above)")
    sys.exit(1 if any(i["severity"] == "ERROR" for i in remaining) else 0)


if __name__ == "__main__":
    main()
