# Authoring reference

A film is one HTML page. `mg.js` reads it once, then computes every frame from the time.

```html
<body data-fps="30" data-width="1920" data-height="1080">
<div id="stage">
  <section class="scene center" id="intro" data-dur="4" data-in="fade">
    <div class="kicker" data-anim="fade" data-at="0.1">Launch week</div>
    <h1 data-anim="rise" data-at="0.3" data-split="words">Ship faster with <em>Orbit</em></h1>
    <p class="lead" data-anim data-at="1.1" data-out="fade">Deploys your team will like</p>
  </section>
  <div id="mg-flash"></div>
</div>
<script src="mg.js"></script>
</body>
```

## Contents
- Scenes · Element animation · Entrances · Easings · Transitions · Camera · Loops
- Text splitting · Numbers · Drawing lines · Layout classes · Units
- Custom code (canvas, SVG, charts) · Preview · What the linter rejects

## Scenes

Scenes play in page order. Each is `<section class="scene">` inside `#stage`.

| Attribute | Meaning | Default |
|---|---|---|
| `data-dur` | seconds on screen | 3 |
| `data-in` | transition from the previous scene | the style's (`--mg-transition`) |
| `data-in-dur` | transition length, seconds | 0.5 |
| `data-in-ease` | easing of the transition | `inout` |
| `data-cam` | slow camera move over the whole scene | the style's (`push`) |
| `data-cam-amt` | camera amount in percent | 4 |

A transition overlaps the previous scene, so total length = sum of `data-dur` − sum of transition lengths. `body data-duration="20"` forces a total.

## Element animation

All times are seconds **from the start of the element's scene**.

| Attribute | Meaning | Default |
|---|---|---|
| `data-anim` | entrance name; bare `data-anim` = the style's default | — |
| `data-at` | when the entrance starts | 0 |
| `data-dur` | entrance length | style (`--mg-dur`) |
| `data-ease` | easing name | style (`--mg-ease`) |
| `data-out` | exit name (plays in reverse sense) | none |
| `data-out-at` | when the exit starts | scene end − exit length |
| `data-out-dur` | exit length | 70% of the style duration |
| `data-split` | `words` or `chars` — animate each part | none |
| `data-stagger` | delay between parts | style (`--mg-stagger`) |
| `data-loop` | continuous motion while visible | none |
| `data-cue` | a label that appears in `mg.py cues` (for sound) | none |

The runtime owns `transform`, `opacity`, `filter` and `clip-path` on animated elements. To give one a static rotation or offset, wrap it in a plain `<div>` and style the wrapper.

## Entrances (`data-anim`, also valid for `data-out`)

| Name | Does | Good for |
|---|---|---|
| `fade` | opacity only | captions, calm styles |
| `rise` / `drop` | fade + move up / down | default text entrance |
| `left` / `right` | fade + slide in from that side | lists, lower thirds |
| `scale` | fade + grow from 82% | cards, logos |
| `pop` | grow from 40% with overshoot | badges, buttons, playful beats |
| `zoom-out` | settle from 135% | hero words |
| `slam` | drop in from 220%, hard stop | kinetic type |
| `blur` | fade from blur | premium, glass |
| `tilt` | rotate + rise | handmade, casual |
| `wipe` / `wipe-up` / `wipe-down` | reveal behind a moving edge | bars, underlines, images |
| `reveal` | wipe-up + small rise | editorial headlines |
| `bar` | scale X from the left edge | chart bars, progress, rules |
| `grow` | scale Y from the bottom | columns |
| `type` | characters appear one by one over `data-dur` | terminal, retro |
| `count` | number runs from `data-from` to `data-to` | stats |
| `draw` | SVG stroke draws itself | lines, icons, charts, maps |
| `none` | no entrance (use with `data-loop` or `data-out`) | |

## Easings (`data-ease`)

`linear` · `in` · `out` (default feel) · `inout` · `smooth` · `snap` (very fast then stop) · `expo` (long soft landing) · `back` (overshoot) · `elastic` (wobble) · `bounce` · `steps` (8 hard steps, retro)

Use `out`/`expo`/`snap` to enter, `in` to leave, `inout` for moves that start and end on screen. `back`, `elastic`, `bounce` are seasoning: one or two per scene.

## Transitions (`data-in`)

`cut` · `fade` · `push` (= `push-left`) · `push-right` · `push-up` · `slide` (new scene rises over the old) · `wipe` · `wipe-up` · `iris` · `zoom` · `flash` (white frame; needs `<div id="mg-flash">` in the stage)

## Camera (`data-cam`)

`push` (slow zoom in) · `pull` (slow zoom out) · `pan-left` · `pan-right` · `rise` · `none`

The move runs across the whole scene on its content, not the background. It exists so holds never look frozen. Use `none` for pixel-precise UI or when your own code animates the scene.

## Loops (`data-loop`)

`float` · `drift` · `pulse` · `spin` · `sway`, with `data-loop-amp` (default 10) and `data-loop-period` seconds (default 4). For decoration only — never on text someone has to read.

## Text splitting

`data-split="words"` or `"chars"` wraps each part and gives it its own entrance, `data-stagger` apart. Inline tags such as `<em>` survive. Keep total stagger under ~0.8 s: `stagger × parts`. Characters are for 1–3 words; sentences split by word.

## Numbers

```html
<div class="big" data-anim="count" data-to="4.2" data-decimals="1" data-suffix=" s" data-dur="1.2" data-ease="expo">0</div>
```
Also `data-from`, `data-prefix`, `data-sep` (thousands separator, default `,`; use `data-sep=""` for none).

## Drawing lines

```html
<svg class="line" viewBox="0 0 800 300" data-anim="draw" data-at="0.4" data-dur="1.4" data-ease="inout">
  <polyline points="0,260 200,210 400,150 600,90 800,30"/>
</svg>
```
Every shape inside the element draws along its length.

## Layout classes (from `theme.css`)

`.scene.center` centred · `.scene.bottom` content at the bottom · `.scene.clear` no background · `.kicker` small label · `.lead` large paragraph · `.big` hero number · `.accent`, `<em>` accent colour · `.card` · `.pill` · `.rule` · `.row` · `.col` · `.grid` (set `--cols`) · `.item` (numbered list row) · `.barrow` + `.track` + `.fill` (bar chart row; width from `--v`) · `.quote` · `svg.line`

## Units

Size everything with `calc(var(--u) * N)`: `--u` is 1% of the short side, so a layout scales to any format. `--w` and `--h` are the stage size in pixels. Avoid `vw`/`vh`: they follow the window in preview and the stage only in render.

## Custom code

For anything the attributes cannot express, draw from time. Put the script **after** `mg.js`.

```html
<section class="scene clear" id="field" data-dur="6" data-cam="none">
  <canvas id="c" width="1920" height="1080" style="position:absolute;inset:0"></canvas>
</section>
<script src="mg.js"></script>
<script>
  const ctx = document.getElementById('c').getContext('2d');
  const rnd = MG.rand(7);                                   // seeded: same dots every run
  const dots = Array.from({length: 240}, () => ({x: rnd(), y: rnd(), r: 2 + rnd() * 6, p: rnd()}));
  MG.scene('field', (t, dur) => {                           // t = seconds into this scene
    ctx.clearRect(0, 0, 1920, 1080);
    ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--accent');
    for (const d of dots) {
      const a = MG.prog(t, d.p * 2, 0.8, 'out');            // each dot's own entrance
      ctx.globalAlpha = a;
      ctx.beginPath();
      ctx.arc(d.x * 1920, d.y * 1080 + Math.sin(t * 1.2 + d.p * 6.28) * 14, d.r * a, 0, 6.2832);
      ctx.fill();
    }
  });
</script>
```

| API | Use |
|---|---|
| `MG.scene(id, (t, dur, el) => …)` | called every frame while that scene is on screen |
| `MG.frame((t, info) => …)` | called every frame with film time |
| `MG.prog(t, at, dur, ease)` | 0→1 progress of a beat, eased |
| `MG.ease.out(p)`, `MG.lerp(a, b, p)`, `MG.clamp(v, a, b)` | helpers |
| `MG.rand(seed)` | repeatable random numbers 0–1 |

The callback must set state from `t` only — never add to a value from the previous call. The renderer may ask for frames in any order.

Libraries (D3, Three.js, GSAP) work if you copy them into the project and drive them from time: build a paused GSAP timeline and call `tl.seek(t)`; call `renderer.render()` from `MG.scene`.

## Preview

Open `index.html` in any browser: play/pause (space), scrubber, time readout. Preview and render call the same code, so what you scrub is what you get.

## What the linter rejects

| Error | Fix |
|---|---|
| CSS `transition:` / `animation:` / `@keyframes` | use `data-anim` or a time callback |
| `Date.now()`, `performance.now()`, `Math.random()`, timers, free animation-frame loops | `MG.frame`, `MG.rand(seed)` |
| `<video>` | render with `--alpha`, composite with ffmpeg |
| unknown animation / easing / transition / camera name | see the tables above |
| an animation ending after its scene | lengthen `data-dur` or start earlier |

A line that must break a rule on purpose (rare) can carry the comment `mg-allow`; say why next to it.
