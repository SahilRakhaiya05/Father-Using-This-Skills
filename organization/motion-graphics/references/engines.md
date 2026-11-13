# Other engines

`mg.py` is the default because it needs no build step and renders exactly. Use another engine when the job calls for it. Commands and licences below were checked in November 2026 — **confirm against the project's own docs before relying on them**, and ask before installing anything.

## Decision table

| Situation | Engine | Why |
|---|---|---|
| Type, layout, stats, charts, overlays, most social and launch films | **mg.py** (this skill) | fastest path, 16 styles, transparent output |
| The project already uses React/Remotion; hundreds of data-driven variants; complex component reuse | **Remotion** | React component model, parametrised renders |
| GSAP timelines, video and audio clips inside the composition, HTML-first agent workflow | **HyperFrames** | seekable HTML compositions, CLI lint/preview/render |
| Equations, geometry, graphs, algorithm walk-throughs | **Manim Community** | built for mathematical animation |
| Hand-tuned TypeScript animation with a visual editor | **Motion Canvas** | generator-based timeline, live editor |
| Animation that runs inside a website or app | **Lottie / CSS / GSAP** | it is not a video; ship code or JSON |
| 3D objects, cameras, shaders | **Three.js** inside mg.py, or **Blender** | real 3D |
| Existing footage: cut, join, caption, resize | the `video-making` skill | ffmpeg work |

Stay with the engine a project already uses. Never migrate a working project unasked.

## The rule every engine shares

A frame must depend only on its frame number. No wall clock, no timers, no unseeded randomness, no network during render, fixed size and frame rate. If a library animates by itself, pause it and seek it.

## Remotion

- React components; each frame reads `useCurrentFrame()`.
- **Licence:** not a standard open-source licence. Free for individuals and for companies of up to 3 people; larger companies need a paid company licence. Tell the user this before choosing it for company work, and point them to remotion.dev/docs/license.
- Start: `npx create-video@latest` · preview: `npx remotion studio` · render: `npx remotion render <CompositionId> out.mp4`
- Official agent skills: `npx skills add remotion-dev/skills`
- Rules: animate from `useCurrentFrame()` with `interpolate()` / `spring()`; no CSS transitions or animations; wait for assets with `delayRender()`; fonts through `@remotion/google-fonts` or local files.
- Bring a style across: copy the six colour roles, the two font stacks and the motion numbers (`dur` × fps = frames, same easing family) from `assets/styles.json` into a theme object.

## HyperFrames

- Plain HTML compositions, usually with GSAP timelines that the renderer seeks. **Licence:** Apache-2.0.
- Needs Node 22+ and ffmpeg.
- Start: `npx hyperframes init my-video` · check: `npx hyperframes lint` · preview: `npx hyperframes preview` · render: `npx hyperframes render`
- Its own agent skills: `npx skills add heygen-com/hyperframes`
- Authoring: the root element carries `data-composition-id`, `data-start`, `data-duration`, `data-width`, `data-height`; clips carry `class="clip"`, `data-start`, `data-duration`, `data-track-index`. Create timelines paused — `gsap.timeline({paused: true})` — and register them on `window.__timelines` under the composition id. Do not call play.
- Choose it over mg.py when video/audio clips must live inside the composition or the team already writes GSAP.

## Manim Community

- Python; scenes are classes with a `construct` method. Manim itself is MIT-licensed.
- Draft: `manim -pql scene.py SceneName` · final: `manim -qh scene.py SceneName` (`-ql` low, `-qm` medium, `-qh` high, `-qk` 4K; `-p` opens the result)
- Needs a LaTeX install for typeset maths.
- Use it for the maths; add titles and captions on top with mg.py `--alpha` if the film needs a consistent style.

## Motion Canvas

- TypeScript; scenes are generator functions, with a browser editor for timing. MIT-licensed.
- Start: `npm init @motion-canvas@latest` · run the editor: `npm start` · render from the editor's render panel.
- Good when a person will keep hand-tuning the animation.

## Lottie, CSS, GSAP for the web

When the animation ships in a product, a video is the wrong output. Deliver a Lottie JSON (from After Effects or a Lottie editor), CSS, or GSAP code, and respect `prefers-reduced-motion`. Use mg.py only to render a preview clip of it.

## Three.js inside mg.py

Copy `three.module.js` into the project, create the renderer once, and draw from scene time:

```html
<section class="scene clear" id="orbit" data-dur="6" data-cam="none">
  <canvas id="gl" style="position:absolute;inset:0;width:100%;height:100%"></canvas>
</section>
<script src="mg.js"></script>
<script type="module">
  import * as THREE from './three.module.js';
  const renderer = new THREE.WebGLRenderer({canvas: document.getElementById('gl'), antialias: true, alpha: true, preserveDrawingBuffer: true});
  renderer.setSize(1920, 1080, false);
  const scene = new THREE.Scene(), cam = new THREE.PerspectiveCamera(40, 16 / 9, 0.1, 100);
  cam.position.z = 6;
  const mesh = new THREE.Mesh(new THREE.IcosahedronGeometry(1.6, 1), new THREE.MeshNormalMaterial({flatShading: true}));
  scene.add(mesh);
  MG.scene('orbit', t => { mesh.rotation.set(t * 0.4, t * 0.7, 0); renderer.render(scene, cam); });
</script>
```

Module scripts load after the page is parsed; register the callback at the top level of the module as shown, and confirm with `mg.py sheet` that the 3D appears. Software WebGL in headless Chromium is slow — keep geometry light and render drafts at `--scale 0.5`.

## Generated images and video clips

AI-generated stills or clips can be backgrounds or b-roll. They are assets, not the film: generate them only with a service the user has chosen and pays for, keep clips short (4–5 s), copy the files into the project, and record the tool and prompt in the delivery note. Text and numbers stay as real type rendered by the engine — never baked into a generated image.

## Handing off to an editor

Deliver ProRes 4444 with alpha (`--alpha` → `.mov`) for Premiere, After Effects, Final Cut or DaVinci Resolve, one file per graphic, named by purpose and length (`lower-third_name_6s.mov`). Include the frame rate and size in the note.
