---
name: morning-brief
description: Use only when the user explicitly asks for their morning brief (or /morning-brief), or asks to set one up as a recurring weekday task. Gathers today's calendar, important unread messages, tasks and news into one short, scannable page.
license: MIT. Complete terms in LICENSE.txt
---

# Morning Brief

A one-screen summary of the user's day: what's scheduled, what needs a reply, what's due, and anything worth knowing. Fast to read, no fluff.

## 1. Gather (use whatever is connected; skip silently what isn't)

| Section | Source | What to pull |
|---|---|---|
| **Today** | Calendar | Today's events in local time: time, title, location/link, attendees count. Flag overlaps, back-to-backs, early starts, travel needs |
| **Needs you** | Email / Slack / chat | Unread or flagged from the last ~18 h that ask the user something, mention them, come from their manager or key people, or have deadlines |
| **Due** | Task tool (Asana, Todoist, Jira, Notion…) | Overdue + due today + due tomorrow |
| **Heads-up** | Calendar, email | Tomorrow's first meeting, upcoming deadlines this week, prep needed |
| **Weather** | Location | Today's high/low and rain chance — one line |
| **News** (optional) | Web search | 3–5 headlines on topics the user named (industry, city, interests) |

Use the user's timezone for every time. Never include message bodies verbatim beyond a short phrase.

## 2. Prioritize

- Put the single most important thing at the top ("Board deck due 11:00 — not yet sent").
- In **Needs you**, rank by: from key people → explicit question/deadline → age. Max 7 items; summarize the rest as a count.
- Drop newsletters, automated notifications and FYIs unless they contain a deadline.

## 3. Render

Put what you gathered into a `brief.json` (format in the script's header) and render it:

```bash
python3 scripts/render_brief.py brief.json brief.html --png brief.png
```

The page has: the date, a one-line headline written from the shape of the day (packed / steady / open, naming the clear stretch), a strip showing the day's meetings from 7 AM to 9 PM (overlaps in the warning colour, optional meetings pale), the agenda, then **Needs you** (numbered — in priority order), **Due**, **Tomorrow**, **Sorted since yesterday**, and any extra sections the user asked for. Empty sections disappear; with nothing pending it says "Nothing needs you this morning."

Writing the items:
- Title in your own words, ≤ 10 words ("Sign off the Q4 budget"), never a copied subject line.
- Detail: who, where, when, and what they need, plus why it matters today ("Priya asked in #finance at 9:12; she needs it before her noon call").
- Observe, don't command or scold: no "you need to…", no "you missed…", no filler ("You've got this!").
- Only https links are kept; every gathered string is escaped, so nothing from an email can inject code into the page.

Publish `brief.html` as a page (or attach it); in chat-only surfaces, paste a compact Markdown version instead.

## 3b. Check before delivering

Run the **page-preview** checker on `brief.html` (or look at `brief.png`) — phone and desktop, light and dark: nothing clipped, times aligned, warning colour used sparingly. Embed any web font as a base64 data URI or use system fonts — a page that tries to fetch fonts from the network can render with fallbacks or fail offline. Escape every gathered subject, name and snippet as plain text (never inject it as HTML).

Before an item goes in **Needs you**, open its thread once: if the user already replied or reacted, drop it or move it to a short "Sorted" list.

## 4. Make it recurring (if asked)

Create a scheduled task on weekdays shortly before the user's start time (ask the time and timezone if unknown; default 07:30 local). The task prompt must be standalone: "Run my morning brief: calendar today, unread important email/Slack since yesterday evening, tasks due/overdue, weather for <city>, headlines on <topics>. Render as a one-page HTML artifact." Confirm the schedule back to the user in one line.

## 5. Rules

- Read-only: never send, reply, accept invites or change tasks from the brief unless the user asks.
- If a source fails, include a one-line note ("Couldn't reach Gmail") rather than silently omitting it.
- Keep it under ~40 lines. If there's nothing in a section, drop the section.
