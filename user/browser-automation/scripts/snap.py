#!/usr/bin/env python3
"""Screenshot a page at desktop + mobile widths and dump its readable text.

Usage: snap.py URL_OR_FILE [OUTPREFIX] [--full]
Writes OUTPREFIX-desktop.png, OUTPREFIX-mobile.png, OUTPREFIX.txt and prints console errors.
"""
import os
import sys
from playwright.sync_api import sync_playwright


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit(__doc__)
    url = args[0]
    if os.path.exists(url):
        url = "file://" + os.path.abspath(url)
    out = args[1] if len(args) > 1 else "snap"
    full = "--full" in sys.argv
    errors = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        for name, vp in (("desktop", {"width": 1280, "height": 800}), ("mobile", {"width": 375, "height": 812})):
            ctx = b.new_context(viewport=vp, device_scale_factor=1 if name == "desktop" else 2)
            page = ctx.new_page()
            page.on("console", lambda m: m.type == "error" and errors.append(m.text))
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(url, wait_until="domcontentloaded", timeout=45000)
            try:
                page.wait_for_load_state("networkidle", timeout=8000)
            except Exception:
                pass
            page.screenshot(path=f"{out}-{name}.png", full_page=full)
            if name == "desktop":
                title = page.title()
                body = page.locator("body").inner_text()
                with open(f"{out}.txt", "w") as f:
                    f.write(f"{title}\n{url}\n\n{body}")
                overflow = page.evaluate("document.documentElement.scrollWidth > window.innerWidth")
            else:
                m_overflow = page.evaluate("document.documentElement.scrollWidth > window.innerWidth")
            ctx.close()
        b.close()
    print(f"title: {title}")
    print(f"wrote {out}-desktop.png, {out}-mobile.png, {out}.txt ({len(body)} chars)")
    print(f"horizontal overflow: desktop={overflow} mobile={m_overflow}")
    print(f"console errors: {len(set(errors))}")
    for e in sorted(set(errors))[:20]:
        print("  ", e[:200])


if __name__ == "__main__":
    main()
