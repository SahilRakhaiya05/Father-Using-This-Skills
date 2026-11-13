#!/usr/bin/env python3
"""Build the Father Using This Skills banner and logo.

  python docs/make_banner.py

Writes docs/banner-light.svg, docs/banner-dark.svg, docs/logo.svg and PNG copies
(2x) of each. The PNGs are what the README shows, so the banner looks the same
on every computer. Needs: pip install playwright && python -m playwright install chromium
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
W, H = 1280, 360
FONT = "'Segoe UI', 'Helvetica Neue', Helvetica, Arial, sans-serif"
MONO = "'Cascadia Mono', Consolas, 'SF Mono', Menlo, monospace"

THEMES = {
    "light": {"bg": "#f6f3ec", "ink": "#16130f", "muted": "#6f685c", "rule": "#d9d3c6", "tile": "#16130f", "mark": "#f6f3ec", "accent": "#e2512a"},
    "dark": {"bg": "#12110f", "ink": "#f4f0e8", "muted": "#9a9388", "rule": "#2e2b27", "tile": "#f4f0e8", "mark": "#12110f", "accent": "#ff6a3d"},
}

MOUSTACHE = ("M0 -6C14 -22 44 -20 62 -2C70 6 80 8 88 2C82 22 56 28 34 18C20 12 8 8 0 12"
             "C-8 8 -20 12 -34 18C-56 28 -82 22 -88 2C-80 8 -70 6 -62 -2C-44 -20 -14 -22 0 -6Z")


def mark(size, tile, fg, accent):
    """The logo: round glasses and a moustache on a rounded tile. Drawn on a 200-unit grid."""
    k = size / 200
    return f"""<g transform="scale({k:.4f})">
    <rect width="200" height="200" rx="46" fill="{tile}"/>
    <g fill="none" stroke="{fg}" stroke-width="11" stroke-linecap="round">
      <circle cx="58" cy="88" r="30"/><circle cx="142" cy="88" r="30"/>
      <path d="M88 84q12 -11 24 0"/>
    </g>
    <path transform="translate(100 150) scale(0.74)" d="{MOUSTACHE}" fill="{fg}"/>
    <circle cx="166" cy="34" r="8" fill="{accent}"/>
  </g>"""


def banner(t):
    tile = 156
    x0, y0 = 232, (H - tile) // 2
    tx = x0 + tile + 44
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="Father Using This Skills">
  <rect width="{W}" height="{H}" fill="{t['bg']}"/>
  <g transform="translate({x0} {y0})">{mark(tile, t['tile'], t['mark'], t['accent'])}</g>
  <text x="{tx - 3}" y="{y0 + 70}" font-family="{FONT}" font-size="66" font-weight="700" letter-spacing="-2.4" fill="{t['ink']}">Father Using This Skills</text>
  <text x="{tx}" y="{y0 + 114}" font-family="{FONT}" font-size="25" fill="{t['muted']}">Skills that teach your AI to do real work.</text>
  <text x="{tx}" y="{y0 + 148}" font-family="{MONO}" font-size="15" letter-spacing="0.4" fill="{t['muted']}"><tspan fill="{t['accent']}">19 skills</tspan>  ·  SKILL.md  ·  MIT</text>
</svg>
"""


def logo(t):
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" width="200" height="200" role="img" aria-label="Father Using This Skills logo">
  {mark(200, t['tile'], t['mark'], t['accent'])}
</svg>
"""


def main():
    files = {f"banner-{name}.svg": (banner(t), W, H) for name, t in THEMES.items()}
    files["logo.svg"] = (logo(THEMES["light"]), 200, 200)
    for name, (svg, _, _) in files.items():
        (HERE / name).write_bytes(svg.encode("utf-8"))
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for name, (_, w, h) in files.items():
            page = browser.new_page(viewport={"width": w, "height": h}, device_scale_factor=2)
            page.goto((HERE / name).as_uri())
            page.screenshot(path=str(HERE / name.replace(".svg", ".png")), omit_background=name == "logo.svg")
            page.close()
        browser.close()
    print("wrote", ", ".join(sorted(files)), "and PNG copies")


if __name__ == "__main__":
    main()
