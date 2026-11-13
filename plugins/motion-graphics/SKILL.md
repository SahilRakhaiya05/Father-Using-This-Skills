---
name: motion-graphics
description: Use this skill whenever the user wants animated video made from code - motion graphics, kinetic typography, explainer or product launch videos, animated titles, lower thirds, logo stings, animated charts and stats, social Reels/Shorts/TikTok clips, or any "make this move" request. It offers a choice of 16 visual styles, builds the film as HTML scenes, renders it frame-exact to MP4/WebM/MOV/GIF (with transparency if needed), and verifies the result. Also routes to Remotion, HyperFrames, Manim, Motion Canvas or Lottie when one of those fits better. For editing existing footage, slideshows or plain ffmpeg work use the video-making skill instead.
license: MIT. Complete terms in LICENSE.txt
---

# Motion Graphics

You are the director, the designer and the editor. The job is a short film that looks intentional: one look, clear story, motion that means something, and a file that plays everywhere.

Everything is driven by one tool, `scripts/mg.py`, and a small runtime, `assets/mg.js`. A film is an HTML page of scenes; every frame is computed from the time alone, so a render is identical on every run.

Needs Python 3.8+, `pip install playwright pillow`, `python -m playwright install chromium`, and ffmpeg. Check these first; ask before installing anything.

## The workflow

Do the steps in order. Steps 1–2 are a conversation; do not render before the look and the storyboard are agreed, unless the user said "just make it".

### 1. Brief — ask only what is missing

| Decide | Default if not told |
|---|---|
| Message — the one thing a viewer should remember | ask; never guess this |
| Where it plays → format | 16:9 for YouTube/web/slides · 9:16 for Reels/Shorts/TikTok · 1:1 or 4:5 for feeds |
| Length | 15–30 s social · 30–60 s launch · 60–90 s explainer |
| Brand — colours, fonts, logo | pick a style, then override its accent |
| Sound — music, voiceover, silent | silent draft first; must work on mute anyway |

### 2. Style — let the user choose

```bash
python scripts/mg.py styles                          # the 16 looks, with their motion personality
python scripts/mg.py pick styles.png --format 9:16 --title "Their headline"
```

`pick` renders the user's own headline in every style on one sheet. Show it and ask which they want. If they have no opinion, recommend one from this table and say why in a sentence.

| The film is… | Start from |
|---|---|
| Product or feature launch, UI | `saas-glass`, `clean-minimal`, `sunset-gradient` |
| Hook-first social clip, hype, big words | `bold-kinetic`, `neo-brutal`, `sunset-gradient` |
| Numbers, report, year in review | `data-story`, `corporate` |
| Story, essay, quote, documentary | `editorial`, `cinematic-dark`, `paper-craft` |
| Developer tool, CLI, architecture | `mono-terminal`, `blueprint`, `neon-cyber` |
| Premium brand, invitation, property | `luxury`, `cinematic-dark` |
| Kids, education, celebration | `playful`, `paper-craft` |
| Retro, gaming, music | `retro-vhs`, `neon-cyber` |

A style is colour + type + **how things move** (entrance, easing, speed, transition). Mixing two styles in one film looks like a mistake. For a brand look, write a small JSON that extends a style — see `references/styles.md`.

### 3. Storyboard — write it before any HTML

Write `storyboard.json`: an ordered list of scenes. One idea per scene, 12 words or fewer on screen, the first scene is the hook.

```json
{"scenes": [
  {"type": "title",   "kicker": "Launch week", "title": "Ship faster with *Orbit*", "subtitle": "Deploys your team will like"},
  {"type": "bullets", "title": "Three things change", "items": ["One command", "4-second rollbacks", "Previews per branch"]},
  {"type": "stat",    "kicker": "Median deploy", "value": 4.2, "suffix": " s", "label": "down from 3 minutes"},
  {"type": "bars",    "title": "Deploys per week", "items": [{"label": "Before", "value": 12}, {"label": "After", "value": 58}]},
  {"type": "cards",   "title": "Built for teams", "items": [{"title": "Secure", "text": "SSO and audit log"}]},
  {"type": "quote",   "text": "We stopped fearing *Fridays*.", "by": "Head of Platform"},
  {"type": "end",     "title": "Try *Orbit* today", "cta": "orbit.example"}
]}
```

`*word*` marks the accent word. Scene length is worked out from the words unless you give `"dur"`. Any scene can be `{"type": "html", "html": "…", "dur": 4}` for custom markup. Show the storyboard to the user as a short table (scene · on screen · seconds) and get a yes.

### 4. Build

```bash
python scripts/mg.py new film --style saas-glass --format 16:9 --storyboard storyboard.json --accent "#ff5a1f"
```

This writes `film/index.html`, `film/theme.css` and `film/mg.js`. Open `index.html` in a browser for a live preview with a scrubber. Then edit the HTML by hand to direct it: reorder beats, change an entrance, add a chart or SVG. The attribute reference — animations, easings, transitions, camera moves, loops, custom canvas code — is in `references/authoring.md`. Read it before hand-editing.

Rules that keep a render exact (the linter enforces them):
- Motion comes only from `data-*` attributes or `MG.frame(t)` / `MG.scene()` callbacks. No CSS `transition`/`animation`, no timers, no `Date.now()`, no `Math.random()` — use `MG.rand(seed)`.
- Fonts, images and scripts live in the project folder. A render that needs the network is not repeatable.
- Footage is not rendered here. Render graphics with `--alpha` and lay them over the clip (step 6).

### 5. Look before you render

```bash
python scripts/mg.py lint film                 # determinism, unknown names, reading time, long holds
python scripts/mg.py sheet film sheet.png      # contact sheet + off-frame / clipped / overlapping text report
```

**Open the sheet and look at it.** Check it against `references/motion-craft.md` (hierarchy, safe areas, one focus per frame). Fix, re-run, repeat. Rendering is the slow step; the sheet takes seconds.

### 6. Render

```bash
python scripts/mg.py render film draft.mp4 --scale 0.5            # fast draft to judge timing
python scripts/mg.py render film draft.mp4 --scale 0.5 --range 4-9  # only the part you changed
python scripts/mg.py render film final.mp4 --audio music.mp3      # full quality, music faded out at the end
python scripts/mg.py render film lower-third.mov --alpha          # transparent ProRes 4444 (or .webm)
python scripts/mg.py render film loop.gif --scale 0.4             # GIF for chat and docs
```

Show the draft, take notes, change, re-render the changed range. One full-quality render at the end. To put transparent graphics over footage:

```bash
ffmpeg -i clip.mp4 -i lower-third.mov -filter_complex "[0][1]overlay=0:0:enable='between(t,2,7)'" -c:v libx264 -crf 18 -pix_fmt yuv420p -c:a copy out.mp4
```

Sound, voiceover timing and captions: `python scripts/mg.py cues film cues.json` lists every scene and animation start time; use it to place sound effects and subtitles exactly. See `references/sound-and-captions.md`.

### 7. Verify, then deliver

```bash
python scripts/mg.py check final.mp4 --project film
```

It confirms size, frame rate, duration, codec and pixel format against the project, and warns about dead holds (nothing moving), black frames, clipping or near-silent audio. Deliver only after `OK`. Give the user the file, one line of facts (length, size, style), and what they can ask to change.

## Quality bar — check every film against this

1. **Hook in the first 2 seconds.** Something legible and moving by frame 15.
2. **One focus per frame.** If two things enter together they are one group.
3. **Readable on mute, on a phone.** Body text ≥ 4% of the short side; hold ≈ 0.4 s + 0.16 s per word after the last entrance.
4. **Nothing sits dead still** for more than ~2.5 s — scenes carry a slow camera push by default; keep it.
5. **Entrances are fast, exits faster, holds honest.** Enter 0.3–0.8 s, exit about 70% of that.
6. **Stagger, do not stampede.** 0.04–0.1 s between siblings; total stagger under ~0.8 s.
7. **One transition language** per film; a second one only for the big moment.
8. **Safe areas.** 5% from every edge; on 9:16 keep the bottom 20% and top 12% free of text.
9. **Ends on the action** — the final frame names what to do next and holds ≥ 1.5 s.

## When another engine fits better

`mg.py` covers type, layout, charts, UI-style and transparent overlays with zero build step. Switch when the job is something else — `references/engines.md` has the commands, licences and trade-offs:

| Need | Use |
|---|---|
| React components, data-driven batches, an existing Remotion project | Remotion (note its company licence) |
| GSAP timelines, video/audio clips inside the composition, agent-first HTML | HyperFrames (Apache-2.0) |
| Maths, equations, geometry, algorithm visuals | Manim Community |
| Hand-authored TypeScript animation with an editor | Motion Canvas |
| Animation that ships inside an app or site | Lottie / CSS / GSAP — not a video |
| 3D scenes, shaders | Three.js driven from `MG.frame(t)`, or Blender |
| Cutting footage, slideshows, captions on a clip | the `video-making` skill |

Never migrate a working project to another engine without being asked.

## Reference files — load only what the task needs

| File | Read when |
|---|---|
| `references/authoring.md` | hand-editing scenes; any attribute, easing or transition name; custom canvas/SVG code |
| `references/styles.md` | choosing, mixing or creating a style; brand colours and fonts |
| `references/motion-craft.md` | judging a contact sheet or draft; pacing, hierarchy, typography, common mistakes |
| `references/sound-and-captions.md` | music, sound effects, voiceover timing, subtitles, loudness |
| `references/engines.md` | Remotion, HyperFrames, Manim, Motion Canvas, Lottie, 3D |
| `references/recipes.md` | ready patterns: lower third, logo sting, kinetic lyric line, chart race, UI mock, countdown, end card |

## Honest limits

- Fonts fall back to what the machine has. For an exact match, put the font files in the project and declare `@font-face` (check the font's licence first).
- A draft at `--scale 0.5` judges timing, not sharpness.
- The checks catch mechanical faults; taste still needs eyes. Always look at the sheet and the draft yourself and say what you saw, not what you assume.
- Use only assets the user owns or that are licensed for the use; note the source and licence of anything you bring in.
