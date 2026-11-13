"""Measure text with real font metrics so layouts and QA know whether text fits its box.

Office fonts are measured with their metric-compatible open twins when the originals aren't installed
(Calibri→Carlito, Cambria→Caladea, Arial→Liberation Sans, Times New Roman→Liberation Serif,
Courier New→Liberation Mono), which have identical character widths.
"""
import functools
import subprocess

from PIL import ImageFont

TWINS = {"calibri": "Carlito", "cambria": "Caladea", "arial": "Liberation Sans", "helvetica": "Liberation Sans",
         "times new roman": "Liberation Serif", "courier new": "Liberation Mono"}
# Fonts whose stand-ins here have different widths: fit checks on them are approximate.
UNRELIABLE = {"georgia", "trebuchet ms", "impact", "arial black", "garamond", "consolas", "palatino linotype",
              "calibri light", "aptos", "segoe ui", "verdana", "tahoma", "century gothic", "gill sans"}
SAFE = ["Calibri", "Arial", "Cambria", "Times New Roman", "Courier New"]


@functools.lru_cache(maxsize=64)
def font_file(name, bold=False):
    fam = TWINS.get(name.lower(), name)
    pat = f"{fam}:style={'Bold' if bold else 'Regular'}"
    try:
        out = subprocess.run(["fc-match", "-f", "%{file}", pat], capture_output=True, text=True, timeout=10).stdout
        return out.strip() or None
    except Exception:
        return None


@functools.lru_cache(maxsize=512)
def _font(name, size_pt, bold):
    f = font_file(name, bold)
    try:
        return ImageFont.truetype(f, max(1, int(round(size_pt * 10))))   # 10 px per pt for precision
    except Exception:
        return ImageFont.load_default()


def width_in(text, name="Calibri", size_pt=18, bold=False):
    """Rendered width of one line, in inches."""
    if not text:
        return 0.0
    f = _font(name, size_pt, bold)
    return f.getlength(text) / 10 / 72


def wrap_lines(text, box_w_in, name="Calibri", size_pt=18, bold=False):
    """Greedy word wrap like PowerPoint's; returns the list of lines."""
    lines = []
    for para in str(text).split("\n"):
        cur = ""
        for word in para.split(" "):
            trial = f"{cur} {word}" if cur else word
            if width_in(trial, name, size_pt, bold) <= box_w_in or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        lines.append(cur)
    return lines


def height_in(text, box_w_in, name="Calibri", size_pt=18, bold=False, spacing=1.2, space_after_pt=0):
    lines = wrap_lines(text, box_w_in, name, size_pt, bold)
    paras = str(text).count("\n") + 1
    return (len(lines) * size_pt * spacing + paras * space_after_pt) / 72


def fit_size(paragraphs, box_w_in, box_h_in, name, start_pt, min_pt, bold=False, spacing=1.2, space_after_ratio=0.0):
    """Largest size <= start_pt at which all paragraphs fit the box (never below min_pt)."""
    size = start_pt
    while size > min_pt:
        h = sum(height_in(p, box_w_in, name, size, bold, spacing, size * space_after_ratio) for p in paragraphs)
        if h <= box_h_in:
            break
        size -= 1
    return size
