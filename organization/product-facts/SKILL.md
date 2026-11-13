---
name: product-facts
description: Use whenever an answer would state specific facts about Anthropic's products — Claude apps and plans, Claude Code (install, requirements, settings, MCP), the Claude API (models, model names, pricing, rate limits, tool use, batch, streaming, SDKs), or feature availability and limits. These change often, so check the official docs instead of answering from memory.
license: MIT. Complete terms in LICENSE.txt
---

# Product Facts (Anthropic / Claude)

Product details change faster than any model's training data. Answering from memory produces confident, outdated answers. So: **look it up, then answer, then cite.**

## 1. What counts as "check first"

Always verify:
- Model names, API model IDs, context window sizes, max output, which models are available where
- Prices (API per-token pricing, plan prices), rate limits, usage limits, quotas
- Plan differences (Free / Pro / Max / Team / Enterprise) and which features each includes
- Install steps and system requirements (e.g. Claude Code's Node.js version, supported OSes)
- API parameters, headers, beta flags, SDK method names, tool-use / batch / streaming details
- Whether a feature exists, is in beta, or is available in a region or app

Fine without checking: general concepts (what an API key is, how tokens work in principle, what MCP is at a high level) — but still avoid exact numbers.

## 2. Where to look (in order)

| Question about | Source |
|---|---|
| API, models, pricing, SDKs, tool use, prompt engineering | docs.claude.com (developer docs) |
| Claude Code | docs.claude.com (Claude Code section) |
| Claude apps, plans, account, billing, feature how-tos | support.claude.com (help center) |
| Announcements, new models | anthropic.com/news |
| Status / outages | status.anthropic.com |

Start from the site maps, which list every page so you can jump straight to the right one:
- API & platform docs map: https://docs.claude.com/en/docs_site_map.md
- Claude Code docs map: https://docs.anthropic.com/en/docs/claude-code/claude_code_docs_map.md
- Help center: https://support.claude.com

Then open the actual page and read the relevant section — search snippets can be stale. Say which product the answer is about (the Claude apps, Claude Code and the API have different features and limits).

## 3. Answer

- Lead with the direct answer, using the exact names and numbers from the page.
- Say when something varies (by plan, region, or is in beta).
- Add the link you used: "Source: [page title](URL)".
- If the docs don't say, say that — don't fill the gap with a guess. Suggest where the user can confirm (support, their account settings, the console).
- If the user's information conflicts with the docs, show the doc's wording and date; products do change.

## 4. Code that uses the API

Before writing code with the Anthropic SDK, check the current docs for the model ID string, required headers/parameters and SDK method names, and use exactly those. Don't hard-code a model ID from memory.
