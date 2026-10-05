// Trust is temperature: verified things are cold, hostile things run hot (FLIR ironbow).
export const C = {
  void: "#100C2A",
  deep: "#1B1747",
  steel: "#4E5A8C",
  mist: "#8C93C4",
  ice: "#9BE8FF",
  frost: "#E8F7FF",
  heat0: "#3A0F6B",
  heat1: "#9B1D8F",
  heat2: "#F0306A",
  heat3: "#FF7A2F",
  heat4: "#FFD36B",
  heat5: "#FFF6E0",
} as const;

export const HEAT = [C.heat0, C.heat1, C.heat2, C.heat3, C.heat4, C.heat5];
export const COLD = ["#1B1747", "#2F4FA8", "#4FA3E0", "#9BE8FF", "#E8F7FF"];

type RGB = [number, number, number];
const cache = new Map<string, RGB>();
export const rgb = (hex: string): RGB => {
  let v = cache.get(hex);
  if (!v) {
    v = [parseInt(hex.slice(1, 3), 16), parseInt(hex.slice(3, 5), 16), parseInt(hex.slice(5, 7), 16)];
    cache.set(hex, v);
  }
  return v;
};
const clamp01 = (x: number) => (x < 0 ? 0 : x > 1 ? 1 : x);
const toHex = (c: RGB) =>
  "#" + c.map((v) => Math.round(Math.max(0, Math.min(255, v))).toString(16).padStart(2, "0")).join("");

export const mix = (a: string, b: string, p: number): string => {
  const A = rgb(a), B = rgb(b), q = clamp01(p);
  return toHex([A[0] + (B[0] - A[0]) * q, A[1] + (B[1] - A[1]) * q, A[2] + (B[2] - A[2]) * q]);
};
const ramp = (stops: string[], x: number) => {
  const s = clamp01(x) * (stops.length - 1);
  const i = Math.min(stops.length - 2, Math.floor(s));
  return mix(stops[i], stops[i + 1], s - i);
};
/** 0..1 up the heat ramp: violet, magenta, hostile pink, orange, yellow, white-hot. */
export const ironbow = (x: number) => ramp(HEAT, x);
/** 0..1 up the cold ramp: indigo to ice to white-cold. */
export const coldbow = (x: number) => ramp(COLD, x);
export const alpha = (hex: string, a: number) => {
  const [r, g, b] = rgb(hex);
  return `rgba(${r},${g},${b},${a})`;
};
