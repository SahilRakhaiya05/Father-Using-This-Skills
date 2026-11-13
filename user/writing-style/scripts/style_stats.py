#!/usr/bin/env python3
"""Measure someone's writing style from their own samples (standard library only, no network).

Usage:
  style_stats.py SAMPLES_DIR [--out stats.json] [--examples examples.md] [--min-words 25] [--chat-min-words 6]
  style_stats.py --selftest

Layout: SAMPLES_DIR/<channel>/<audience>__<thread>__<YYYY-MM-DD>__<n>.txt  (one message or document per file)
  channel  = email | chat | slack | dm | whatsapp | sms | docs | posts | …  (folder name)
  audience = team | manager | client | friend | external | …               (filename prefix)
Short chat messages from the same thread are pooled into one sample, so quick replies still count.

Cleaning before measuring: quoted replies ("> …", "On … wrote:"), forwarded blocks, signatures after "--",
"Sent from my …", auto-replies / out-of-office messages are removed, so only the author's own words count.

Output: per channel and per audience — length, sentence rhythm (mean, median, spread), contractions,
lowercase starts, conjunction starts, greetings, sign-offs, punctuation habits, exclamation/emoji/bullet use,
function words, frequent phrases, AI-sounding words used vs never used — plus provenance (counts, date range)
and a few representative samples per channel (examples.md).
"""
import json
import os
import re
import statistics
import sys
from collections import Counter, defaultdict

CHAT = {"chat", "slack", "dm", "dms", "whatsapp", "sms", "teams", "messages", "telegram"}
FUNCTION_WORDS = ["the", "a", "and", "but", "so", "i", "we", "you", "just", "really", "actually", "maybe",
                  "think", "please", "thanks", "sorry", "basically", "also", "though", "anyway", "pretty", "quite"]
AI_TELLS = ["delve", "leverage", "utilize", "seamless", "robust", "furthermore", "moreover", "in conclusion",
            "it's worth noting", "i hope this email finds you well", "game-changer", "navigate", "tapestry",
            "streamline", "elevate", "synergy", "circle back", "unlock", "pivotal", "foster", "quietly",
            "load-bearing", "testament", "realm", "embark", "nuanced", "honestly,", "let's dive", "crucial"]
GREETING_RE = re.compile(r"^\s*(hi|hey|hello|dear|good (?:morning|afternoon|evening)|hiya|yo|namaste|greetings)\b", re.I)
SIGNOFF_RE = re.compile(r"^\s*(thanks|thank you|thx|ty|cheers|best|regards|warm regards|kind regards|best regards|"
                        r"talk soon|take care|love|br|sincerely)\b[^\n]{0,30}$", re.I | re.M)
QUOTE_HEADER_RE = re.compile(r"^(on .{5,160} wrote:|-{2,} ?original message ?-{2,}|-{2,} ?forwarded message ?-{2,}|"
                             r"from: .+@.+|sent from my \w+|get outlook for \w+)", re.I | re.M)
AUTO_RE = re.compile(r"out of (the )?office|auto(matic)?[- ]?reply|i am currently away|this is an automated", re.I)
CONJ_RE = re.compile(r"^(and|but|so|or|also|plus)\b", re.I)


def clean(text):
    text = text.replace("\r\n", "\n")
    m = QUOTE_HEADER_RE.search(text)
    if m:
        text = text[:m.start()]
    m = re.search(r"^-- ?$", text, re.M)
    if m:
        text = text[:m.start()]
    return "\n".join(l for l in text.split("\n") if not l.lstrip().startswith(">")).strip()


def sentences(text):
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [p.strip() for p in parts if re.search(r"[A-Za-zऀ-ॿ]", p or "")]


def words(text):
    return re.findall(r"[A-Za-zऀ-ॿ']+", text.lower())


def measure(samples, messages=None):
    messages = messages or samples
    all_words, sent_lens, contractions = [], [], 0
    greet, sign = Counter(), Counter()
    punct = Counter()
    bullets = exclam_samples = emoji_msgs = lower_start = conj_start = n_exclam = 0
    lengths = []
    for s in samples:
        w = words(s)
        all_words += w
        lengths.append(len(w))
        for sent in sentences(s):
            sent_lens.append(len(words(sent)))
            if sent[:1].islower():
                lower_start += 1
            if CONJ_RE.match(sent):
                conj_start += 1
            if sent.endswith("!"):
                n_exclam += 1
        contractions += len(re.findall(r"\b\w+'(s|t|re|ve|ll|d|m)\b", s.lower()))
        punct["em_dash"] += s.count("—")
        punct["spaced_hyphen_dash"] += s.count(" - ") + s.count(" – ")
        punct["ellipsis"] += s.count("...") + s.count("…")
        punct["exclamation"] += s.count("!")
        punct["question"] += s.count("?")
        punct["semicolon"] += s.count(";")
        punct["parentheses"] += s.count("(")
        punct["colon"] += s.count(":")
        if "!" in s:
            exclam_samples += 1
        if re.search(r"^\s*([-*•]|\d+[.)])\s", s, re.M):
            bullets += 1
    for m in messages:
        g = GREETING_RE.match(m)
        if g:
            greet[g.group(1).lower()] += 1
        sg = SIGNOFF_RE.findall(m)
        if sg:
            sign[sg[-1].lower()] += 1
        if re.search(r"[\U0001F300-\U0001FAFF☀-➿]|(?<![\w:;])[:;]-?[)(DPp](?!\w)", m):
            emoji_msgs += 1
    n, nm = max(len(samples), 1), max(len(messages), 1)
    nw, ns = max(len(all_words), 1), max(len(sent_lens), 1)
    fw = Counter(all_words)
    grams = Counter(zip(all_words, all_words[1:], all_words[2:])) + Counter(zip(all_words, all_words[1:]))
    phrases = [" ".join(k) for k, c in grams.most_common(80) if c >= 3 and not all(x in FUNCTION_WORDS for x in k)][:15]
    text_all = " ".join(samples).lower()
    return {
        "samples": len(samples), "messages": len(messages), "words": len(all_words),
        "words_per_sample": {"median": statistics.median(lengths) if lengths else 0,
                             "p90": sorted(lengths)[int(len(lengths) * 0.9)] if lengths else 0},
        "words_per_message_median": statistics.median([len(words(m)) for m in messages]) if messages else 0,
        "sentence_words": {"mean": round(statistics.mean(sent_lens), 1) if sent_lens else 0,
                           "median": statistics.median(sent_lens) if sent_lens else 0,
                           "spread_stdev": round(statistics.pstdev(sent_lens), 1) if sent_lens else 0,
                           "short_share(<=6)": round(sum(l <= 6 for l in sent_lens) / ns, 2)},
        "contractions_per_100_words": round(contractions * 100 / nw, 2),
        "lowercase_sentence_starts_share": round(lower_start / ns, 2),
        "conjunction_sentence_starts_share": round(conj_start / ns, 2),
        "exclamations_per_100_sentences": round(n_exclam * 100 / ns, 1),
        "greetings": greet.most_common(5),
        "greeting_share": round(sum(greet.values()) / nm, 2),
        "signoffs": sign.most_common(5),
        "signoff_share": round(sum(sign.values()) / nm, 2),
        "punctuation_per_1000_words": {k: round(v * 1000 / nw, 2) for k, v in punct.items()},
        "share_with": {"exclamation": round(exclam_samples / n, 2), "emoji_per_message": round(emoji_msgs / nm, 2),
                       "bullets_or_numbered": round(bullets / n, 2)},
        "function_words_per_1000": {k: round(fw[k] * 1000 / nw, 1) for k in FUNCTION_WORDS},
        "frequent_phrases": phrases,
        "ai_tells_used": {t: text_all.count(t) for t in AI_TELLS if t in text_all},
        "ai_tells_never_used": [t for t in AI_TELLS if t not in text_all],
        "english_stopword_share": round(sum(fw[k] for k in ("the", "and", "a", "i", "you", "to", "is")) / nw, 3),
        "non_english_suspected": (sum(fw[k] for k in ("the", "and", "a", "i", "you", "to", "is")) / nw) < 0.04,
    }


def parse_name(fname):
    stem = fname[:-4]
    parts = stem.split("__")
    audience = parts[0].lower() if len(parts) > 1 else "general"
    bundle = "__".join(x for x in parts[:-1] if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", x)) if len(parts) > 1 else stem
    date = next((p for p in parts if re.fullmatch(r"\d{4}-\d{2}-\d{2}", p)), None)
    return audience, bundle, date


def load(dirpath, min_words, chat_min):
    raw = defaultdict(list)                 # channel -> [(audience, bundle, date, text)]
    dropped = Counter()
    for root, _, files in os.walk(dirpath):
        for f in sorted(files):
            if not f.endswith(".txt"):
                continue
            ch = os.path.relpath(root, dirpath)
            ch = "general" if ch == "." else ch.split(os.sep)[0].lower()
            txt = open(os.path.join(root, f), encoding="utf-8", errors="replace").read()
            if AUTO_RE.search(txt[:400]):
                dropped["auto_reply"] += 1
                continue
            if re.search(r"-{2,} ?forwarded message", txt, re.I) and len(words(clean(txt))) < 5:
                dropped["forward_only"] += 1
                continue
            t = clean(txt)
            if not t:
                dropped["empty_after_cleaning"] += 1
                continue
            aud, bundle, date = parse_name(f)
            raw[ch].append((aud, bundle, date, t))
    groups = {}
    for ch, items in raw.items():
        if ch in CHAT:
            pools = defaultdict(list)
            for aud, bundle, date, t in items:
                pools[(aud, bundle)].append((date, t))
            samples = []
            for (aud, bundle), msgs in pools.items():
                joined = "\n".join(t for _, t in msgs)
                if len(words(joined)) < chat_min:
                    dropped["too_short"] += len(msgs)
                    continue
                samples.append({"audience": aud, "text": joined, "messages": [t for _, t in msgs],
                                "dates": [d for d, _ in msgs if d]})
        else:
            samples = []
            for aud, bundle, date, t in items:
                if len(words(t)) < min_words:
                    dropped["too_short"] += 1
                    continue
                samples.append({"audience": aud, "text": t, "messages": [t], "dates": [date] if date else []})
        if samples:
            groups[ch] = samples
    return groups, dropped


def pick_examples(samples, k=5):
    if not samples:
        return []
    by_len = sorted(samples, key=lambda s: len(words(s["text"])))
    idx = sorted({int(i * (len(by_len) - 1) / max(k - 1, 1)) for i in range(min(k, len(by_len)))})
    picked = [by_len[i] for i in idx]
    auds = {s["audience"] for s in picked}
    for s in samples:                               # make sure every audience has an example
        if s["audience"] not in auds:
            picked.append(s)
            auds.add(s["audience"])
    return picked


def analyse(dirpath, min_words=25, chat_min=6):
    groups, dropped = load(dirpath, min_words, chat_min)
    result = {"provenance": {}, "dropped": dict(dropped), "channels": {}}
    for ch, samples in groups.items():
        texts = [s["text"] for s in samples]
        msgs = [m for s in samples for m in s["messages"]]
        stats = measure(texts, msgs)
        by_aud = defaultdict(list)
        for s in samples:
            by_aud[s["audience"]].append(s)
        if len(by_aud) > 1:
            stats["audiences"] = {a: {k: v for k, v in measure([x["text"] for x in ss],
                                                                 [m for x in ss for m in x["messages"]]).items()
                                      if k in ("samples", "words_per_message_median", "sentence_words",
                                               "contractions_per_100_words", "exclamations_per_100_sentences",
                                               "greetings", "signoffs", "share_with")}
                                  for a, ss in by_aud.items()}
        result["channels"][ch] = stats
        dates = sorted(d for s in samples for d in s["dates"])
        result["provenance"][ch] = {"samples": len(samples), "messages": len(msgs),
                                    "audiences": dict(Counter(s["audience"] for s in samples)),
                                    "from": dates[0] if dates else None, "to": dates[-1] if dates else None}
    all_s = [s for v in groups.values() for s in v]
    result["overall"] = measure([s["text"] for s in all_s], [m for s in all_s for m in s["messages"]]) if all_s else {}
    return result, groups


def selftest():
    import tempfile
    d = tempfile.mkdtemp()
    os.makedirs(f"{d}/email")
    os.makedirs(f"{d}/slack")
    for i in range(3):
        open(f"{d}/email/team__launch__2026-10-0{i + 1}__{i}.txt", "w").write(
            "Hey team,\n\nQuick one - can we ship Friday? I think we're close and the copy's ready. "
            "But let's double check the pricing page first.\n\nThanks!\nA\n\nOn Mon, Bob wrote:\n> please delve into this")
    open(f"{d}/email/client__acme__2026-10-05__1.txt", "w").write(
        "Dear Priya,\n\nThank you for the update. We will confirm the delivery schedule by Thursday and share "
        "the revised plan with your team.\n\nKind regards,\nAsha")
    open(f"{d}/email/team__ooo__2026-10-06__1.txt", "w").write("Out of office: I am currently away until Monday.")
    for i in range(4):
        open(f"{d}/slack/team__general__2026-10-0{i + 1}__{i}.txt", "w").write("yep makes sense :)")
    r, g = analyse(d, min_words=10, chat_min=6)
    e, s = r["channels"]["email"], r["channels"]["slack"]
    assert r["dropped"].get("auto_reply") == 1, r["dropped"]
    assert "audiences" in e and set(e["audiences"]) == {"team", "client"}
    assert e["greetings"][0] == ("hey", 3), e["greetings"]
    assert s["samples"] == 1 and s["messages"] == 4, (s["samples"], s["messages"])   # pooled chat thread
    assert s["share_with"]["emoji_per_message"] == 1.0
    assert "delve" in r["overall"]["ai_tells_never_used"]                            # quoted text excluded
    assert r["provenance"]["email"]["from"] == "2026-10-01"
    print("selftest OK")


def main():
    if "--selftest" in sys.argv:
        return selftest()
    a = sys.argv[1:]
    if not a:
        sys.exit(__doc__)
    out = a[a.index("--out") + 1] if "--out" in a else "stats.json"
    ex = a[a.index("--examples") + 1] if "--examples" in a else "examples.md"
    mw = int(a[a.index("--min-words") + 1]) if "--min-words" in a else 25
    cm = int(a[a.index("--chat-min-words") + 1]) if "--chat-min-words" in a else 6
    result, groups = analyse(a[0], mw, cm)
    if not groups:
        sys.exit(f"no usable samples (dropped: {result['dropped']}) — gather more real writing; don't lower the limits")
    json.dump(result, open(out, "w"), indent=2, ensure_ascii=False)
    with open(ex, "w", encoding="utf-8") as f:
        for ch, samples in groups.items():
            f.write(f"## {ch}\n\n")
            for s in pick_examples(samples):
                tag = f"audience: {s['audience']}" + (f", {len(s['messages'])} messages" if len(s["messages"]) > 1 else "")
                body = "\n---\n".join(s["messages"]) if len(s["messages"]) > 1 else s["text"]
                f.write(f"*{tag}*\n```\n{body[:1500]}\n```\n\n")
    for ch, p in result["provenance"].items():
        print(f"{ch}: {p['samples']} samples ({p['messages']} messages), audiences {p['audiences']}, {p['from']} → {p['to']}")
    print(f"dropped: {result['dropped'] or 'none'} -> {out}, {ex}")
    thin = [ch for ch, p in result["provenance"].items() if p["samples"] < 10]
    if thin:
        print(f"note: fewer than 10 samples in {thin} — describe those channels cautiously or gather more")


if __name__ == "__main__":
    main()
