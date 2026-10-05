# Research notes: what Opus 5.5 is good at, and where the web is going

Compiled 2026-10-03 for the "Threat model" gallery. Three parallel research passes:
Opus 5.5 showcases, frontier browser technology, and creative-coding craft.
Links go to the original articles.

## 1. What people build with Opus 5.5 (beyond motion films)

X itself wasn't directly readable; claims come from aggregators quoting posts. "Unverified" means a single secondhand source.

**Interactive explainers and cutaway labs: the most viral format**
- "The Plane of Focus" lens lab: focus ring, f/2 to f/16, exploded lens view. One max-effort run, 1 h 26 m, $25.66, 3.2M views. https://lens.lab.sael.net · https://runtimewire.com/article/ryan-sael-opus-5-5-interactive-camera-lens-lab
- Raptor 3 cutaway in Three.js: propellant flow through turbopumps, throttle-driven shock diamonds. https://www.airsup.ai/rocket-engine
- "Architect's Model" in Three.js + TSL: sketch, then massing, then detail. Tip: pin the Three.js version and paste the TSL docs into context. https://x.com/techartist_/status/2102503719762018434
- Trebuchet sketch turned into a ballistics sim. https://favtutor.com/claude-opus-5-5-real-examples/
- Prompt collection (atlas, tectonics, Blender volcano): https://github.com/TripoGrowthLab/awesome-opus-5-5-prompts

**WebGPU simulation and rendering**
- Tidewater: custom WebGPU FFT ocean, caustics, volumetric clouds, GTAO. https://github.com/dgreenheck/tidewater
- Splashery "Phase Fluids": MLS-MPM lava that cools to a basalt crust. https://github.com/ryanjosephkamp/splashery/pull/180
- Falling-sand alchemy (Noita benchmark): 20+ materials, self-tested in a headless browser. https://github.com/JerryLiu369/noita-benchmark
- Opus 5 procedural desert: Babylon.js WebGPU, clipmap terrain, GPU cloth. https://explainx.ai/blog/opus-5-procedural-desert-explorer-babylonjs-webgpu-july-2026

**Simulated media, and tools the model builds for itself**
- claude-paint: Rust oil-paint simulator with Kubelka–Munk layering; the model looks between strokes. https://github.com/aliceisjustplaying/claude-paint
- "Functional Emotions": WebGL2 renderer of about 60k instanced brushstrokes; 168 shots made by 7 chapter subagents. https://github.com/ledbetterljoshua/functional-emotions-video
- build123d-mcp CAD tooling; Opus 5.5 leads CADGenBench. https://experimentsin3d.substack.com/p/i-asked-claude-what-would-help-it

**Blender, games, music, design**
- Blender Python reconstruction of Market Street, San Francisco, 1906: https://x.com/alexalbert__/status/2102466523164274839 · Spiderbench: https://github.com/xikhar/spiderbench
- 42 playable Opus 5.5 games: https://github.com/theolundqvist/frontier-games · single-file SVG games with Web Audio: https://github.com/OpenVGLab/awesome-opus5.5-frontend-showcases
- Deep-house track produced by driving Ableton through MCP: https://postcutoff.com/v/yt-bitheap-tech-prescient-a-deep-house-song-made-with-op/
- Designer demos (refracting water hero, CMYK kinetic type, risograph covers): https://muz.li/blog/claude-opus-5-5-for-designers/
- 100 HTML pages from 20 parallel agents: https://github.com/MiaAI-lab/Claude-Opus-5.5-100-HTML-Files
- Video prompts (Manim, Remotion + KaTeX): https://github.com/X-RayLuan/awesome-opus-5-5-video-prompts

**Workflow techniques people share**
- Contact sheets: `ffmpeg -vf fps=2,scale=270:-1,tile=6x5`. Self-score on six points (hook in the first 2 s, readable on a phone, motion, variety, on-brand, sound sync) and list the 3 worst flaws by timestamp. https://ciyo.ai/blog/opus-5-5-video-motion-graphics-guide
- Motion blur from 4 subframes across a 180° shutter; wait two rAFs after each seek.
- Briefs: exact hex values, pinned BPM and bar counts, banned-move lists, "frame 0 = last frame" for loops.
- Storyboard first, one subagent per chapter, a director reviewing contact sheets.
- Effort: medium for tweaks, xhigh for exploration, max only for launch-critical work.
- Make checks measurable, but keep human taste in the loop: numeric pass criteria can produce work that passes and looks dull.

## 2. Frontier browser technology (versions checked 2026-10-03)

| Area | What | Status / how to load |
|---|---|---|
| In-browser AI | Transformers.js 4.3 (WebGPU, Safari 26+) | `@huggingface/transformers@4.3.0` on jsDelivr; all-MiniLM-L6-v2 int8 23 MB; `marklkelly/bert-tiny-injection-detector` int8 4.5 MB (load the `onnx/opset11/` file with ONNX Runtime Web); Prompt-Guard-2-22M 72.5 MB |
| | WebLLM 0.2.85, wllama 3.8 | `esm.run/@mlc-ai/web-llm@0.2.85` |
| | Chrome Prompt API (Gemini Nano) | Chrome 148+; needs about 22 GB of disk |
| | MediaPipe Tasks 1.0.1 | `@mediapipe/tasks-vision@1.0.1` |
| Media | WebCodecs + Mediabunny 1.61 | in-page MP4/WebM export; `mediabunny@1.61.0/dist/bundles/mediabunny.min.mjs` |
| CSS | scroll-triggered animations (146), element-scoped view transitions (147), `border-shape` (147), `text-fit` (150), anchor positioning, `sibling-index()`, `@function`, `if()` | Chrome stable 153 |
| | HTML-in-canvas | origin trial only (148–150) |
| 3D | Spark 2.3.1 procedural Gaussian splats (`constructSplats`, `textSplats`, dyno modifiers) | `@sparkjsdev/spark@2.3.1`, needs three ≥ 0.180 |
| | three.js r186 native splats; Rayzee 9.4 WebGPU path tracer; Babylon.js 9 | |
| Simulation | luma.gl MLS-MPM; webgpu-ocean; Box3D wasm 0.2; Box2D v3 wasm; Jolt 1.1 | |
| Creative | Strudel `@strudel/web` 1.3 (AGPL); Hydra 1.4; p5.js 2.3 (WebGPU); PixiJS 8.22; Motion 14; anime.js 4.5 | |
| Offline | Remotion 4.0.532 (+ in-browser renderer); Revideo 0.11; Manim CE 0.21; bpy 5.2 (Python 3.13 only) | |
| Data | deck.gl 9.4 (WebGPU), MapLibre 6 (ESM only), cosmos.gl 3.4 | |
| Security feeds | CISA KEV via the GitHub mirror (CORS open): `cdn.jsdelivr.net/gh/cisagov/kev-data@develop/known_exploited_vulnerabilities.json`, 1.77 MB, 1,733 entries, 361 known ransomware use; NVD 2.0, EPSS, OSV.dev and GitHub advisories are all CORS-open; ATT&CK STIX 54 MB | |

## 3. Creative-coding techniques worth stealing (2025–2026)

- **Real-time datamosh**: warp the previous frame with block motion vectors, add only residual detail, suppress keyframes at cuts. Codrops, Sep 2026 (https://tympanus.net/codrops/2026/09/02/breaking-the-frame-building-a-real-time-datamosh-effect-with-three-js/).
- **NTSC/VHS signal-path emulation**: YIQ conversion, chroma on a 3.58 MHz subcarrier, filtered back, giving chroma bleed and dot crawl. https://ntsc.rs/
- **CMYK halftone with rotated screens and gooey dots**: https://blog.maximeheckel.com/posts/shades-of-halftone/
- **Kuwahara painterly filter**: https://blog.maximeheckel.com/posts/on-crafting-painterly-shaders/
- **Woodblock toon, ink-wash shadows, silk weave**: Codrops "Still" (https://tympanus.net/codrops/?p=119730).
- **2D radiance cascades**: real-time global illumination from a jump-flood distance field plus cascaded probes. https://jason.today/rc
- **Volumetric god rays by post-process raymarching**: https://blog.maximeheckel.com/posts/shaping-light-volumetric-lighting-with-post-processing-and-raymarching/
- **Caustics, dispersion and procedural audio**: Codrops "Volatile Nexus" (https://tympanus.net/codrops/2026/08/31/volatile-nexus-tinkering-with-glass-caustics-cubes-and-sound-in-three-js/).
- **Atmospheric scattering**: https://blog.maximeheckel.com/posts/on-rendering-the-sky-sunsets-and-planets/
- **Depth-map relighting**, and a **fluid X-ray reveal** between two scenes (https://tympanus.net/codrops/2026/03/23/building-a-dual-scene-fluid-x-ray-reveal-effect-in-three-js/).
- **MSDF text dissolving into dust and petals**: Codrops "Gommage" (https://tympanus.net/codrops/2026/01/28/webgpu-gommage-effect-dissolving-msdf-text-into-dust-and-petals-with-three-js-tsl/).
- **Quine art**: Larva Labs "Quine", where programs typeset their own source. https://larvalabs.com/quine
- **Tweet-sized turbulence shaders** (XorDev): https://tympanus.net/codrops/?p=89119.
- **MLS-MPM fluid with screen-space rendering**: https://tympanus.net/codrops/2025/02/26/webgpu-fluid-simulations-high-performance-real-time-rendering/.
- **Particle Lenia**: https://google-research.github.io/self-organising-systems/particle-lenia/
- **Wave Function Collapse**; **progressive path tracing** (Revision 2026 4K graphics winner); **explorable explanations** in the style of Bartosz Ciechanowski.
