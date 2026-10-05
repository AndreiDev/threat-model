// Kinetic type primitives. Every value is a pure function of absolute time `t` (seconds).
import React from "react";
import { C, HEAT, mix, alpha } from "../lib/color";
import { MONO, SANS } from "../lib/fonts";
import { SETTLE, clamp01, ease, prog, lerp } from "../lib/motion";

/** Arrives white-hot, settles to its target colour over ~13 frames. */
export const settleColor = (u: number, target: string) => {
  if (u <= 0) return HEAT[4];
  if (u < 0.12) return mix(HEAT[4], HEAT[5], u / 0.12);
  return mix(HEAT[5], target, ease.out(clamp01((u - 0.12) / 0.88)));
};

type KineticProps = {
  text: string;
  t: number;
  t0: number;
  size: number;
  color?: string;
  wght?: number;
  wdthFrom?: number;
  wdthTo?: number;
  stagger?: number;
  tOut?: number;
  style?: React.CSSProperties;
  /** Per-character colour override (index -> colour). */
  colorAt?: (i: number) => string | undefined;
};

/**
 * Title type: each character rises, opens its width axis (75 -> 112.5) and cools from
 * white-hot to its target colour over 13 frames.
 */
export const KineticType: React.FC<KineticProps> = ({
  text, t, t0, size, color = C.frost, wght = 250, wdthFrom = 75, wdthTo = 112.5,
  stagger = 1.1 / 30, tOut, style, colorAt,
}) => {
  const chars = Array.from(text);
  return (
    <div style={{ fontFamily: MONO, fontSize: size, lineHeight: 1.1, whiteSpace: "pre", ...style }}>
      {chars.map((ch, i) => {
        const u = (t - t0 - i * stagger) / SETTLE;
        const a = clamp01(u);
        const out = tOut == null ? 0 : prog(t, tOut + i * 0.012, tOut + i * 0.012 + 0.32, ease.in);
        const wd = lerp(wdthFrom, wdthTo, ease.out(clamp01(u / 1.6)));
        const target = colorAt?.(i) ?? color;
        const col = settleColor(u, target);
        const glow = (1 - ease.out(a)) * 0.9;
        return (
          <span
            key={i}
            style={{
              display: "inline-block",
              opacity: u <= 0 ? 0 : 1 - out,
              transform: `translateY(${(1 - ease.outBack(a)) * 0.32 + out * -0.3}em)`,
              color: col,
              fontVariationSettings: `'wdth' ${wd}, 'wght' ${wght}`,
              textShadow: glow > 0.02 ? `0 0 ${0.25 * size}px ${alpha(C.heat3, glow)}` : "none",
            }}
          >
            {ch}
          </span>
        );
      })}
    </div>
  );
};

type Token = { text: string; mode: "plain" | "hot" | "cold" | "code" };
/** `*hot words*`, `~cold words~`, and `code` in backticks. */
const tokenize = (src: string): Token[] => {
  const out: Token[] = [];
  let mode: Token["mode"] = "plain";
  for (const raw of src.split(" ")) {
    let w = raw;
    let m: Token["mode"] = mode;
    let close = false;
    if (w.startsWith("*")) { m = "hot"; w = w.slice(1); }
    else if (w.startsWith("~")) { m = "cold"; w = w.slice(1); }
    else if (w.startsWith("`")) { m = "code"; w = w.slice(1); }
    const endRe = /[*~`]([.,:;!?)”]*)$/;
    const mm = w.match(endRe);
    if (mm) { w = w.slice(0, w.length - mm[0].length) + mm[1]; close = true; }
    out.push({ text: w, mode: m });
    mode = close ? "plain" : m;
  }
  return out;
};

type CaptionProps = {
  text: string;
  t: number;
  t0: number;
  tOut?: number;
  size?: number;
  color?: string;
  wght?: number;
  width?: number;
  x: number;
  y: number;
  align?: "left" | "center";
  hot?: string;
  cold?: string;
  lineHeight?: number;
  font?: "sans" | "mono";
};

/** Caption: words rise out of a mask line, exit by sliding up. */
export const Caption: React.FC<CaptionProps> = ({
  text, t, t0, tOut, size = 56, color = C.frost, wght = 500, width = 1640, x, y,
  align = "left", hot = C.heat3, cold = C.ice, lineHeight = 1.22, font = "sans",
}) => {
  if (t < t0 - 0.1 || (tOut != null && t > tOut + 1.2)) return null;
  const toks = tokenize(text);
  return (
    <div
      style={{
        position: "absolute", left: x, top: y, width, textAlign: align,
        fontFamily: font === "sans" ? SANS : MONO, fontSize: size, fontWeight: wght,
        lineHeight, color,
        fontVariationSettings: font === "mono" ? `'wdth' 100, 'wght' ${wght}` : undefined,
      }}
    >
      {toks.map((tk, k) => {
        const a = prog(t, t0 + k * 0.032, t0 + k * 0.032 + 0.5, ease.outQuint);
        const b = tOut == null ? 0 : prog(t, tOut + k * 0.012, tOut + k * 0.012 + 0.34, ease.in);
        const c = tk.mode === "hot" ? hot : tk.mode === "cold" ? cold : color;
        const isCode = tk.mode === "code";
        return (
          <React.Fragment key={k}>
            <span style={{ display: "inline-block", overflow: "hidden", verticalAlign: "top", padding: "0.04em 0 0.14em", margin: "-0.04em 0 -0.14em" }}>
              <span
                style={{
                  display: "inline-block",
                  transform: `translateY(${(1 - a) * 115 - b * 115}%)`,
                  color: c,
                  ...(isCode
                    ? { fontFamily: MONO, fontSize: "0.84em", fontVariationSettings: "'wdth' 87.5, 'wght' 400", color: C.frost }
                    : {}),
                }}
              >
                {tk.text}
              </span>
            </span>
            {k < toks.length - 1 ? " " : null}
          </React.Fragment>
        );
      })}
    </div>
  );
};

/** Typewriter line by string slicing (never per-character opacity). */
export const Typed: React.FC<{
  text: string; t: number; t0: number; cps?: number; style?: React.CSSProperties; caret?: boolean; prefix?: React.ReactNode;
}> = ({ text, t, t0, cps = 40, style, caret = false, prefix }) => {
  const n = Math.max(0, Math.min(text.length, Math.floor((t - t0) * cps)));
  if (t < t0) return null;
  const showCaret = caret && Math.floor(t * 2.2) % 2 === 0;
  return (
    <div style={{ whiteSpace: "pre", ...style }}>
      {prefix}
      {text.slice(0, n)}
      {caret ? (
        <span style={{ display: "inline-block", width: "0.55em", height: "1.05em", verticalAlign: "-0.2em", marginLeft: "0.08em", background: C.ice, opacity: showCaret ? 0.9 : 0 }} />
      ) : null}
    </div>
  );
};
