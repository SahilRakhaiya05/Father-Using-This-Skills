# Styles

A style is three things that must agree: **colour**, **type** and **motion personality**. All 16 live in `assets/styles.json`. See them with `python scripts/mg.py pick styles.png`.

| id | Mood | Enters with | Speed | Transition | Best for |
|---|---|---|---|---|---|
| `clean-minimal` | calm, airy | rise | 0.6 s | fade | explainers, updates |
| `bold-kinetic` | loud, type-led | slam | 0.32 s | cut | hooks, hype, lyric lines |
| `saas-glass` | glow, depth | blur | 0.8 s | zoom | product launches, UI |
| `editorial` | magazine serif | reveal | 0.9 s | fade | stories, quotes, news |
| `neo-brutal` | flat, outlined | pop | 0.42 s | push | creators, indie products |
| `neon-cyber` | dark, glowing | wipe | 0.5 s | flash | gaming, dev tools, music |
| `retro-vhs` | 80s tape | type | 0.7 s | flash | throwbacks, intros |
| `corporate` | dependable | left | 0.55 s | wipe | B2B, training, investors |
| `playful` | bouncy, round | pop (elastic) | 0.9 s | iris | kids, consumer, parties |
| `cinematic-dark` | slow, dramatic | blur | 1.4 s | fade | trailers, brand films |
| `blueprint` | technical drawing | wipe | 0.7 s | wipe | architecture, hardware |
| `paper-craft` | handmade | tilt | 0.6 s | push-up | education, non-profit |
| `data-story` | numbers first | rise (expo) | 0.7 s | push-up | stats, reports |
| `luxury` | restrained | fade | 1.6 s | fade | fashion, property, invites |
| `sunset-gradient` | vivid gradient | scale | 0.7 s | push | social ads, events |
| `mono-terminal` | command line | type | 0.8 s | cut | CLI demos, releases |

## Choosing

Ask three questions, in this order:
1. **Who watches, and where?** A phone feed rewards contrast and speed (`bold-kinetic`, `sunset-gradient`). A board room rewards calm (`corporate`, `clean-minimal`).
2. **What is the content made of?** Words → type-led styles. Numbers → `data-story`. A product screen → `saas-glass`. A feeling → `cinematic-dark`, `luxury`, `editorial`.
3. **What does the brand already look like?** Match its darkness (light or dark background) and its corner shape (sharp or round) first; colour second.

When unsure, show `pick` with the user's real headline. People choose in seconds when they see their own words.

## Quick overrides

```bash
python scripts/mg.py new film --style clean-minimal --accent "#ff5a1f" --bg "#fffaf5" --fg "#1c1410"
```

## A brand style

Write a JSON file that extends the nearest built-in. Only list what changes.

```json
{
  "extends": "clean-minimal",
  "id": "acme",
  "colors": {"bg": "#0b1020", "surface": "#141b33", "fg": "#f5f7ff", "muted": "#9aa6c9", "accent": "#00d4a6", "accent2": "#ffb020"},
  "font_display": "'Acme Display', 'Segoe UI', Arial, sans-serif",
  "font_body": "'Acme Text', 'Segoe UI', Arial, sans-serif",
  "heading": {"weight": 800, "tracking": "-0.03em"},
  "radius": "1.2",
  "motion": {"anim": "rise", "ease": "expo", "dur": 0.55, "stagger": 0.06, "transition": "push", "cam": "push"},
  "extra_css": "@font-face{font-family:'Acme Display';src:url('fonts/AcmeDisplay.woff2')}"
}
```

```bash
python scripts/mg.py new film --style acme.json --storyboard storyboard.json
```

Put font files in `film/fonts/`. Confirm the licence allows video use and embedding.

## Building a palette that works

- Six roles only: `bg`, `surface` (cards), `fg` (text), `muted` (secondary text), `accent`, `accent2`.
- `fg` on `bg` needs strong contrast — aim for 7:1 for body text, since video is compressed and watched small. `muted` on `bg` at least 4.5:1.
- One accent does the pointing. `accent2` is for the second data series or a rare highlight, not decoration.
- Pure `#000` and `#fff` together look harsh after compression; shift one of them slightly.
- Saturated red and blue smear in H.264. Check a rendered frame, not the browser.

## Choosing type

- Two families at most: display for headlines, body for the rest. One family in two weights is often better.
- Headline line-height 0.9–1.1; body 1.3–1.4. Tight negative tracking on big sans headlines, positive tracking on uppercase labels.
- Thin weights vanish on phones. Minimum weight 400 for body, 600+ for anything over a busy background.
- Each built-in lists a well-known open font first and system fallbacks after it. If the first is not installed, the fallback is used and the look shifts slightly — bundle the font when it matters.

## Motion personality

The motion fields are what make a style feel like itself:

| Field | Effect | Range |
|---|---|---|
| `anim` | default entrance | any entrance name |
| `ease` | character: `snap` aggressive, `expo` polished, `back` friendly, `inout` graceful | |
| `dur` | energy: short = urgent, long = premium | 0.3–1.6 s |
| `stagger` | rhythm between siblings | 0.03–0.14 s |
| `transition` | how scenes change | any transition name |
| `cam` | background life during holds | `push`, `pull`, `pan-left`, `pan-right`, `rise`, `none` |

Keep these consistent across the film. Break the pattern once, on the moment that matters most.

## Mixing

Do not mix two built-ins. If the user likes "the colours of A and the motion of B", write a brand style that extends A and copies B's `motion` block.
