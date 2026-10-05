# Threat model

**Live: https://andreidev.github.io/threat-model/**

Thirty pieces about AI that writes code, and the security around it. Every pixel and every
sound is made by code, with no image or video models, and each piece leads with a different
web technology. Colour means trust throughout, like a thermal camera: trusted things run
cold, hostile things run hot.

Everything runs in the browser. There is no server: open `index.html`, or serve the folder
with any static host. Libraries, fonts and models load from public CDNs (jsDelivr, Google
Fonts, Hugging Face, Google's MediaPipe bucket).

## The pieces

| Family | Pieces |
|---|---|
| Hands-on | Hands on (MediaPipe hand tracking) · Containment (WebGPU MLS-MPM fluid) · Soft perimeter (tearable XPBD cloth) · Keep the secret (a language model in the browser) · How a curve keeps a secret (explorable essay) |
| Vector and CSS | Approve once (SVG liquid glass) · Commit guard (SMIL) · Secure pipeline (procedural isometric SVG) · Defense in depth (CSS 3D, scroll-driven) |
| Shaders and light | Dark repo (radiance cascades) · Cipher lock (raymarched SDFs) · Worm (ASCII and dithering) |
| 3D, physics and splats | Codebase nebula (Gaussian splats) · Unsafe eval (Three.js WebGPU + TSL) · Transitive (Rapier) · Zero-trust mesh (Three.js) |
| Simulations and games | Threat hunters (WebGPU physarum) · Token swarm (WebGL2 particles) · Sandbox (falling sand) |
| Labs and explainers | Why a security key can’t be phished (3D cutaway) · Five hundred milliseconds (Remotion) |
| Painting and print | Thirty-six views of the firewall (woodblock rendering) · Memento expirare (oil painting in Python) |
| Models, data and proofs | Known exploited (CISA KEV + Strudel) · Injection radar (Transformers.js) · Integrity (a quine) |
| Motion, type and sound | Zero day (demoscene intro) · So you’ve been prompt-injected (1989) · Hidden instruction (Canvas film) · Rotate your keys (GSAP) |

Some pieces need more than a modern browser: WebGPU (Containment, Threat hunters; both
fall back to WebGL2), a Chromium browser for real refraction (Approve once), a camera
(Hands on; a mouse works too), or an optional model download (Keep the secret, Injection radar).

## How they’re made

Every piece follows the workflow behind the viral code-rendered motion work of 2026:

1. **Storyboard first**: timings, easing and palette before drawing code.
2. **Frames are functions of time**: `window.__seek(t)` paints exactly the frame for `t`;
   randomness is seeded and simulations replay from a seed.
3. **Contact sheets**: a headless browser seeks to chosen moments, on the real GPU, and
   saves images to review.
4. **Capture and encode**: frames render in parallel and ffmpeg stitches them.

The design brief is in [`docs/BRIEF.md`](docs/BRIEF.md) and the research in
[`docs/RESEARCH.md`](docs/RESEARCH.md).

## Tools

Needs Node with a global Playwright install, Python 3 with Pillow and numpy, and ffmpeg.

```sh
node tools/shot.cjs pieces/02-zero-trust-mesh.html 1,4,8 --w=1440 --h=900   # frames at any times
node tools/perf.cjs                     # frame rates on the real GPU
node tools/previews.cjs                 # the homepage hover loops
node tools/render-film.cjs --workers=4  # Hidden instruction to MP4
node tools/render-intro.cjs             # Zero day to MP4, with its synthesised audio
python3 tools/paint_vanitas.py          # the oil painting and its timelapse
cd remotion && npm install && npm run render   # Five hundred milliseconds
python3 tools/build_index.py            # this homepage
```

## Credits and licences

Built by Claude Opus 5.5 agents in Claude Code. Third-party code is loaded from CDNs under
its own licence; notably Strudel (AGPL-3.0, in Known exploited) and Remotion (its own licence,
free for individuals and small teams; used only to render). Fonts are under the SIL Open
Font License (see `remotion/public/fonts/LICENSE.md`). The vulnerability data is CISA’s
public Known Exploited Vulnerabilities catalog.
