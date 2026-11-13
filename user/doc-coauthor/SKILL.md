---
name: doc-coauthor
description: Use when the user wants to write a substantial document together — a proposal, spec, PRD, design doc, policy, essay, grant, report — through an interactive process of gathering context, drafting section by section, and refining, rather than a one-shot draft.
license: MIT. Complete terms in LICENSE.txt
---

# Document Co-authoring

Write *with* the user, not *for* them. The user owns the ideas; you bring structure, clarity, speed and a critical eye.

## Stage 1 — Gather context (short)

Ask only what you can't infer, in **one** message, at most 5 questions:
1. **Purpose:** what decision or action should this document cause?
2. **Audience:** who reads it, what do they already know, what do they care about?
3. **Must-include material:** notes, data, prior docs, constraints? (Invite them to paste or attach.)
4. **Format and length:** template to follow? Target length?
5. **Tone:** formal, plain, persuasive, neutral?

If the user says "just start", make sensible assumptions, list them in two lines, and go.

Then ask them to brain-dump everything they know, in any order. Messy is fine — sorting it is your job.

## Stage 2 — Outline

Propose an outline: section headings + one line each on what the section must achieve. Lead with the conclusion or ask (for decision docs) unless the format demands otherwise.

Get a quick yes / changes before drafting. This is the cheapest point to change direction.

## Stage 3 — Draft section by section

First create the document scaffold: every heading with a one-line placeholder, so the user can see the whole shape. Start with the section that has the most unknowns (usually the core proposal or the approach); leave the summary for last.

For each section:
1. **Questions** — 3–6 specific questions about what this section must contain (answerable in shorthand: "1: yes, 2: see the Slack thread, 3: no").
2. **Brainstorm** — list 5–15 numbered candidate points, including things the user mentioned earlier but may have forgotten and angles they haven't raised.
3. **Curate** — the user says what to keep, cut or merge ("keep 1, 4, 7; cut 3, audience knows it; merge 5+6"). Free-form feedback is fine; turn it into keep/cut decisions yourself, and note *why* things were cut — it tells you their priorities for the next sections.
4. **Gap check** — "anything missing?"
5. **Draft** — replace the placeholder with prose; mark gaps `[TODO: confirm Q3 numbers]`.
6. **Refine with targeted edits** — change only what was asked, never regenerate the whole doc. If the user edits the text themselves, notice what they changed and apply that preference to later sections.
7. After three rounds with no real changes, ask whether anything can be cut without losing meaning.

For short documents (< ~1 page) skip the per-section loop and draft the whole thing at once.

For short documents (< ~1 page) draft the whole thing at once instead.

Keep a running list of open TODOs and decisions; show it when it changes.

## Stage 4 — Review passes

Once all sections exist, do focused passes rather than one vague "polish":
1. **Argument:** does each section serve the purpose? Is the main point in the first paragraph? Anything that doesn't earn its place → cut.
2. **Reader test:** read as the target audience. Where would they get lost, object, or ask "so what?" Fix or flag those spots.
3. **Evidence:** every claim supported; numbers consistent across sections.
4. **Clarity:** short sentences, active voice, concrete words, defined acronyms, no filler ("It is important to note that…").
5. **Consistency:** terms, capitalization, tense, formatting.

Report what you changed in a few bullets — don't silently rewrite the user's voice.

## Stage 4b — Reader test (catch blind spots)

Authors can't un-know context. Test the draft on a reader who has none:

1. Write 5–8 questions a real reader would ask ("What are we deciding?", "What does this cost?", "Why not option B?", "What do I need to do by when?").
2. **If you can start a fresh helper agent:** give it *only* the document and the questions — no conversation history — and ask for each answer plus anything ambiguous and any knowledge the doc assumes.
   **If you can't:** ask the user to paste the doc into a fresh chat with those questions, and paste the answers back.
3. Compare answers with what the authors intended. Every wrong or hedged answer marks a section to fix: missing context, an undefined term, a buried conclusion, or two sections that contradict.
4. Fix, then re-run only the questions that failed. Done when a cold reader answers them all correctly.

Also before sharing: images need alt text (a reader using an assistant can't see them), and every link should open for the intended audience.

## Stage 5 — Finish

- Resolve or explicitly list remaining TODOs.
- Add a summary / TL;DR at the top if the doc is longer than ~2 pages.
- Deliver in the format the user needs (a shareable doc by default; Word/PDF if asked).

## Principles

- Preserve the user's voice and opinions; suggest, don't overwrite. When you disagree, say so once with a reason, then follow their call.
- Prefer showing a rewritten paragraph over describing what to change.
- Short feedback loops beat long silent drafts.
- Never invent facts, quotes, data or sources — mark them as TODO.
