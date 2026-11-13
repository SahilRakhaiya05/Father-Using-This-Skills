#!/usr/bin/env python3
"""Render a page at phone/tablet/desktop sizes and report visual + technical problems.

Usage:
  preview_check.py TARGET [--out DIR] [--dark] [--full] [--size WxH ...] [--pdf]
                   [--click SELECTOR ...] [--type SELECTOR=TEXT ...] [--wait MS]

TARGET: an .html file, a folder containing index.html, or an http(s) URL.
Writes DIR/<size>[-dark].png screenshots and DIR/preview_report.json; prints a summary.
Exit code 0 = no errors (warnings allowed), 1 = errors found.
"""
import json
import os
import sys

from playwright.sync_api import sync_playwright

DEFAULT_SIZES = [("phone", 375, 812), ("tablet", 768, 1024), ("desktop", 1280, 800)]

AUDIT_JS = r"""
() => {
  const out = {overflow: [], tinyText: [], lowContrast: [], clipped: [], brokenImages: [], noAlt: 0, overlaps: []};
  const vw = document.documentElement.clientWidth;
  out.pageWidth = document.documentElement.scrollWidth;
  out.viewport = vw;
  const desc = el => {
    let s = el.tagName.toLowerCase();
    if (el.id) s += '#' + el.id;
    if (el.classList && el.classList.length) s += '.' + [...el.classList].slice(0, 2).join('.');
    return s;
  };
  const visible = el => {
    const st = getComputedStyle(el);
    if (st.display === 'none' || st.visibility === 'hidden' || +st.opacity === 0) return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };
  const parseRGB = c => { const m = c.match(/rgba?\(([^)]+)\)/); if (!m) return null;
    const p = m[1].split(/[ ,\/]+/).filter(Boolean).map(Number); return {r:p[0], g:p[1], b:p[2], a: p.length > 3 ? p[3] : 1}; };
  const lum = ({r,g,b}) => { const f = v => { v /= 255; return v <= 0.03928 ? v/12.92 : Math.pow((v+0.055)/1.055, 2.4); };
    return 0.2126*f(r) + 0.7152*f(g) + 0.0722*f(b); };
  const bgOf = el => { let e = el; while (e) { const c = parseRGB(getComputedStyle(e).backgroundColor);
      if (c && c.a > 0.5) return c; e = e.parentElement; } return {r:255, g:255, b:255, a:1}; };
  const all = [...document.body.querySelectorAll('*')];
  for (const el of all) {
    if (!visible(el)) continue;
    const r = el.getBoundingClientRect();
    if (r.right > vw + 1 && getComputedStyle(el).position !== 'fixed') {
      // report the outermost offenders only
      if (!el.parentElement || el.parentElement.getBoundingClientRect().right <= vw + 1)
        out.overflow.push({el: desc(el), right: Math.round(r.right)});
    }
    const hasText = [...el.childNodes].some(n => n.nodeType === 3 && n.textContent.trim().length > 1);
    if (hasText) {
      const st = getComputedStyle(el);
      const fs = parseFloat(st.fontSize);
      if (fs < 12) out.tinyText.push({el: desc(el), px: fs, text: el.textContent.trim().slice(0, 40)});
      const fg = parseRGB(st.color);
      if (fg) { const bg = bgOf(el); const L1 = lum(fg), L2 = lum(bg);
        const ratio = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
        const large = fs >= 24 || (fs >= 18.66 && +st.fontWeight >= 700);
        if (ratio < (large ? 3 : 4.5)) out.lowContrast.push({el: desc(el), ratio: +ratio.toFixed(2), text: el.textContent.trim().slice(0, 40)}); }
      if ((st.overflow === 'hidden' || st.textOverflow === 'ellipsis') && (el.scrollWidth > el.clientWidth + 2 || el.scrollHeight > el.clientHeight + 2))
        out.clipped.push({el: desc(el), text: el.textContent.trim().slice(0, 40)});
    }
  }
  for (const img of document.images) {
    if (img.complete && img.naturalWidth === 0 && visible(img)) out.brokenImages.push(img.getAttribute('src'));
    if (!img.hasAttribute('alt')) out.noAlt++;
  }
  const inter = [...document.querySelectorAll('a,button,input,select,textarea,[role=button]')].filter(visible);
  for (let i = 0; i < inter.length; i++) for (let j = i + 1; j < inter.length; j++) {
    if (inter[i].contains(inter[j]) || inter[j].contains(inter[i])) continue;
    const a = inter[i].getBoundingClientRect(), b = inter[j].getBoundingClientRect();
    const ox = Math.min(a.right, b.right) - Math.max(a.left, b.left), oy = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
    if (ox > 4 && oy > 4) out.overlaps.push([desc(inter[i]), desc(inter[j])]);
  }
  out.title = document.title;
  for (const k of ['overflow','tinyText','lowContrast','clipped','overlaps']) out[k] = out[k].slice(0, 15);
  return out;
}
"""


def parse_args(a):
    o = {"out": "preview", "dark": False, "full": False, "sizes": [], "pdf": False, "click": [], "type": [], "wait": 400}
    i = 0
    target = None
    while i < len(a):
        x = a[i]
        if x == "--out":
            o["out"] = a[i + 1]; i += 2
        elif x == "--size":
            w, h = a[i + 1].lower().split("x"); o["sizes"].append((a[i + 1], int(w), int(h))); i += 2
        elif x == "--click":
            o["click"].append(a[i + 1]); i += 2
        elif x == "--type":
            sel, txt = a[i + 1].split("=", 1); o["type"].append((sel, txt)); i += 2
        elif x == "--wait":
            o["wait"] = int(a[i + 1]); i += 2
        elif x in ("--dark", "--full", "--pdf"):
            o[x[2:]] = True; i += 1
        else:
            target = x; i += 1
    if not target:
        sys.exit(__doc__)
    if os.path.isdir(target):
        target = os.path.join(target, "index.html")
    if os.path.exists(target):
        target = "file://" + os.path.abspath(target)
    o["target"] = target
    o["sizes"] = o["sizes"] or DEFAULT_SIZES
    return o


def main():
    o = parse_args(sys.argv[1:])
    os.makedirs(o["out"], exist_ok=True)
    schemes = ["light", "dark"] if o["dark"] else ["light"]
    report = {"target": o["target"], "runs": []}
    errors = warnings = 0
    with sync_playwright() as p:
        browser = p.chromium.launch()
        for scheme in schemes:
            for name, w, h in o["sizes"]:
                ctx = browser.new_context(viewport={"width": w, "height": h}, color_scheme=scheme,
                                          device_scale_factor=1)
                page = ctx.new_page()
                console, failed = [], []
                page.on("console", lambda m: m.type == "error" and console.append(m.text[:300]))
                page.on("pageerror", lambda e: console.append(f"uncaught: {str(e)[:300]}"))
                page.on("requestfailed", lambda r: failed.append(f"{r.url[:150]} ({r.failure})"))
                page.on("response", lambda r: r.status >= 400 and failed.append(f"{r.url[:150]} (HTTP {r.status})"))
                try:
                    page.goto(o["target"], wait_until="load", timeout=45000)
                    try:
                        page.wait_for_load_state("networkidle", timeout=6000)
                    except Exception:
                        pass
                    for sel in o["click"]:
                        page.click(sel, timeout=5000)
                    for sel, txt in o["type"]:
                        page.fill(sel, txt, timeout=5000)
                    page.wait_for_timeout(o["wait"])
                    audit = page.evaluate(AUDIT_JS)
                except Exception as e:
                    audit = {"fatal": str(e)[:300]}
                tag = f"{name}{'-dark' if scheme == 'dark' else ''}"
                shot = os.path.join(o["out"], f"{tag}.png")
                try:
                    page.screenshot(path=shot, full_page=o["full"])
                except Exception:
                    shot = None
                if o["pdf"] and scheme == "light" and name == o["sizes"][-1][0]:
                    try:
                        page.pdf(path=os.path.join(o["out"], "page.pdf"), print_background=True)
                    except Exception:
                        pass
                run = {"size": tag, "viewport": [w, h], "screenshot": shot, "console_errors": sorted(set(console)),
                       "failed_requests": sorted(set(failed)), **audit}
                report["runs"].append(run)
                e = len(run["console_errors"]) + len(run.get("brokenImages", [])) + (1 if "fatal" in run else 0)
                overflowed = run.get("pageWidth", 0) > (run.get("viewport") or w) + 1
                e += 1 if overflowed else 0
                wn = (len(run["failed_requests"]) + len(run.get("tinyText", [])) + len(run.get("lowContrast", [])) +
                      len(run.get("clipped", [])) + len(run.get("overlaps", [])) + (1 if not run.get("title") else 0))
                errors += e
                warnings += wn
                status = "ERROR" if e else ("warn" if wn else "ok")
                ov = f"overflow {run.get('pageWidth')}px>{run.get('viewport')}px" if run.get("pageWidth", 0) > (run.get("viewport") or w) + 1 else "no overflow"
                print(f"[{status:5}] {tag:14} {ov}; console {len(run['console_errors'])}; failed req {len(run['failed_requests'])}; "
                      f"broken img {len(run.get('brokenImages', []))}; tiny text {len(run.get('tinyText', []))}; "
                      f"low contrast {len(run.get('lowContrast', []))}; clipped {len(run.get('clipped', []))}; "
                      f"overlaps {len(run.get('overlaps', []))}")
                ctx.close()
        browser.close()
    rp = os.path.join(o["out"], "preview_report.json")
    with open(rp, "w") as f:
        json.dump(report, f, indent=2)
    first = report["runs"][0]
    if first.get("console_errors"):
        print("console:", *first["console_errors"][:5], sep="\n  ")
    if first.get("overflow"):
        print("overflowing elements (phone):", first["overflow"][:5])
    print(f"{'FAILED' if errors else 'OK'}: {errors} error(s), {warnings} warning(s) -> {rp}")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
