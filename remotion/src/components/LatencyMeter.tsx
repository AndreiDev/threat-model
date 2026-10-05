// The latency meter: a failed SSH login timed on a 0 to 1.0 s track.
// Time inside the usual 0.299 s is cold; every millisecond beyond it runs up the heat ramp.
import React from "react";
import { C, COLD, alpha, coldbow, ironbow } from "../lib/color";
import { MONO, SANS } from "../lib/fonts";
import { clamp01, ease, lerp, prog } from "../lib/motion";

export type MeterCue = { t0: number; tUsual: number; tHold: number; tStop: number; usual: number; after: number };

/** Value shown by the meter at time t: eases into the usual 0.299 s, pauses, then keeps going. */
export const meterValue = (t: number, c: MeterCue) => {
  if (t <= c.t0) return 0;
  if (t < c.tUsual) return c.usual * prog(t, c.t0, c.tUsual, ease.out);
  if (t < c.tHold) return c.usual;
  if (t < c.tStop) return lerp(c.usual, c.after, prog(t, c.tHold, c.tStop, ease.inOut));
  return c.after;
};
/** Small damped overshoot of the bar head after it lands. */
export const meterOvershoot = (t: number, c: MeterCue) => {
  const d = t - c.tStop;
  if (d <= 0) return 0;
  return 0.022 * Math.exp(-5.5 * d) * Math.sin(17 * d);
};
/** Colour of a value: cold up to the usual time, then up the ironbow ramp. */
export const valueColor = (v: number, usual = 0.299) =>
  v <= usual + 0.004 ? coldbow(0.55 + 0.4 * (v / usual)) : ironbow(0.38 + 0.6 * clamp01((v - usual) / 0.52));

type Props = {
  value: number;
  overshoot?: number;
  x: number;
  y: number;
  width: number;
  usual?: number;
  /** 0..1: labels, ticks and ghost marker. */
  furniture?: number;
  /** 0..1: hot bracket labelled with the overrun. */
  bracket?: number;
  /** 0..1: cold caliper closing on the overrun. */
  caliper?: number;
  /** 0..1: collapse into a slim line. */
  slim?: number;
  id: string;
};

export const LatencyMeter: React.FC<Props> = ({
  value, overshoot = 0, x, y, width, usual = 0.299, furniture = 1, bracket = 0, caliper = 0, slim = 0, id,
}) => {
  const X = (s: number) => x + (s / 1.0) * width;
  const bh = lerp(40, 8, slim);
  const v = Math.max(0, value + overshoot);
  const head = valueColor(value, usual);
  const gx0 = X(0), gx1 = X(1);
  const u = (s: number) => `${(s * 100).toFixed(2)}%`;
  return (
    <g>
      <defs>
        <linearGradient id={`fill-${id}`} gradientUnits="userSpaceOnUse" x1={gx0} y1={0} x2={gx1} y2={0}>
          <stop offset={u(0)} stopColor={COLD[1]} />
          <stop offset={u(usual - 0.01)} stopColor={C.ice} />
          <stop offset={u(usual + 0.02)} stopColor={C.heat1} />
          <stop offset={u(0.48)} stopColor={C.heat2} />
          <stop offset={u(0.66)} stopColor={C.heat3} />
          <stop offset={u(0.8)} stopColor={C.heat4} />
          <stop offset={u(1)} stopColor={C.heat5} />
        </linearGradient>
        <filter id={`glow-${id}`} x="-20%" y="-200%" width="140%" height="500%">
          <feGaussianBlur stdDeviation="10" />
        </filter>
      </defs>
      {/* track */}
      <rect x={gx0} y={y - bh / 2} width={width} height={bh} rx={bh / 2} fill={alpha(C.deep, 0.9)} stroke={alpha(C.steel, 0.7)} strokeWidth={1.5} />
      {/* ticks + labels */}
      <g opacity={furniture * (1 - slim)}>
        {Array.from({ length: 11 }, (_, i) => {
          const tx = X(i / 10);
          return (
            <g key={i}>
              <line x1={tx} x2={tx} y1={y + bh / 2 + 6} y2={y + bh / 2 + (i % 5 === 0 ? 26 : 16)} stroke={alpha(C.steel, 0.9)} strokeWidth={2} />
              <text x={tx} y={y + bh / 2 + 62} textAnchor="middle" fill={C.mist} style={{ fontFamily: MONO, fontSize: 26, fontVariationSettings: "'wdth' 87.5, 'wght' 400" }}>
                {i === 0 ? "0" : i === 10 ? "1.0 s" : (i / 10).toFixed(1)}
              </text>
            </g>
          );
        })}
      </g>
      {/* fill */}
      {v > 0.001 ? (
        <>
          <rect x={gx0} y={y - bh / 2 - 4} width={X(v) - gx0} height={bh + 8} rx={bh / 2} fill={`url(#fill-${id})`} opacity={0.5} filter={`url(#glow-${id})`} />
          <rect x={gx0} y={y - bh / 2} width={X(v) - gx0} height={bh} rx={bh / 2} fill={`url(#fill-${id})`} />
          <rect x={X(v) - 3} y={y - bh / 2 - 14} width={6} height={bh + 28} rx={3} fill={head} />
        </>
      ) : null}
      {/* ghost marker: the usual time */}
      <g opacity={furniture}>
        <line x1={X(usual)} x2={X(usual)} y1={y - bh / 2 - lerp(70, 20, slim)} y2={y + bh / 2 + 4} stroke={C.ice} strokeWidth={3} strokeDasharray="6 6" />
        <text
          x={caliper > 0 ? X(usual) - 34 : X(usual)} y={y - bh / 2 - lerp(84, 34, slim)} textAnchor={caliper > 0 ? "end" : "middle"}
          fill={C.ice} style={{ fontFamily: SANS, fontSize: 30, fontWeight: 500, whiteSpace: "pre" }} opacity={1 - slim}
        >
          {"usual: "}
          <tspan style={{ fontFamily: MONO, fontVariationSettings: "'wdth' 87.5, 'wght' 400" }}>0.299 s</tspan>
        </text>
      </g>
      {/* hot bracket over the overrun */}
      {bracket > 0 ? (
        <g opacity={bracket}>
          <path
            d={`M ${X(usual) + 6} ${y - bh / 2 - 30} v -22 H ${lerp(X(usual) + 6, X(0.807) - 6, ease.out(bracket))} v 22`}
            stroke={C.heat3} strokeWidth={3} fill="none"
          />
          <text x={(X(usual) + X(0.807)) / 2} y={y - bh / 2 - 74} textAnchor="middle" fill={C.heat3} style={{ fontFamily: MONO, fontSize: 46, fontVariationSettings: "'wdth' 100, 'wght' 400" }}>
            +0.508 s
          </text>
        </g>
      ) : null}
      {/* cold caliper closing on the overrun */}
      {caliper > 0 ? (() => {
        const k = ease.outBack(clamp01(caliper));
        const a = lerp(X(usual) - 220, X(usual), k);
        const b = lerp(X(0.807) + 220, X(0.807), k);
        const top = y - bh / 2 - 120, bot = y + bh / 2 + 14;
        return (
          <g opacity={clamp01(caliper * 3)}>
            {[a, b].map((cx, i) => (
              <g key={i}>
                <line x1={cx} x2={cx} y1={top} y2={bot} stroke={C.ice} strokeWidth={4} />
                <line x1={cx} x2={cx + (i ? -26 : 26)} y1={bot} y2={bot} stroke={C.ice} strokeWidth={4} />
              </g>
            ))}
            <line x1={a + 10} x2={b - 10} y1={top + 18} y2={top + 18} stroke={C.ice} strokeWidth={2} />
            <path d={`M ${a + 10} ${top + 18} l 14 -8 v 16 z M ${b - 10} ${top + 18} l -14 -8 v 16 z`} fill={C.ice} />
            <text x={(a + b) / 2} y={top - 6} textAnchor="middle" fill={C.ice} style={{ fontFamily: MONO, fontSize: 58, fontVariationSettings: "'wdth' 100, 'wght' 350" }}>
              +508 ms
            </text>
          </g>
        );
      })() : null}
    </g>
  );
};
