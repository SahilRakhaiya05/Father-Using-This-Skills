---
name: research-report
description: Use when a question needs research across many sources — comparing options, analyzing a market or industry, reviewing studies, tracing history or trends — and the answer should be a well-sourced narrative report rather than a quick fact.
license: MIT. Complete terms in LICENSE.txt
---

# Research Report

Turn an open question into a sourced, readable report. Quality comes from a good plan, varied sources, and honest synthesis — not from the number of searches.

## 1. Frame the question (before any search)

Write down, briefly:
- **The real question** and who it's for (decision? learning? publication?).
- **Scope:** time period, geography, what's in and out.
- **Sub-questions** (3–7) that together answer it.
- **What a good answer looks like:** a recommendation, a comparison table, a timeline, numbers?

If scope is genuinely unclear and wrong guesses would waste a lot of work, ask **one** short clarifying question. Otherwise state your assumptions and proceed.

## 2. Plan searches per sub-question

For each sub-question, plan 2–4 distinct queries from different angles:
- Primary sources: official sites, government data, company filings, standards bodies, original papers.
- Independent analysis: reputable journalism, academic reviews, industry reports.
- Counter-evidence: search explicitly for criticism, failures, "problems with X", "X vs Y".
- Recency: add the current year for fast-moving topics; check the date on every source.

Keep queries short (2–6 words). Don't repeat near-identical queries — change the angle.

## 2b. Big questions: research in parallel (if you can start helper agents)

Split the question into independent, non-overlapping slices — by sub-question, by entity (each company, each country), or by viewpoint (supporters, critics, data). Rough guide: 1 helper for a single fact, 3 for a focused topic, 4–6 for comparisons or many entities.

- Make a folder per request: `research/<short title>/notes/` and `research/<short title>/report.md`. Use a new title for every new request so earlier notes are never overwritten.
- Start all helpers **at the same time**, each with: the exact slice, key questions, preferred source types, the user's constraints (dates, region, budget), the absolute path of its notes file, and the instruction to first read `references/researcher-brief.md` (give its absolute path).
- Allow at most **one** extra round for a critical gap — every round delays the answer.
- Then have one writer (you or a single helper, told to read `references/report-writer-brief.md` first) read all notes and write the report (section 5). Read the finished report yourself before delivering.
- Coordinating keeps your own context clean: you plan, brief, check gaps and deliver; the helpers search and read.
- A follow-up on the same topic gets a new title that says what it adds ("EU AI Act startup penalties"), and the writer is pointed at the earlier report to build on.

Without helper agents, do the same slices yourself one after another.

## 3. Gather and log

Keep a running source log (in a scratch file) as you read:

```
[S1] Title — Publisher — date — URL
     Key facts: … (with numbers, exact)
     Reliability: primary / secondary / opinion; any bias
```

- Open the full page for important sources; snippets mislead.
- Capture exact figures with units and dates.
- When sources conflict, log both and note why they might differ (date, definition, methodology).
- Stop a sub-question when new sources only repeat what you have.

## 4. Synthesize

Before writing, answer for yourself:
- What's the bottom line in 2–3 sentences?
- Which findings are well-supported (multiple independent sources) vs. single-source vs. contested?
- What surprised you? What's missing from the evidence?

## 5. Write the report

Structure:

1. **Title**
2. **Bottom line** — the answer in 3–5 sentences, up front.
3. **Key findings** — 4–8 findings, each a clear claim with its evidence and citation [S3].
4. **Detail sections** — one per sub-question, prose first; tables for comparisons; a timeline for history.
5. **Disagreements and uncertainty** — where evidence conflicts or is thin.
6. **Recommendation / implications** — only if the user is making a decision.
7. **Sources** — numbered list: title, publisher, date, link.

Writing rules:
- Every factual claim traceable to a source; numbers always cited.
- Paraphrase; quote only short phrases where exact wording matters.
- Distinguish fact, estimate and opinion ("the company says…", "analysts estimate…").
- Prefer specific over vague: "fell 18% between 2023 and 2025 [S4]", not "declined significantly".
- Plain language, short paragraphs, no filler.

## 6. Check before delivering

- [ ] Every sub-question answered (or explicitly marked as unanswerable with why)
- [ ] Each number matches its source (re-open and verify the important ones)
- [ ] Source dates are current enough for the topic
- [ ] Counter-evidence considered, not just supporting evidence
- [ ] The bottom line actually follows from the findings

## Output format

Default to a document the user can keep and share. A short question answered by research can stay in the chat with a Sources list at the end.
