#!/usr/bin/env python3
"""Builds index.html, the gallery homepage, from the metadata table below.

    python3 tools/build_index.py

The page is static HTML (it works without JavaScript); scripts add the heat-diffusion title,
hover previews (out/previews/*.mp4, made by tools/previews.cjs), the list view and filters.
"""
import html, json, pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

FAMILIES = [
    ("hands", "Hands-on", "Five ways to touch a page: your hands, a liquid, a fabric, a model you can talk to, and maths you can drag."),
    ("vector", "Vector and CSS", "SVG and the browser’s own layout engine: animation elements, filters, generated geometry and 3D transforms."),
    ("shaders", "Shaders and light", "Programs that run once per pixel: light that bounces, geometry with no meshes, type as a rendering medium."),
    ("3d", "3D, physics and splats", "Scene graphs, node materials for WebGPU, rigid bodies in WebAssembly, and Gaussian splats made from code."),
    ("sim", "Simulations and games", "Thousands to millions of agents moved by noise fields, sensing rules or falling-sand chemistry."),
    ("labs", "Labs and explainers", "An interactive cutaway you can take apart, and a fact-checked documentary short."),
    ("paint", "Painting and print", "No image models: a woodblock print rendered live, and an oil painting made stroke by stroke in Python."),
    ("checks", "Models, data and proofs", "A real classifier in the tab, the real catalogue of exploited vulnerabilities, and a page that verifies its own source."),
    ("motion", "Motion, type and sound", "Storyboarded films, kinetic typography and soundtracks synthesised in the page."),
]

# slug, family, title, technology, description, image alt, badges, verbs.  First piece of a family is featured.
PIECES = [
    ("30-hands-on", "hands", "Hands on", "MediaPipe hand tracking driving a 3D game",
     "Protect the core with your bare hands: pinch threats, flick them into containment, raise a palm to shield. A mouse works too.",
     "A glowing hand skeleton raising a hexagonal shield against hot orbs", ["Camera optional"], ["Play"]),
    ("26-containment", "hands", "Containment", "WebGPU MLS-MPM fluid, 162,000 particles",
     "Stir, pour, tilt and shake a liquid. Leaked data pours in hot and cools to ice once it settles.",
     "A hot liquid sloshing up the wall of a glass tank", ["WebGPU"], ["Play"]),
    ("27-soft-perimeter", "hands", "Soft perimeter", "Tearable XPBD cloth you can grab",
     "Grab the firewall curtain, rip it open, watch hot packets pour through, then patch the tear.",
     "A torn fabric curtain with glowing packets streaming through the holes", [], ["Play"]),
    ("29-keep-the-secret", "hands", "Keep the secret", "A language model running in your browser",
     "Talk an on-device model into leaking its password through four layers of defence, and watch its confidence token by token.",
     "A chat with an in-browser model, its tokens coloured by confidence", ["Optional 290 MB model"], ["Play", "Read"]),
    ("28-curve-secret", "hands", "How a curve keeps a secret", "An explorable essay with 14 live figures",
     "Elliptic-curve cryptography taught by touch: drag points, wrap the curve onto a torus, race a brute-force search.",
     "An elliptic curve's points wrapped onto a torus", [], ["Read", "Play"]),

    ("11-approve-once", "vector", "Approve once", "Liquid glass from SVG displacement maps",
     "An agent asks to pipe a remote script into a shell. The glass sheet flows into a sandbox that runs it there instead.",
     "A liquid glass permission sheet refracting an agent's terminal", ["Best in Chromium"], ["Watch", "Play"]),
    ("01-commit-guard", "vector", "Commit guard", "Pure SVG, animated with SMIL and filters",
     "An AI pair programmer writes a query, flags the SQL injection and patches it while a shield morphs from alert to lock.",
     "A code editor with a SQL injection line glowing hot beside a warning shield", [], ["Watch"]),
    ("06-secure-pipeline", "vector", "Secure pipeline", "Procedural isometric SVG",
     "Agent-written changes ride a conveyor through a policy gate; clean ones ship signed, flagged ones go to quarantine.",
     "An isometric pipeline of stations with tokens moving along a track", [], ["Watch", "Play"]),
    ("12-defense-in-depth", "vector", "Defense in depth", "Pure CSS 3D driven by scrolling",
     "Scroll down through six layers of an agent’s security while an attack slips past some of them and breaks on the sandbox.",
     "Rings of panels around a tunnel, one ring per security layer", ["Scroll"], ["Play"]),

    ("17-dark-repo", "shaders", "Dark repo", "2D global illumination with radiance cascades",
     "A repository at night, lit only by freshly typed code, until a reviewer’s torch finds the SQL injection.",
     "A floor plan of a codebase lit by soft light, one room glowing red", [], ["Watch", "Play"]),
    ("03-cipher-lock", "shaders", "Cipher lock", "One GLSL shader, raymarched distance fields",
     "A padlock opens and locks while a thermal scan sorts the data blocks around it into trusted and quarantined.",
     "A raymarched padlock on a field of data blocks", [], ["Watch"]),
    ("10-worm", "shaders", "Worm", "ASCII glyph atlas with Bayer dithering",
     "A worm spelled out in its own source code burrows from rack to rack; a lens shows the 3D render underneath.",
     "A data centre drawn in ASCII characters with a worm made of code", [], ["Watch", "Play"]),

    ("16-codebase-nebula", "3d", "Codebase nebula", "Procedural Gaussian splats with Spark",
     "A repository as a nebula of 264,000 splats; the camera dives from galaxy scale into one legible line of vulnerable code.",
     "Lines of code made of glowing splats, one line white-hot", [], ["Watch"]),
    ("09-unsafe-eval", "3d", "Unsafe eval", "Three.js WebGPU renderer with TSL",
     "eval(userInput) shatters into hot glass and cools as it reassembles into JSON.parse(userInput).",
     "3D text shattering into hot glass shards around a cold core", [], ["Watch"]),
    ("13-transitive", "3d", "Transitive", "Rapier physics compiled to WebAssembly",
     "A poisoned update to one tiny dependency topples the tower. Then the deterministic physics plays it backwards.",
     "A tower of labelled dependency blocks toppling", [], ["Watch"]),
    ("02-zero-trust-mesh", "3d", "Zero-trust mesh", "Three.js with custom shaders and bloom",
     "Cold traffic flows between an agent’s services while hostile packets break against a hex shield.",
     "A glowing service mesh inside a hexagonal shield", [], ["Watch", "Play"]),

    ("08-threat-hunters", "sim", "Threat hunters", "WebGPU compute: 1.5 million physarum agents",
     "A living web of hunting agents re-plumbs itself toward each new anomaly and cools it. Click to drop a honeypot.",
     "A vein-like network converging on a hot anomaly", ["WebGPU"], ["Watch", "Play"]),
    ("05-token-swarm", "sim", "Token swarm", "24,000 hand-written WebGL2 particles",
     "Tokens run hot while in flight, then cool into braces, a network, a shield, a lock and a word.",
     "Particles forming a shield, hot ones still streaming in", [], ["Watch"]),
    ("23-sandbox", "sim", "Sandbox", "A playable falling-sand game",
     "Data piles, malware eats it, ransomware burns it into locked crystal, and patch water steams the fire out.",
     "Pixel bins of data, malware and burning ransomware", ["Playable"], ["Play"]),

    ("24-security-key", "labs", "Why a security key can’t be phished", "Interactive 3D cutaway lab",
     "Take a security key apart, follow a real sign-in through its chips, then watch a lookalike site’s request die in the secure element.",
     "A cutaway security key chip glowing hot where a phishing request fails", [], ["Play", "Read"]),
    ("25-five-hundred-ms", "labs", "Five hundred milliseconds", "Remotion: React rendered to MP4",
     "The xz-utils backdoor, from a patient takeover to the half-second delay one engineer refused to ignore.",
     "A frame from an explainer about the xz backdoor", ["Sound"], ["Watch", "Listen"]),

    ("18-thirty-six-views", "paint", "Thirty-six views of the firewall", "Woodblock-print rendering in real time",
     "After Hokusai: a great wave of packets breaks on the firewall, and each print presses itself block by block.",
     "A woodblock-style great wave made of packets", [], ["Watch"]),
    ("19-vanitas", "paint", "Memento expirare", "An oil painting made by Python and numpy",
     "A vanitas still life for the age of credentials, painted stroke by stroke without an image model.",
     "A painted still life with a book, candle, hourglass and a key with a red tag", ["Python"], ["Watch", "Play"]),

    ("21-known-exploited", "checks", "Known exploited", "Live CISA KEV data, D3 and a Strudel score",
     "All 1,733 vulnerabilities CISA has seen exploited, 361 of them by ransomware, played as a live-coded track.",
     "A beeswarm timeline of exploited vulnerabilities", ["Sound"], ["Read", "Listen", "Play"]),
    ("15-injection-radar", "checks", "Injection radar", "Transformers.js and ONNX Runtime in the page",
     "Untrusted text streams past a real prompt-injection classifier onto a map of meaning. Paste your own.",
     "A thermal radar of text chunks with injections clustered hot", ["54 MB of models"], ["Play", "Watch"]),
    ("20-integrity", "checks", "Integrity", "A quine and the Web Crypto API",
     "The page rebuilds its exact source, hashes it and shows its own fingerprint. Flip one bit and half the hash changes.",
     "Tiny source-code glyphs with a scattered ring of hash bits", [], ["Play", "Watch"]),

    ("07-zero-day-intro", "motion", "Zero day", "Demoscene intro: WebGL2 and Web Audio",
     "A one-minute intro where every pixel and every note comes from the page. A patch slams shut on the beat.",
     "A demoscene frame with a hexagonal patch reading Patched", ["Sound"], ["Watch", "Listen"]),
    ("22-prompt-injected-1989", "motion", "So you’ve been prompt-injected (1989)", "Composite-video emulation, FM synthesis, WebCodecs",
     "A deadpan training tape about a 2026 problem. Rewind it and the memo’s hidden instruction tears into view.",
     "A CRT showing a memo with a hidden instruction glowing through tracking noise", ["Sound"], ["Watch", "Listen"]),
    ("04-injection-film", "motion", "Hidden instruction", "A Canvas 2D film, every frame a function of time",
     "A prompt injection hidden in a pull request, caught by a guard model, in 24 seconds.",
     "A frame showing a hidden instruction in a pull request", [], ["Watch"]),
    ("14-rotate-your-keys", "motion", "Rotate your keys", "GSAP: SplitText, ScrambleText, MorphSVG, Physics2D",
     "A leaked key is caught within a minute, smashed into a heap of characters, revoked and replaced.",
     "A leaked access key glowing white-hot", [], ["Watch"]),
]

FILMS = [
    ("out/zero-day.mp4", "out/thumbs/07-zero-day-intro.webp", "Zero day", "1:04, with sound",
     "The demoscene intro, captured frame by frame and muxed with its synthesised soundtrack."),
    ("out/five-hundred-ms.mp4", "out/thumbs/25-five-hundred-ms.webp", "Five hundred milliseconds", "1:29, with sound",
     "The xz-utils story as a Remotion documentary, every frame a React component."),
    ("out/hidden-instruction.mp4", "out/thumbs/04-injection-film.webp", "Hidden instruction", "0:24",
     "The Canvas 2D film, rendered by four headless workers in 88 seconds."),
    ("out/vanitas-timelapse.mp4", "out/thumbs/19-vanitas.webp", "Memento expirare, being painted", "0:42",
     "Every stroke of the Python painting, from the first wash to the varnish."),
]

SOURCES = [
    ("https://explainx.ai/blog/how-opus-5-5-viral-videos-are-made-code-not-diffusion-2026", "How Opus 5.5 viral videos are made"),
    ("https://rar.design/posts/claude-opus-5-5-animation-guide", "Claude Opus 5.5 animation guide"),
    ("https://ciyo.ai/blog/opus-5-5-video-motion-graphics-guide", "Opus 5.5 motion-graphics guide"),
    ("https://hermes-ai.net/zh/ai-models/claude-opus-5-5/case/2102893186330841502/", "The 280 KB demoscene intro"),
    ("https://lens.lab.sael.net", "The Plane of Focus lens lab"),
    ("https://jason.today/rc", "Radiance cascades, explained"),
    ("https://sparkjs.dev/docs/procedural-splats/", "Procedural splats in Spark"),
    ("https://github.com/huggingface/transformers.js/releases", "Transformers.js releases"),
    ("https://blog.maximeheckel.com/posts/the-art-of-dithering-and-retro-shading-web", "The art of dithering"),
    ("https://blog.logrocket.com/how-create-liquid-glass-effects-css-and-svg/", "Liquid glass with CSS and SVG"),
    ("https://ntsc.rs/", "NTSC and VHS signal emulation"),
    ("https://larvalabs.com/quine", "Quine by Larva Labs"),
    ("https://www.cisa.gov/known-exploited-vulnerabilities-catalog", "CISA’s Known Exploited Vulnerabilities catalog"),
    ("https://research.swtch.com/xz-timeline", "Timeline of the xz attack"),
    ("https://www.w3.org/TR/webauthn-3/", "Web Authentication Level 3"),
    ("https://ciechanow.ski/moon/", "Bartosz Ciechanowski’s explorables"),
]

e = lambda s: html.escape(s, quote=True)


def layout(n):
    """Column/row spans per position for a family of n pieces (12-column grid)."""
    if n == 2: return [(6, 1), (6, 1)]
    if n == 3: return [(8, 2), (4, 1), (4, 1)]
    if n == 4: return [(6, 1)] * 4
    if n == 5: return [(8, 2), (4, 1), (4, 1), (6, 1), (6, 1)]
    return [(4, 1)] * n


def tile(p, span, rows, side_flag=False):
    slug, fam, title, how, desc, alt, badges, verbs = p
    no = slug.split("-")[0]
    feature = rows > 1
    side = side_flag
    b = "".join(f'<span class="badge">{e(x)}</span>' for x in badges)
    desc_html = e(desc).replace("eval(userInput)", "<code>eval(userInput)</code>").replace("JSON.parse(userInput)", "<code>JSON.parse(userInput)</code>")
    return f'''        <a class="tile{' feature' if feature else ''}{' side' if side else ''}" href="pieces/{slug}.html" style="--span:{span};--rows:{rows}"
           data-no="{no}" data-title="{e(title)}" data-how="{e(how)}" data-family="{fam}" data-verbs="{' '.join(verbs)}" data-badges="{e('|'.join(badges))}">
          <span class="media" data-preview="out/previews/{slug}.mp4">
            <img src="out/thumbs/{slug}.webp" alt="{e(alt)}" loading="lazy" decoding="async" width="1440" height="900">
            {f'<span class="badges">{b}</span>' if b else ''}
          </span>
          <span class="cap">
            <span class="t">{e(title)}</span>
            <span class="how">{e(how)}</span>
            <span class="desc">{desc_html}</span>
          </span>
        </a>'''


def webp_thumbs():
    """Gallery thumbnails ship as WebP (~10x smaller than the PNG captures, which stay local)."""
    from PIL import Image
    for png in sorted((ROOT / "out" / "thumbs").glob("*.png")):
        webp = png.with_suffix(".webp")
        if not webp.exists() or webp.stat().st_mtime < png.stat().st_mtime:
            Image.open(png).convert("RGB").save(webp, "WEBP", quality=82, method=6)


def build():
    webp_thumbs()
    fam_html = []
    for fid, name, blurb in FAMILIES:
        items = [p for p in PIECES if p[1] == fid]
        spans = layout(len(items))
        has_feature = spans and spans[0][1] > 1
        tiles = "\n".join(tile(p, *s, side_flag=has_feature and i in (1, 2)) for i, (p, s) in enumerate(zip(items, spans)))
        fam_html.append(f'''      <section class="family" id="f-{fid}" data-family="{fid}" aria-labelledby="h-{fid}">
        <header class="fam-head">
          <h2 id="h-{fid}">{e(name)}</h2>
          <p>{e(blurb)}</p>
          <span class="count">{len(items)} pieces</span>
        </header>
        <div class="grid">
{tiles}
        </div>
      </section>''')
    chips = ['<button type="button" class="chip" data-filter="all" aria-pressed="true">All <span>30</span></button>'] + [
        f'<button type="button" class="chip" data-filter="{fid}" aria-pressed="false">{e(name)} <span>{sum(1 for p in PIECES if p[1] == fid)}</span></button>'
        for fid, name, _ in FAMILIES]
    films = "\n".join(
        f'''          <button type="button" class="film{' on' if i == 0 else ''}" data-src="{src}" data-poster="{poster}" aria-pressed="{'true' if i == 0 else 'false'}">
            <img src="{poster}" alt="" loading="lazy"><span class="ft">{e(t)}</span><span class="fm">{e(meta)}</span><span class="fd">{e(d)}</span>
          </button>''' for i, (src, poster, t, meta, d) in enumerate(FILMS))
    sources = "\n".join(f'        <li><a href="{u}">{e(t)}</a></li>' for u, t in SOURCES)
    page = TEMPLATE.replace("{{FAMILIES}}", "\n".join(fam_html)).replace("{{CHIPS}}", "\n          ".join(chips)) \
        .replace("{{FILMS}}", films).replace("{{FILM0_SRC}}", FILMS[0][0]).replace("{{FILM0_POSTER}}", FILMS[0][1]) \
        .replace("{{SOURCES}}", sources)
    (ROOT / "index.html").write_text(page)
    print("wrote index.html with", len(PIECES), "pieces")


TEMPLATE = (ROOT / "tools" / "index.template.html").read_text()

if __name__ == "__main__":
    build()
