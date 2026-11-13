#!/usr/bin/env python3
"""Render a morning brief from JSON into one self-contained HTML page (no network, light + dark, phone-friendly).

Usage: render_brief.py BRIEF.json OUT.html [--png OUT.png]

BRIEF.json:
{
  "name": "Asha", "date": "2026-11-06", "timezone": "Asia/Kolkata", "language": "en",
  "headline": "optional — otherwise written from the shape of the day",
  "events":   [{"start": "09:30", "end": "10:00", "title": "Standup", "where": "Meet", "optional": false,
                "link": "https://..."}],
  "needs_you": [{"title": "Sign off Q4 budget", "detail": "Priya asked in #finance at 9:12; she needs it by noon.",
                 "source": "#finance", "link": "https://..."}],
  "due":      [{"title": "Expense report", "detail": "overdue by 2 days", "link": "..."}],
  "sorted":   [{"title": "Venue confirmed", "detail": "Rohan booked it yesterday evening."}],
  "tomorrow": [{"title": "8:00 flight to Delhi", "detail": "web check-in opens today 08:00"}],
  "weather":  "29° / 21° · 10% rain",
  "sections": [{"title": "Headlines", "items": [{"title": "...", "detail": "...", "link": "..."}]}]
}
Every gathered string is HTML-escaped; only https links are kept.
"""
import datetime as dt
import html
import json
import sys

DAY_START, DAY_END = 7 * 60, 21 * 60          # strip covers 07:00–21:00, widened if events fall outside


def mins(hhmm):
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def fmt(m):
    h, mm = divmod(m, 60)
    suffix = "AM" if h < 12 else "PM"
    h12 = h % 12 or 12
    return f"{h12}:{mm:02d} {suffix}" if mm else f"{h12} {suffix}"


def esc(s):
    return html.escape(str(s or ""), quote=True)


def safe_link(u):
    u = str(u or "")
    return u if u.startswith("https://") else ""


def classify(events):
    busy = [(mins(e["start"]), mins(e["end"])) for e in events if not e.get("optional")]
    total = sum(b - a for a, b in busy)
    busy.sort()
    run, longest, prev_end = 0, 0, None
    for a, b in busy:
        run = run + 1 if prev_end is not None and a - prev_end <= 10 else 1
        longest = max(longest, run)
        prev_end = b
    if total >= 300 or longest >= 3:
        return "heavy", total, busy
    if len(busy) <= 1 and total <= 60:
        return "open", total, busy
    return "normal", total, busy


def free_blocks(busy, lo, hi, minimum=60):
    out, cur = [], lo
    for a, b in sorted(busy):
        if a - cur >= minimum:
            out.append((cur, a))
        cur = max(cur, b)
    if hi - cur >= minimum:
        out.append((cur, hi))
    return out


def headline(brief, kind, busy, lo, hi):
    if brief.get("headline"):
        return brief["headline"]
    name = brief.get("name", "")
    free = free_blocks(busy, max(lo, 9 * 60), min(hi, 18 * 60))
    longest = max(free, key=lambda f: f[1] - f[0]) if free else None
    if kind == "open":
        return f"A wide-open day{', ' + name if name else ''} — room for the work that's been waiting."
    if kind == "heavy":
        if longest and longest[1] - longest[0] >= 90:
            return f"Meetings stack up{', ' + name if name else ''}; your clear stretch is {fmt(longest[0])}–{fmt(longest[1])}."
        last = max(b for _, b in busy)
        return f"A packed day{', ' + name if name else ''} — it eases after {fmt(last)}."
    if longest:
        return f"A steady day{', ' + name if name else ''}, with {fmt(longest[0])}–{fmt(longest[1])} to yourself."
    return f"Here's your day{', ' + name if name else ''}."


def overlaps(events):
    ev = sorted([(mins(e["start"]), mins(e["end"]), i) for i, e in enumerate(events)])
    clash = set()
    for i in range(len(ev)):
        for j in range(i + 1, len(ev)):
            if ev[j][0] < ev[i][1]:
                clash.update({ev[i][2], ev[j][2]})
    return clash


def item_list(items, numbered=False):
    if not items:
        return ""
    out = []
    for i, it in enumerate(items, 1):
        link = safe_link(it.get("link"))
        title = esc(it.get("title"))
        title_html = f'<a href="{esc(link)}" target="_blank" rel="noopener">{title}</a>' if link else title
        num = f'<span class="num">{i}</span>' if numbered else ""
        detail = f"<p>{esc(it['detail'])}</p>" if it.get("detail") else ""
        out.append(f'<li>{num}<div><div class="it">{title_html}</div>{detail}</div></li>')
    return f'<ol class="items{" numbered" if numbered else ""}">' + "".join(out) + "</ol>"


def render(brief):
    events = brief.get("events", [])
    kind, total, busy = classify(events)
    lo = min([DAY_START] + [mins(e["start"]) // 60 * 60 for e in events])
    hi = max([DAY_END] + [-(-mins(e["end"]) // 60) * 60 for e in events])
    span = hi - lo
    clash = overlaps(events)
    date = dt.date.fromisoformat(brief["date"]) if brief.get("date") else dt.date.today()
    day_line = date.strftime("%A · %-d %B %Y")
    # timeline strip
    blocks = []
    for i, e in enumerate(events):
        a, b = mins(e["start"]), mins(e["end"])
        left, width = (a - lo) / span * 100, max((b - a) / span * 100, 0.8)
        cls = "ev" + (" opt" if e.get("optional") else "") + (" clash" if i in clash else "")
        blocks.append(f'<div class="{cls}" style="left:{left:.2f}%;width:{width:.2f}%" '
                      f'title="{esc(fmt(a))}–{esc(fmt(b))} {esc(e.get("title"))}"></div>')
    ticks = "".join(f'<span style="left:{(h * 60 - lo) / span * 100:.2f}%">{fmt(h * 60).replace(":00", "")}</span>'
                    for h in range(lo // 60, hi // 60 + 1, 2))
    agenda = []
    for i, e in sorted(enumerate(events), key=lambda x: mins(x[1]["start"])):
        a, b = mins(e["start"]), mins(e["end"])
        link = safe_link(e.get("link"))
        t = esc(e.get("title"))
        t = f'<a href="{esc(link)}" target="_blank" rel="noopener">{t}</a>' if link else t
        tags = (' <span class="tag">optional</span>' if e.get("optional") else "") + \
               (' <span class="tag warn">overlaps</span>' if i in clash else "")
        where = f'<span class="where">{esc(e.get("where"))}</span>' if e.get("where") else ""
        agenda.append(f'<li><span class="when">{fmt(a)}–{fmt(b)}</span><span class="what">{t}{tags}{where}</span></li>')
    free = free_blocks(busy, max(lo, 9 * 60), min(hi, 18 * 60))
    free_txt = ", ".join(f"{fmt(a)}–{fmt(b)}" for a, b in free) or "none longer than an hour"
    hours = f"{total // 60}h {total % 60:02d}m" if total >= 60 else f"{total}m"
    summary = f"{len(busy)} meeting{'s' if len(busy) != 1 else ''} · {hours} booked · free: {free_txt}"
    sections_html = []
    for title, key, numbered in (("Needs you", "needs_you", True), ("Due", "due", False),
                                 ("Tomorrow", "tomorrow", False), ("Sorted since yesterday", "sorted", False)):
        if brief.get(key):
            sections_html.append(f'<section><h2>{title}</h2>{item_list(brief[key], numbered)}</section>')
    if not brief.get("needs_you") and not brief.get("due"):
        sections_html.insert(0, '<section><p class="calm">Nothing needs you this morning.</p></section>')
    for sec in brief.get("sections", []):
        if sec.get("items"):
            sections_html.append(f'<section><h2>{esc(sec.get("title"))}</h2>{item_list(sec["items"])}</section>')
    weather = f'<div class="weather">{esc(brief["weather"])}</div>' if brief.get("weather") else ""
    lang = esc(brief.get("language", "en"))
    rtl = ' dir="rtl"' if brief.get("language", "en")[:2] in ("ar", "he", "fa", "ur") else ""
    return f"""<!doctype html><html lang="{lang}"{rtl}><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Morning brief · {esc(day_line)}</title>
<style>
:root{{--bg:#fbfbfa;--wash:#f3f4f1;--fg:#22251f;--soft:#575c52;--faint:#a7ab9f;--line:#e2e4dc;--ev:#3f5a46;--opt:#c7ccc0;--warn:#a84a28;--free:#dfe9dc}}
@media (prefers-color-scheme:dark){{:root{{--bg:#151714;--wash:#1c1f1a;--fg:#e8eae3;--soft:#a9ae9f;--faint:#6d7266;--line:#2c3029;--ev:#8fb79a;--opt:#4a5046;--warn:#e7895f;--free:#22301f}}}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 -apple-system,"Segoe UI",Roboto,"Noto Sans","Noto Sans Devanagari",sans-serif}}
.band{{padding:28px max(16px,env(safe-area-inset-left)) 22px;background:var(--wash);border-bottom:1px solid var(--line)}}
.wrap{{max-width:820px;margin:0 auto}}
.date{{color:var(--soft);font-size:14px;letter-spacing:.02em}}
h1{{font:600 clamp(24px,4.6vw,34px)/1.2 Georgia,"Times New Roman",serif;margin:6px 0 18px;text-wrap:balance}}
.strip{{position:relative;height:34px;border-radius:6px;background:var(--free);overflow:hidden}}
.ev{{position:absolute;top:0;bottom:0;background:var(--ev);border-right:1px solid var(--wash)}}
.ev.opt{{background:var(--opt)}} .ev.clash{{background:var(--warn)}}
.ticks{{position:relative;height:20px;margin-top:4px;font-size:12px;color:var(--soft)}}
.ticks span{{position:absolute;transform:translateX(-50%);white-space:nowrap}}
.ticks span:first-child{{transform:none}} .ticks span:last-child{{transform:translateX(-100%)}}
.summary{{margin:12px 0 0;color:var(--soft);font-size:14px}}
.weather{{float:right;color:var(--soft);font-size:14px}}
.agenda{{list-style:none;margin:16px 0 0;padding:0}}
.agenda li{{display:flex;gap:14px;padding:7px 0;border-top:1px solid var(--line)}}
.when{{flex:0 0 9.5em;color:var(--soft);font-variant-numeric:tabular-nums}}
.what{{min-width:0}} .where{{display:block;color:var(--soft);font-size:14px}}
.tag{{font-size:12px;color:var(--soft);border:1px solid var(--line);border-radius:4px;padding:0 5px;margin-left:6px}}
.tag.warn{{color:var(--warn);border-color:var(--warn)}}
main{{padding:8px max(16px,env(safe-area-inset-left)) 40px}}
section{{margin-top:22px}}
h2{{font-size:13px;letter-spacing:.08em;text-transform:uppercase;color:var(--soft);margin:0 0 8px;font-weight:600}}
.items{{list-style:none;margin:0;padding:0}}
.items li{{display:flex;gap:12px;padding:10px 0;border-top:1px solid var(--line)}}
.num{{color:var(--soft);font-variant-numeric:tabular-nums;min-width:1.2em}}
.it{{font-weight:600}} .it a{{color:inherit;text-decoration-color:var(--faint)}}
.items p{{margin:2px 0 0;color:var(--soft)}}
.calm{{color:var(--soft);font-style:italic}}
a{{color:inherit}}
@media (max-width:560px){{.when{{flex-basis:7.6em;font-size:14px}} .weather{{float:none;display:block;margin-bottom:6px}}}}
</style></head><body>
<div class="band"><div class="wrap">{weather}<div class="date">{esc(day_line)}</div>
<h1>{esc(headline(brief, kind, busy, lo, hi))}</h1>
<div class="strip" role="img" aria-label="{esc(summary)}">{''.join(blocks)}</div><div class="ticks">{ticks}</div>
<p class="summary">{esc(summary)}</p>
<ul class="agenda">{''.join(agenda) or '<li><span class="what">No meetings today.</span></li>'}</ul>
</div></div>
<main><div class="wrap">{''.join(sections_html)}</div></main>
</body></html>"""


def main():
    a = sys.argv[1:]
    if len(a) < 2:
        sys.exit(__doc__)
    brief = json.load(open(a[0], encoding="utf-8"))
    page = render(brief)
    open(a[1], "w", encoding="utf-8").write(page)
    print(f"wrote {a[1]}")
    if "--png" in a:
        png = a[a.index("--png") + 1]
        import os
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page(viewport={"width": 900, "height": 1200})
            pg.goto("file://" + os.path.abspath(a[1]))
            pg.screenshot(path=png, full_page=True)
            b.close()
        print(f"screenshot {png}")


if __name__ == "__main__":
    main()
