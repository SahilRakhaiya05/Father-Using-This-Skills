# Motion craft

Use this to plan a film and to judge a contact sheet or draft. Code is rarely the problem; pacing, hierarchy and restraint are.

## Structure

| Length | Shape |
|---|---|
| 6–15 s | hook → one proof → action |
| 15–30 s | hook → problem → 2–3 proofs → action |
| 30–60 s | hook → problem → how it works (3 beats) → proof (number or quote) → action |
| 60–90 s | the same with a second act; change the visual rhythm at the midpoint |

- The hook is a claim, a question or a number — not a logo. Logo goes last, or small in a corner.
- One idea per scene. If a scene needs "and", it is two scenes.
- Scene length 2–6 s. Vary it: short-short-long reads as rhythm; equal lengths read as a slideshow.
- Write the words first and cut them by a third. Then cut again.

## Timing numbers

| Thing | Value |
|---|---|
| Entrance of text | 0.3–0.8 s (up to 1.6 s in slow, premium styles) |
| Exit | about 70% of the entrance; often just a cut |
| Stagger between siblings | 0.04–0.10 s; whole group under ~0.8 s |
| Gap between two separate beats | 0.25–0.5 s |
| Hold after the last thing lands | 0.4 s + 0.16 s per word on screen |
| Scene transition | 0.3–0.6 s; cuts are free |
| Number count-up | 0.9–1.4 s, `expo` |
| Longest stillness | ~2.5 s (the default camera push covers holds) |
| Final frame | ≥ 1.5 s |

At 30 fps one frame is 0.033 s. Put the important landing on a round time (2.0 s, not 2.07 s) so sound and cuts can hit it.

## Easing

- Things arriving decelerate (`out`, `expo`, `snap`). Things leaving accelerate (`in`). Things moving within the frame do both (`inout`).
- `linear` is for mechanical things only: tickers, typing, progress, camera pushes.
- Overshoot (`back`) says friendly; `elastic` says toy; `bounce` says joke. Match the brand.
- Bigger and heavier elements move slower. A full-screen panel takes longer than a badge.

## Hierarchy — one focus per frame

On every frame of the sheet ask: where does the eye go first? There must be one answer.

- Make the important thing largest **and** highest contrast. Size ratio between headline and body at least 2:1.
- Motion draws the eye more than colour. Only the thing you want read should be moving when it needs to be read.
- Accent colour on one element per scene.
- Alignment: pick left or centre for the film. Centre suits short lines; left suits lists and anything over two lines.

## Layout

- Keep text 5% from every edge. On 9:16 also keep the top 12% and bottom 20% clear — app buttons and captions cover them.
- Lines of 2–6 words on vertical, up to 10 on wide. Break lines by meaning, not by width.
- Leave empty space. A frame filled edge to edge has nowhere to look.
- Body text at least 4% of the short side (about 43 px at 1080). Labels may go to 2.6%.

## Continuity between scenes

- Carry something across the cut: the accent colour, a shape, the direction of movement.
- Direction means something. Forward in the story = things move left or up. Do not reverse without a reason.
- A scene that enters from the right should not exit to the right.
- Same kind of content, same entrance. New entrance = "this is a different kind of thing".

## Text on screen

- People read about 3 words a second when the text is still, fewer while it moves.
- Never animate text that is being read. Land it, hold it, then move on.
- Per-character animation is for 1–3 words. Sentences animate per word or per line.
- Numbers: count up once, land exactly, and keep units attached (`4.2 s`, `58%`).
- Sentence case reads faster than all caps; save caps for 1–4 word hits and labels.

## Charts and data

- One message per chart; put it in the title ("Deploys up 5× in a quarter"), not "Deploys per week".
- Animate in reading order: axis or labels, then marks, then the highlighted value.
- Bars grow from the baseline, lines draw left to right, values count with the mark.
- Highlight one series with the accent; everything else in muted tones.
- Start bar axes at zero. Round numbers the way a person would say them.

## Reviewing a contact sheet

Go frame by frame:
1. Is anything off-frame, clipped or overlapping? (The tool reports these — fix all.)
2. Can each frame be read at thumbnail size?
3. Is there one focus?
4. Do two neighbouring scenes look the same? Change layout or scale.
5. Does the final frame say what to do?
6. Is the style consistent — same corners, same accent, same type?

## Reviewing a draft

Watch three times: once normally, once muted at phone size, once looking only at the edges and corners.
- Mark the time of anything that feels slow, sudden or unclear, then fix those ranges and re-render only them.
- If a moment feels slow, shorten the hold before trying a flashier animation.
- If it feels chaotic, remove an animation before adding polish.
- A fresh reviewer catches more than the maker. When a second agent or person is available, have them review the draft without the brief and say what they think the message is.

## Common mistakes

| Looks wrong | Usually because | Fix |
|---|---|---|
| "PowerPoint" feel | every scene same layout and length, everything fades | vary scale and rhythm; use the style's transition; one bold moment |
| Busy | too many things animate at once | group them; stagger; cut half |
| Floaty | long durations with soft easing everywhere | shorten to 0.4–0.6 s; use `expo`/`snap` |
| Jittery | tiny text moving, or sub-pixel drifts on thin lines | hold text still; thicken lines |
| Cheap | default colours, three fonts, drop shadows on everything | one style, two fonts, one accent |
| Unreadable on phone | small type, low contrast, text in the bottom fifth | enlarge, raise contrast, move up |
| Ends abruptly | last scene too short | hold the final frame ≥ 1.5 s, fade audio |

## Accessibility

- No flashes faster than three per second; keep `flash` transitions rare.
- Do not rely on colour alone for meaning — add a label or shape.
- Provide captions when there is speech (see `sound-and-captions.md`).
