import { Easing, interpolate } from "remotion";

export const FPS = 30;
/** Kinetic type settles over ~13 frames. */
export const SETTLE = 13 / FPS;

export const clamp01 = (x: number) => (x < 0 ? 0 : x > 1 ? 1 : x);
export const lerp = (a: number, b: number, p: number) => a + (b - a) * p;
/** Progress 0..1 of absolute time t through [a, b], with optional easing. */
export const prog = (t: number, a: number, b: number, ease: (x: number) => number = (x) => x) =>
  ease(clamp01((t - a) / (b - a)));

export const ease = {
  out: Easing.out(Easing.cubic),
  in: Easing.in(Easing.cubic),
  inOut: Easing.inOut(Easing.cubic),
  outQuint: Easing.out(Easing.poly(5)),
  inOutQuint: Easing.inOut(Easing.poly(5)),
  outBack: Easing.out(Easing.back(1.7)),
  outExpo: Easing.out(Easing.exp),
};

/** Closed-form damped spring 0 -> 1 (seconds). Overshoots when damping < critical. */
export function springAt(t: number, stiffness = 170, damping = 18, mass = 1) {
  if (t <= 0) return 0;
  const w0 = Math.sqrt(stiffness / mass);
  const z = damping / (2 * Math.sqrt(stiffness * mass));
  if (z < 1) {
    const wd = w0 * Math.sqrt(1 - z * z);
    return 1 - Math.exp(-z * w0 * t) * (Math.cos(wd * t) + ((z * w0) / wd) * Math.sin(wd * t));
  }
  return 1 - Math.exp(-w0 * t) * (1 + w0 * t);
}

/** Keyframe table [[t, v], ...] with easing into each key. */
export function keys(t: number, table: [number, number, ((x: number) => number)?][]) {
  if (t <= table[0][0]) return table[0][1];
  for (let i = 1; i < table.length; i++) {
    const [t1, v1, e] = table[i];
    if (t <= t1) {
      const [t0, v0] = table[i - 1];
      return interpolate(t, [t0, t1], [v0, v1], { easing: e ?? ease.inOut });
    }
  }
  return table[table.length - 1][1];
}

/** In/out envelope: rises over [a, a+fin], falls over [b, b+fout]. */
export const env = (t: number, a: number, b: number, fin = 0.4, fout = 0.4) =>
  Math.min(prog(t, a, a + fin, ease.out), 1 - prog(t, b, b + fout, ease.in));

export function mulberry32(seed: number) {
  let a = seed | 0;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}
export const hash = (i: number, seed = 1) => mulberry32(Math.imul(i + 1, 2654435761) ^ Math.imul(seed, 40503))();
