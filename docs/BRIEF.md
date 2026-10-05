# Threat model: AI × code × security graphics

A small gallery of single-file HTML graphics. Each piece shows a **different rendering
technique** (the ones behind the viral 2026 "Opus 5.5 code-rendered" motion pieces) on one theme:
**AI writing code, and the security around it.**

## The research, condensed (why the pieces are built this way)

The viral work isn't diffusion video. Each piece is **code that paints frames**:

1. **Single self-contained HTML file**, rendered with SVG, Canvas 2D, WebGL or Three.js.
2. **Every frame is a pure function of time `t`.** Same `t` → same frame. No carried state between
   frames, no unseeded randomness (`Math.random` is banned; use a seeded PRNG such as mulberry32).
   This makes frames scrubbable, parallel-renderable and verifiable.
3. **Storyboard / keyframe tables first**: shots with start/end times, easing functions, then code.
4. **Verification by contact sheet**: render specific `t` values headlessly, look at them, fix, repeat.
5. **Motion craft**: anticipation and overshoot, objects morph instead of fading, kinetic type where
   characters settle into colour over ~13 frames, a single strong hook in the first second.
6. **Rich vector/shader tricks**: SVG `feTurbulence` + `feDisplacementMap`, SMIL path morphing,
   stroke-dash drawing, SDF raymarching, fresnel shaders, bloom, instancing, curl-noise particles.

## Visual concept: trust is temperature

Every piece encodes trust like a **thermal camera** (the FLIR "ironbow" palette):
**verified / trusted things are cold** (deep blue → ice), **hostile / untrusted things run hot**
(violet → magenta → orange → white-hot). Neutral structure is steel-violet line work.
The colour always *means* something; never use heat colours decoratively.

### Tokens (use these exact values)

```css
:root{
  --void:   #100C2A;  /* base background: indigo night (not black) */
  --deep:   #1B1747;  /* panels, structure fills */
  --steel:  #4E5A8C;  /* lines, grids, neutral structure */
  --mist:   #8C93C4;  /* secondary text */
  --ice:    #9BE8FF;  /* TRUSTED / verified */
  --frost:  #E8F7FF;  /* primary text, white-cold highlights */
  /* ironbow heat ramp, low → high threat */
  --heat-0: #3A0F6B;
  --heat-1: #9B1D8F;
  --heat-2: #F0306A;  /* HOSTILE */
  --heat-3: #FF7A2F;  /* warning */
  --heat-4: #FFD36B;
  --heat-5: #FFF6E0;  /* white-hot */
}
```

Cold ramp for "trust level" if you need one: `#1B1747 → #2F4FA8 → #4FA3E0 → #9BE8FF → #E8F7FF`.
In shaders, implement `ironbow(x)` (0..1) as a piecewise-linear lookup of the heat ramp, and
`coldbow(x)` from the cold ramp.

### Type

- **Martian Mono** (variable: `wdth` 75–112.5, `wght` 100–800) for titles and any code.
  Titles: expanded width (`font-stretch: 112.5%`), light weight (200–300). Code: normal width, 400.
  Treat its width/weight axes as animatable material where it fits.
- **Schibsted Grotesk** (400/500/600) for notes and UI text.
- Load: `<link href="https://fonts.googleapis.com/css2?family=Martian+Mono:wdth,wght@75..112.5,100..800&family=Schibsted+Grotesk:wght@400;500;600&display=swap" rel="stylesheet">`
- When drawing text in canvas/SVG/WebGL, wait for `document.fonts.ready` before rasterising.

### Writing rules (these are enforced)

- Sentence case everywhere. **No all-caps labels**, no tracked-out eyebrow text above headings.
- No `A · B · C` middle-dot meta strings, no `WORD — fragment` labels, no `→` appended to links.
- Plain, specific words. Code shown on screen must be **real, plausible code** (Python/TS),
  and the vulnerability shown must be a real class (SQL injection, prompt injection, secret
  exfiltration, dependency confusion, etc.) with a real fix.

## Shared page contract (every piece)

File lives in `pieces/NN-name.html`. Self-contained; the only external resources allowed are
Google Fonts and `https://cdn.jsdelivr.net/npm/...` (e.g. three@0.170.0 via an importmap).

1. **Full-viewport graphic.** `body` has `background: var(--void)`, no scrollbars, no horizontal
   overflow. Canvas resizes on window resize; cap devicePixelRatio at 2.
2. **Determinism hooks** (required, the capture tool depends on them):
   - `window.__seek(t)`: paint exactly the frame for time `t` (seconds) and **pause** the loop.
   - `window.__play()`: resume real-time playback from the current `t`.
   - URL `?t=3.2` starts paused on that frame.
   - Interactive input (drag, hover) may perturb the live view, but `__seek` must still give a
     deterministic frame (ignore/reset interaction state when seeking).
3. **Reduced motion**: if `prefers-reduced-motion: reduce`, start paused on a representative
   frame and show the play button state accordingly.
4. **Notes card** (consistent across pieces). Copy this markup/CSS verbatim, then fill it in:

```html
<aside class="notes" id="notes" aria-label="About this piece">
  <h1>Piece title</h1>
  <p>One sentence: what you are looking at, in plain words.</p>
  <ul class="tech">
    <li>Technique one, specific (e.g. "SMIL path morphing between three shield shapes")</li>
    <li>Technique two</li>
    <li>Technique three (3–5 items total)</li>
  </ul>
  <div class="notes-actions">
    <a href="../index.html">Back to gallery</a>
    <button type="button" id="playpause" aria-pressed="false">Pause</button>
    <button type="button" id="hide-notes">Hide notes</button>
  </div>
</aside>
<button type="button" class="show-notes" id="show-notes" hidden>Show notes</button>
```

```css
.notes{position:fixed;left:16px;bottom:16px;max-width:min(380px,calc(100vw - 32px));
  padding:16px 18px 14px;background:rgba(16,12,42,.72);backdrop-filter:blur(14px) saturate(1.2);
  -webkit-backdrop-filter:blur(14px) saturate(1.2);border:1px solid rgba(140,147,196,.22);
  border-radius:14px;color:var(--frost);font:400 14px/1.5 "Schibsted Grotesk",system-ui,sans-serif;z-index:10}
.notes h1{margin:0 0 6px;font:250 20px/1.15 "Martian Mono",ui-monospace,monospace;font-stretch:112.5%;letter-spacing:-.01em}
.notes p{margin:0 0 10px;color:var(--mist)}
.notes .tech{margin:0 0 12px;padding-left:18px;color:var(--frost);font-size:13px}
.notes .tech li{margin:2px 0}
.notes-actions{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
.notes-actions a,.notes-actions button,.show-notes{font:500 13px/1 "Schibsted Grotesk",system-ui,sans-serif;
  color:var(--frost);background:rgba(78,90,140,.25);border:1px solid rgba(140,147,196,.35);
  border-radius:999px;padding:8px 12px;text-decoration:none;cursor:pointer}
.notes-actions a:hover,.notes-actions button:hover,.show-notes:hover{background:rgba(155,232,255,.16)}
:focus-visible{outline:2px solid var(--ice);outline-offset:2px}
.show-notes{position:fixed;left:16px;bottom:16px;z-index:10}
@media (max-width:600px){.notes{font-size:13px}.notes .tech{display:none}}
```

   Behaviour: `H` key toggles notes; `Space` toggles play/pause (unless focus is on a button);
   the play/pause button label reads "Pause"/"Play" and its `aria-pressed` reflects paused state.
   On narrow screens (<600px) the technique list hides; the graphic must still compose well
   at 390×844 (mobile portrait) — re-frame the camera/layout, don't just shrink.
5. **Performance**: hold 60fps on a laptop. Prefer instancing, typed arrays, batching by colour.
6. **No console errors.**

## Verification (do this, repeatedly)

A capture tool exists: `node tools/shot.cjs <file.html> <t1,t2,...> [--w=1280 --h=800] [--out=out/shots/name]`.
It loads the page headlessly (WebGL via SwiftShader works), calls `window.__seek(t)` for each
time, writes PNGs, and prints console logs/page errors. Look at the PNGs with the Read tool.

- Desktop: `--w=1440 --h=900` at 4–6 times spread across the loop.
- Mobile: `--w=390 --h=844` at 2 times.
- Use `--out=out/shots/NN-name` (desktop) and `--out=out/shots/NN-name-m` (mobile) prefixes.
- Iterate until it is genuinely striking, legible, and on-brief. Critique each frame honestly:
  composition, hierarchy, colour meaning, legibility of code text, empty/awkward areas, clipping.
- SwiftShader is slow; if a shader piece times out, reduce internal resolution for the capture
  only (e.g. honour a `?q=low` param), never by making the real piece look worse.

Finally save one **hero frame** for the gallery thumbnail: `out/thumbs/NN-name.png` at 1440×900
(the strongest single frame). Create `out/thumbs/` if missing.

---

# Round two: more technologies, more nerve

Round one covered: SMIL/SVG filters, Three.js WebGL + bloom, GLSL SDF raymarching, a Canvas 2D
film, WebGL2 particles, procedural isometric SVG. **Round two must not repeat those as the
headline technique.** Each new piece leads with a different technology found in research:

- **Demoscene**: one HTML file where every pixel *and every sound* is procedural (the viral
  zero-direction Opus 5.5 demo was a 280 KB demoscene intro). Web Audio synthesis, beat-synced shaders.
- **WebGPU compute** (WGSL): agent simulations like physarum, with millions of agents.
- **Three.js WebGPURenderer + TSL** (three@0.186.1: `three/webgpu` → `build/three.webgpu.js`,
  `three/tsl` → `build/three.tsl.js`); TSL compiles to WGSL, or GLSL on the WebGL2 fallback.
- **Post-processing as art**: ASCII glyph-atlas rendering, ordered Bayer dithering, palette quantisation.
- **Liquid glass**: SVG `feDisplacementMap` refraction applied to the backdrop (`backdrop-filter: url(#f)`).
- **Pure CSS 3D + scroll-driven animations**: `animation-timeline: scroll()/view()`, `@property`,
  CSS trig functions, `transform-style: preserve-3d`, with no animation JS.
- **Deterministic physics**: Rapier (Rust → WASM, bit-exact deterministic) + Three.js.
- **GSAP 3.15 timelines** (all plugins free since the Webflow acquisition): SplitText,
  ScrambleText, MorphSVG, Physics2D.

## Creative bar

Round one was polished. Round two should also be **surprising**. Give every piece **one
unforgettable moment** — the frame people would screenshot and share — and build the piece
around it. Prefer wit and a clear idea over generic "cyber" decoration (no binary rain, no
hooded hackers, no padlock-on-circuit-board stock imagery). Real security concepts, named
accurately, are where the ideas come from.

## Contract additions (round two)

Everything in the shared page contract still applies (notes card, palette, fonts, writing
rules, `__seek`/`__play`, `?t=`, reduced motion, mobile, no console errors). Additions:

- **Stateful simulations** (physics, physarum, fluids): `__seek(t)` must still be deterministic,
  by **re-simulating from the seeded initial state with a fixed timestep** up to `t`. Loop the
  piece on a fixed period so `t` is taken modulo the period and re-simulation stays bounded.
  Live playback may step incrementally, but it must use the same fixed timestep so it matches.
- **Audio**: browsers block autoplay, so show a clear "Play with sound" control and start audio only
  after a user gesture. Visuals stay a pure function of `t`, and `__seek` works silently. When
  audio is playing, drive `t` from the audio clock so picture and sound stay locked.
- **Scroll-driven pieces**: `__seek(t)` maps `t` to a scroll position (document the mapping) and
  waits a frame for styles to apply.
- **Timeline libraries** (GSAP): build one master timeline; `__seek(t)` = `tl.pause().seek(t)`.
- **Fallbacks**: if the headline technology is missing (no WebGPU, no `backdrop-filter: url()`),
  show a graceful, still-beautiful fallback plus one plain sentence in the notes card saying what
  the viewer is missing. Never a blank screen.

## Tools (updated)

`node tools/shot.cjs <file> <times> [--w --h] [--q=low] [--query=a=1&b=2] [--clean] [--name=exact.png]`
- `--clean` hides the notes card (use it for the gallery thumbnail).
- WebGPU works headless here (SwiftShader adapter), but it is slow, so use `--q=low` for captures.
- Gallery thumbnail: `node tools/shot.cjs pieces/NN-name.html <hero t> --w=1440 --h=900 --clean --name=out/thumbs/NN-name.png`

---

# Round three: new horizons

Research for this round is in `docs/RESEARCH.md` (read the section relevant to your piece);
saved tutorial texts are in `docs/research/`. Round three adds formats the research showed
Opus 5.5 is known for: **interactive cutaway labs, falling-sand games, simulated paint,
in-page AI models, real data, Gaussian splats, global illumination, NPR print looks,
analog-signal emulation, offline Python and React video pipelines**.

## Creative bar (unchanged, plus a rubric)

Every piece still needs one unforgettable moment. Before you finish, score your own contact
sheet 1–5 on: **hook in the first 2 seconds, readable on a phone, motion quality, variety,
on-brand (palette/type/meaning), sound sync (if any)**. Then list your **3 worst flaws by
timestamp** and fix them. Repeat until no score is below 4.

## Contract additions (round three)

- **Video-backed pieces** (an offline renderer makes an MP4/PNG; the HTML page presents it):
  the page still has the notes card, palette and fonts; `__seek(t)` sets `video.currentTime = t`,
  waits for `seeked`, and pauses; `__play()` plays. Large binary outputs go in `out/`.
- **Offline pipelines** (Python, Remotion): keep the source in the repo (e.g. `tools/…py`,
  `remotion/`), make the render reproducible with one command, document it in the notes card
  and at the top of the source file. Seed all randomness.
- **Network-loaded models or data** (Transformers.js models, live security feeds): show
  loading progress, cache results so `__seek` is deterministic and fast, and ship an
  **embedded fallback** (precomputed results / a compact data snapshot) so the piece still
  works offline or when a CDN fails. Say in the notes card which one the viewer is seeing.
- **Real-world facts** (CVE details, incident timelines, protocol behaviour): verify against
  primary sources (vendor advisories, the original disclosure, specs), keep claims modest and
  specific, and put 1–3 source links in the notes card. No speculation presented as fact.
- **Licences**: if you load an AGPL/custom-licence library from a CDN, name it in the notes card.
- **Games / interactive labs**: an attract mode plays a deterministic scripted session
  (re-simulated from a seed on `__seek`); real input takes over on the first interaction and
  hands back to attract mode after ~10 s idle.
- Tool reminder: `node tools/shot.cjs <file> <times> [--w --h] [--q=low] [--query=a=1&b=2] [--clean] [--name=…]`.
  Contact sheet from a video: `ffmpeg -i in.mp4 -vf "fps=1,scale=320:-1,tile=6x4" -frames:v 1 sheet.png`.

---

# Round four: hands-on

Five pieces where **the interaction itself is the extraordinary thing**. The AI × security theme
is only a light skin (titles, copy, colour meaning); the technology and the feel of touching it
lead. Each piece uses a **different input modality**: pour/stir a fluid, grab/tear cloth,
drag through an explorable explanation, talk to a real in-browser model, and gesture with your
hands through the camera.

## Interaction quality bar

- **First 3 seconds**: the viewer must immediately understand what they can do — a short,
  plain hint near the action ("Drag to stir. Click to pour."), cursor changes, a visible
  affordance; the hint fades after first use.
- **Feel**: input → response within one frame; physically plausible inertia; satisfying
  feedback (sound only if it really adds, never autoplaying; `navigator.vibrate` on mobile
  where it helps). Touch, mouse and keyboard all work (keyboard: at least a way to trigger the
  main actions and to reset).
- **Controls**: few, well-labelled, sentence case; a "Reset" always exists.
- **Performance**: hold 60 fps on a mid laptop; adaptive quality; never freeze the main thread
  for long loads without progress UI.
- **Permissions** (camera): never request on load. Ask only after an explicit click on a
  clear button that explains what happens ("Use your camera for hand tracking. Video stays on
  this device."). Always offer the non-camera alternative.
- **Big downloads** (models): show size before downloading, ask for a click to start, show
  progress, cache, and keep a meaningful experience available without the download.

## Contract for interactive pieces

Everything in earlier sections still applies. The attract mode (scripted, deterministic,
re-simulated from a seed on `__seek`) exists to show *how to interact*: animate a ghost
cursor/hand performing the interactions. Real input takes over immediately; attract mode
returns after ~12 s idle. Verification must include **real interaction tests** via
Playwright (mouse/touch events, keyboard, typed text), not just attract-mode frames.
