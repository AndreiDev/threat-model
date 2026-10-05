// Synthesises the soundtrack for "Five hundred milliseconds" into public/soundtrack.wav.
// No samples: additive pads, sine ticks and seeded noise. Cue times come from src/cues.json,
// the same file the composition reads, so picture and sound share one clock.
//   node scripts/make-audio.mjs
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const cues = JSON.parse(readFileSync(join(here, "../src/cues.json"), "utf8"));
const SR = 48000;
const N = Math.round(cues.duration * SR);
const L = new Float32Array(N);
const R = new Float32Array(N);
const TAU = Math.PI * 2;

// ---- helpers -----------------------------------------------------------------------------
function mulberry32(seed) {
  let a = seed | 0;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
const clamp01 = (x) => (x < 0 ? 0 : x > 1 ? 1 : x);
const prog = (t, a, b) => clamp01((t - a) / (b - a));
const easeOut = (x) => 1 - (1 - x) ** 3;
const easeInOut = (x) => (x < 0.5 ? 4 * x * x * x : 1 - (-2 * x + 2) ** 3 / 2);
const add = (i, l, r) => { if (i >= 0 && i < N) { L[i] += l; R[i] += r; } };

// Same function as LatencyMeter.meterValue, so ticks land on the frames where marks are crossed.
const meterValue = (t, c) => {
  if (t <= c.t0) return 0;
  if (t < c.tUsual) return c.usual * easeOut(prog(t, c.t0, c.tUsual));
  if (t < c.tHold) return c.usual;
  if (t < c.tStop) return c.usual + (c.after - c.usual) * easeInOut(prog(t, c.tHold, c.tStop));
  return c.after;
};

// ---- 1. pad: odd harmonics when the shot is hot, near-pure sines when it is cold -----------
const temp = (t) => {
  // 1 = hot, 0 = cold, eased across scene overlaps
  let v = 0, w = 0;
  for (const s of cues.scenes) {
    const k = Math.min(prog(t, s.start - 0.4, s.start + 0.4), 1 - prog(t, s.end - 0.4, s.end + 0.4));
    v += k * (s.temp === "hot" ? 1 : 0);
    w += k;
  }
  return w > 0 ? v / w : 0;
};
{
  const ph = new Float64Array(16);
  for (let i = 0; i < N; i++) {
    const t = i / SR;
    const h = temp(t);
    const master = Math.min(prog(t, 0, 1.2), 1 - prog(t, cues.duration - 2.5, cues.duration));
    const breathe = 0.82 + 0.18 * Math.sin(TAU * 0.09 * t);
    let l = 0, r = 0;
    // root A1 + fifth, detuned a hair between channels
    const roots = [55, 82.41, 110];
    roots.forEach((f, k) => {
      for (let n = 1; n <= 7; n += 2) {
        const amp = (n === 1 ? 1 : h * 0.55 / n) * (k === 2 ? 0.35 : 1);
        if (amp < 1e-4) continue;
        const idx = k * 4 + (n >> 1);
        ph[idx] += (TAU * f * n) / SR;
        const s = Math.sin(ph[idx]);
        l += s * amp * (1 + 0.002 * k);
        r += Math.sin(ph[idx] + 0.25 * k) * amp;
      }
    });
    // cold shimmer: a quiet A4/E5 pair
    const cold = 1 - h;
    ph[14] += (TAU * 440) / SR; ph[15] += (TAU * 659.25) / SR;
    const sh = 0.05 * cold * (0.6 + 0.4 * Math.sin(TAU * 0.23 * t));
    l += sh * Math.sin(ph[14]); r += sh * Math.sin(ph[15]);
    const g = 0.085 * master * breathe;
    L[i] += l * g; R[i] += r * g;
  }
}

// ---- 2. ticks as the meter passes each 0.1 s mark, thump when it lands --------------------
function tick(t, hot, gain = 1) {
  const i0 = Math.round(t * SR), len = Math.round(0.05 * SR);
  const f = hot ? 1320 : 2350;
  for (let j = 0; j < len; j++) {
    const e = Math.exp(-j / (0.008 * SR));
    const s = (hot ? Math.sign(Math.sin((TAU * f * j) / SR)) * 0.35 + Math.sin((TAU * f * j) / SR) * 0.65 : Math.sin((TAU * f * j) / SR));
    add(i0 + j, s * e * 0.42 * gain, s * e * 0.42 * gain);
  }
}
function thump(t, gain = 1) {
  const i0 = Math.round(t * SR), len = Math.round(0.6 * SR);
  let p = 0;
  for (let j = 0; j < len; j++) {
    const tt = j / SR;
    const f = 44 + 70 * Math.exp(-tt * 18);
    p += (TAU * f) / SR;
    const e = Math.exp(-tt * 7);
    add(i0 + j, Math.sin(p) * e * 0.32 * gain, Math.sin(p) * e * 0.32 * gain);
  }
}
function ping(t, f, gain = 1, decay = 0.9) {
  const i0 = Math.round(t * SR), len = Math.round(decay * 2.5 * SR);
  for (let j = 0; j < len; j++) {
    const tt = j / SR;
    const e = Math.exp(-tt / (decay * 0.4)) * Math.min(1, tt * 400);
    const s = Math.sin(TAU * f * tt) + 0.3 * Math.sin(TAU * f * 2.01 * tt) * Math.exp(-tt * 6);
    add(i0 + j, s * e * 0.12 * gain, s * e * 0.12 * gain * 0.9);
  }
}
for (const key of ["meter1", "meter2"]) {
  const c = cues[key];
  let last = 0;
  for (let i = Math.round(c.t0 * SR); i < Math.round((c.tStop + 0.05) * SR); i += 48) {
    const t = i / SR;
    const v = meterValue(t, c);
    const mark = Math.floor(v * 10 + 1e-6);
    if (mark > last) { tick(t, v > c.usual + 0.004, key === "meter1" ? 1 : 0.8); last = mark; }
  }
  tick(c.tUsual, false, 0.9);
  thump(c.tStop, key === "meter1" ? 1 : 0.7);
  if (key === "meter1") ping(c.tStop + 0.02, 880, 0.9, 0.7);
}
// cold caliper closing in shot 6
ping(cues.caliper, 1318.5, 0.8, 1.1);

// ---- 3. scan-band wipes and the shot-4 scan: band-limited seeded noise sweeps -------------
function sweep(t0, dur, hot, gain = 1) {
  const rnd = mulberry32(Math.round(t0 * 1000));
  const i0 = Math.round(t0 * SR), len = Math.round((dur + 0.3) * SR);
  let lp = 0, lp2 = 0, hp = 0;
  for (let j = 0; j < len; j++) {
    const tt = j / SR;
    const p = clamp01(tt / dur);
    const fc = (hot ? 300 : 600) * Math.pow(hot ? 12 : 10, p);
    const a = 1 - Math.exp((-TAU * fc) / SR);
    const n = rnd() * 2 - 1;
    lp += a * (n - lp); lp2 += a * (lp - lp2);
    hp += 0.02 * (lp2 - hp);
    const env = Math.sin(Math.PI * clamp01(tt / (dur + 0.3)));
    const s = (lp2 - hp) * env * 0.5 * gain;
    const pan = -1 + 2 * p;
    add(i0 + j, s * (1 - pan) * 0.5 + s * 0.3, s * (1 + pan) * 0.5 + s * 0.3);
  }
}
for (const w of cues.wipes) sweep(w.t, w.dur, w.temp === "hot");
sweep(34.0, 2.3, true, 0.7);
// detection of the altered macro: two hot notes
ping(35.08, 587.33, 0.7, 0.5); ping(35.24, 830.6, 0.7, 0.6);

// ---- 4. soft hits on structural beats -----------------------------------------------------
for (const t of cues.hits) thump(t, 0.45);

// ---- normalise and write 16-bit stereo WAV --------------------------------------------------
let peak = 0;
for (let i = 0; i < N; i++) peak = Math.max(peak, Math.abs(L[i]), Math.abs(R[i]));
const g = peak > 0 ? 0.85 / peak : 1;
const buf = Buffer.alloc(44 + N * 4);
buf.write("RIFF", 0); buf.writeUInt32LE(36 + N * 4, 4); buf.write("WAVE", 8);
buf.write("fmt ", 12); buf.writeUInt32LE(16, 16); buf.writeUInt16LE(1, 20); buf.writeUInt16LE(2, 22);
buf.writeUInt32LE(SR, 24); buf.writeUInt32LE(SR * 4, 28); buf.writeUInt16LE(4, 32); buf.writeUInt16LE(16, 34);
buf.write("data", 36); buf.writeUInt32LE(N * 4, 40);
for (let i = 0; i < N; i++) {
  buf.writeInt16LE(Math.round(Math.max(-1, Math.min(1, L[i] * g)) * 32767), 44 + i * 4);
  buf.writeInt16LE(Math.round(Math.max(-1, Math.min(1, R[i] * g)) * 32767), 46 + i * 4);
}
writeFileSync(join(here, "../public/soundtrack.wav"), buf);
console.log(`soundtrack.wav: ${cues.duration}s, peak gain ${g.toFixed(2)}`);
