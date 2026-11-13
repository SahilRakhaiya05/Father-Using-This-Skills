# Recipes

Each block is a complete scene. Paste it inside `<div id="stage">` (or use it as an `"html"` storyboard scene), then change the words. They take colours and fonts from the active style. Every recipe here was rendered and checked when the skill was written.

## Contents
Lower third · Logo sting · Kinetic line · Big number · Line chart · Progress steps · UI mock · Comparison · Countdown · Checklist · End card

## Lower third (render with `--alpha`)

```html
<section class="scene clear bottom" id="lower-third" data-dur="6" data-cam="none">
  <div style="display:flex;align-items:stretch;gap:calc(var(--u)*2)">
    <div style="width:calc(var(--u)*1);background:var(--accent)" data-anim="grow" data-at="0.1" data-dur="0.4" data-out="fade" data-out-at="5.4"></div>
    <div>
      <div style="font-family:var(--font-display);font-weight:700;font-size:calc(var(--u)*6);color:var(--fg)" data-anim="left" data-at="0.25" data-out="fade" data-out-at="5.3" data-cue="whoosh">Asha Rao</div>
      <div class="kicker" data-anim="left" data-at="0.4" data-out="fade" data-out-at="5.2">Head of Platform, Orbit</div>
    </div>
  </div>
</section>
```

## Logo sting

```html
<section class="scene center" id="logo-sting" data-dur="3.5" data-cam="none">
  <svg viewBox="0 0 200 200" style="width:calc(var(--u)*26);height:calc(var(--u)*26)" class="line" data-anim="draw" data-at="0.1" data-dur="1.1" data-ease="inout">
    <circle cx="100" cy="100" r="78"/><path d="M62 104 L92 134 L142 72"/>
  </svg>
  <h2 data-anim="rise" data-at="1.0" data-split="chars" data-stagger="0.04" data-cue="logo">Orbit</h2>
  <div class="kicker" data-anim="fade" data-at="1.6">Deploy without fear</div>
</section>
```

Swap the SVG for the real logo's outline paths; add `data-anim="fade"` on a filled copy after the draw to "ink" it.

## Kinetic line (word by word, one accent)

```html
<section class="scene" id="kinetic" data-dur="3.6">
  <h1 data-anim="slam" data-ease="snap" data-dur="0.3" data-at="0.1" data-split="words" data-stagger="0.22">Stop <em>waiting</em> for deploys</h1>
  <div class="rule" data-anim="bar" data-at="1.2" data-dur="0.5" data-ease="expo"></div>
</section>
```

Set `data-stagger` to the beat: at 120 BPM a beat is 0.5 s, half a beat 0.25 s.

## Big number with context

```html
<section class="scene center" id="big-number" data-dur="4.2">
  <div class="kicker" data-anim="fade" data-at="0.1">Customers in year one</div>
  <div class="big" data-anim="count" data-at="0.3" data-dur="1.3" data-ease="expo" data-to="12480" data-cue="count">0</div>
  <p class="lead" data-anim="rise" data-at="1.7">across <em>41</em> countries</p>
</section>
```

## Line chart that draws

```html
<section class="scene" id="line-chart" data-dur="5.5">
  <h2 data-anim data-at="0.1" data-split="words">Revenue <em>tripled</em></h2>
  <div style="position:relative;width:100%;height:calc(var(--u)*40)">
    <svg viewBox="0 0 1000 400" preserveAspectRatio="none" style="position:absolute;inset:0;width:100%;height:100%">
      <g stroke="currentColor" stroke-opacity="0.18" stroke-width="2">
        <line x1="0" y1="399" x2="1000" y2="399"/><line x1="0" y1="266" x2="1000" y2="266"/><line x1="0" y1="133" x2="1000" y2="133"/>
      </g>
      <polyline class="line" style="stroke:var(--accent);stroke-width:8;fill:none;stroke-linecap:round;stroke-linejoin:round" data-anim="draw" data-at="0.8" data-dur="1.8" data-ease="inout" data-cue="draw" points="0,360 200,330 400,270 600,210 800,120 1000,40"/>
    </svg>
    <div class="pill" style="position:absolute;right:0;top:0" data-anim="pop" data-at="2.6">3.1×</div>
  </div>
  <div class="row" style="width:100%;justify-content:space-between;color:var(--muted)" data-anim="fade" data-at="0.6"><span>2023</span><span>2024</span><span>2025</span><span>2026</span></div>
</section>
```

## Progress steps

```html
<section class="scene" id="steps" data-dur="6.5">
  <h2 data-anim data-at="0.1">How it works</h2>
  <div class="grid" style="--cols:3">
    <div class="card" data-anim="rise" data-at="0.6" data-cue="tick"><div class="kicker">Step 1</div><h3>Connect</h3><p>Link your repo</p></div>
    <div class="card" data-anim="rise" data-at="1.3" data-cue="tick"><div class="kicker">Step 2</div><h3>Push</h3><p>We build it</p></div>
    <div class="card" data-anim="rise" data-at="2.0" data-cue="tick"><div class="kicker">Step 3</div><h3>Ship</h3><p>Live in seconds</p></div>
  </div>
  <div class="track" style="width:100%;height:calc(var(--u)*1)"><div class="fill" style="--v:100%" data-anim="bar" data-at="0.6" data-dur="2.0" data-ease="linear"></div></div>
</section>
```

## UI mock (a product screen without a screenshot)

```html
<section class="scene center" id="ui-mock" data-dur="6">
  <div class="card" style="width:calc(var(--u)*110);padding:0;overflow:hidden;text-align:left" data-anim="scale" data-at="0.1" data-dur="0.7" data-ease="expo">
    <div style="display:flex;gap:calc(var(--u)*1);padding:calc(var(--u)*2);border-bottom:1px solid color-mix(in srgb,var(--fg) 15%,transparent)">
      <i style="width:calc(var(--u)*1.6);height:calc(var(--u)*1.6);border-radius:50%;background:var(--accent2)"></i>
      <i style="width:calc(var(--u)*1.6);height:calc(var(--u)*1.6);border-radius:50%;background:var(--muted)"></i>
      <i style="width:calc(var(--u)*1.6);height:calc(var(--u)*1.6);border-radius:50%;background:var(--muted)"></i>
    </div>
    <div style="padding:calc(var(--u)*4);display:flex;flex-direction:column;gap:calc(var(--u)*2.4)">
      <div style="font-family:var(--font-display);font-weight:700;font-size:calc(var(--u)*5);color:var(--fg)" data-anim="type" data-at="0.9" data-dur="0.9" data-cue="typing">orbit deploy --prod</div>
      <div class="track"><div class="fill" style="--v:100%" data-anim="bar" data-at="1.9" data-dur="1.4" data-ease="inout"></div></div>
      <div class="row"><span class="pill" data-anim="pop" data-at="3.4" data-cue="success">Live</span><span style="color:var(--muted)" data-anim="fade" data-at="3.6">Deployed in 4.2 s</span></div>
    </div>
  </div>
</section>
```

## Comparison (before / after)

```html
<section class="scene" id="compare" data-dur="5">
  <h2 data-anim data-at="0.1">Before and <em>after</em></h2>
  <div class="grid" style="--cols:2">
    <div class="card" data-anim="left" data-at="0.6"><div class="kicker" style="color:var(--muted)">Before</div><div class="big" style="font-size:calc(var(--u)*14);color:var(--muted)">3 min</div><p>per deploy</p></div>
    <div class="card" data-anim="right" data-at="1.3" data-cue="pop"><div class="kicker">After</div><div class="big accent" style="font-size:calc(var(--u)*14)" data-anim="count" data-at="1.5" data-dur="1.0" data-to="4.2" data-decimals="1" data-suffix=" s">0</div><p>per deploy</p></div>
  </div>
</section>
```

## Countdown

```html
<section class="scene center" id="countdown" data-dur="4.4" data-cam="none">
  <div style="display:grid;place-items:center">
    <div class="big" style="grid-area:1/1" data-anim="pop" data-dur="0.25" data-at="0" data-out="fade" data-out-at="0.8" data-out-dur="0.2" data-cue="tick">3</div>
    <div class="big" style="grid-area:1/1" data-anim="pop" data-dur="0.25" data-at="1" data-out="fade" data-out-at="1.8" data-out-dur="0.2" data-cue="tick">2</div>
    <div class="big" style="grid-area:1/1" data-anim="pop" data-dur="0.25" data-at="2" data-out="fade" data-out-at="2.8" data-out-dur="0.2" data-cue="tick">1</div>
    <div class="big accent" style="grid-area:1/1" data-anim="slam" data-dur="0.3" data-at="3" data-cue="hit">Go</div>
  </div>
</section>
```

## Checklist

```html
<section class="scene" id="checklist" data-dur="5">
  <h2 data-anim data-at="0.1">Everything included</h2>
  <div class="col">
    <div class="item" data-anim="left" data-at="0.7" data-cue="tick"><span class="n">✓</span><span>Unlimited previews</span></div>
    <div class="item" data-anim="left" data-at="1.3" data-cue="tick"><span class="n">✓</span><span>Instant rollbacks</span></div>
    <div class="item" data-anim="left" data-at="1.9" data-cue="tick"><span class="n">✓</span><span>Audit log and SSO</span></div>
  </div>
</section>
```

## End card

```html
<section class="scene center" id="end-card" data-dur="4" data-in="fade">
  <h2 data-anim data-at="0.2" data-split="words">Start free <em>today</em></h2>
  <div class="pill" data-anim="pop" data-at="1.0" data-cue="hit">orbit.example</div>
  <div class="kicker" data-anim="fade" data-at="1.5" data-loop="pulse" data-loop-amp="3" data-loop-period="2">No card needed</div>
</section>
```

## Combining

- Build each scene alone first (`--range` to its seconds) and get it right before assembling.
- Keep the same entrance for the same kind of element across scenes.
- After pasting recipes together, run `lint` and `sheet` again — combined scenes are where overlaps appear.
