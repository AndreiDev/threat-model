// Shared frame furniture: backdrop, thermal legend, scan-band wipes.
import React from "react";
import { AbsoluteFill } from "remotion";
import { C, COLD, HEAT, alpha } from "../lib/color";
import { SANS } from "../lib/fonts";
import { ease, keys, lerp, prog } from "../lib/motion";
import cues from "../cues.json";

export const W = 1920;
export const H = 1080;

/** Indigo night with a faint dot grid and corner brackets, like a thermal viewfinder. */
export const Backdrop: React.FC = () => (
  <AbsoluteFill style={{ background: C.void }}>
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} style={{ position: "absolute", inset: 0 }}>
      <defs>
        <pattern id="dots" width="48" height="48" patternUnits="userSpaceOnUse">
          <circle cx="24" cy="24" r="1.3" fill={alpha(C.steel, 0.28)} />
        </pattern>
        <radialGradient id="vig" cx="50%" cy="46%" r="75%">
          <stop offset="0%" stopColor={C.deep} stopOpacity="0.55" />
          <stop offset="60%" stopColor={C.void} stopOpacity="0" />
          <stop offset="100%" stopColor="#07051A" stopOpacity="0.75" />
        </radialGradient>
      </defs>
      <rect width={W} height={H} fill="url(#vig)" />
      <rect width={W} height={H} fill="url(#dots)" />
      {[
        [56, 56, 1, 1], [W - 56, 56, -1, 1], [56, H - 56, 1, -1], [W - 56, H - 56, -1, -1],
      ].map(([x, y, sx, sy], i) => (
        <path key={i} d={`M ${x} ${y + sy * 34} L ${x} ${y} L ${x + sx * 34} ${y}`} stroke={alpha(C.steel, 0.55)} strokeWidth={2} fill="none" />
      ))}
    </svg>
  </AbsoluteFill>
);

const sceneTemp = (t: number) => {
  // Reading of the thermal legend: hot shots sit near "hostile", cold shots near "verified".
  const table: [number, number][] = [];
  for (const s of cues.scenes) {
    const v = s.temp === "hot" ? 0.1 : 0.88;
    table.push([s.start + 0.4, v]);
    table.push([s.end - 0.6, v]);
  }
  return keys(t, table.map(([a, b]) => [a, b, ease.inOut]));
};

/** FLIR-style scale bar on the right edge: the legend for every colour in the film. */
export const ThermalScale: React.FC<{ t: number }> = ({ t }) => {
  const x = 1838, y0 = 176, h = 240, w = 10;
  const v = sceneTemp(t);
  const my = y0 + v * h;
  const stops = [...[...HEAT].reverse(), ...COLD.slice(1)];
  const fadeIn = prog(t, 0.2, 1.0, ease.out);
  return (
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} style={{ position: "absolute", inset: 0, opacity: 0.85 * fadeIn }}>
      <defs>
        <linearGradient id="scale" x1="0" y1="0" x2="0" y2="1">
          {stops.map((c, i) => (
            <stop key={i} offset={`${(i / (stops.length - 1)) * 100}%`} stopColor={c} />
          ))}
        </linearGradient>
      </defs>
      <rect x={x} y={y0} width={w} height={h} rx={5} fill="url(#scale)" />
      <path d={`M ${x - 8} ${my} l -12 -8 l 0 16 z`} fill={v < 0.5 ? C.heat4 : C.ice} />
      <text x={x + w / 2} y={y0 - 16} textAnchor="middle" fill={C.heat2} style={{ fontFamily: SANS, fontSize: 20, fontWeight: 500 }}>
        hostile
      </text>
      <text x={x + w / 2} y={y0 + h + 32} textAnchor="middle" fill={C.ice} style={{ fontFamily: SANS, fontSize: 20, fontWeight: 500 }}>
        verified
      </text>
    </svg>
  );
};

/** Current x of a scan-band wipe at time t, or null when no wipe is running. */
export const wipeX = (t: number, w: { t: number; dur: number }) => {
  if (t < w.t || t > w.t + w.dur) return null;
  return lerp(-180, W + 180, prog(t, w.t, w.t + w.dur, ease.inOut));
};

/** The visible band of a thermal scan wipe (drawn above both scenes). */
export const ScanBand: React.FC<{ t: number }> = ({ t }) => {
  const live = cues.wipes.map((w) => ({ w, x: wipeX(t, w) })).filter((o) => o.x != null);
  if (!live.length) return null;
  return (
    <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} style={{ position: "absolute", inset: 0 }}>
      <defs>
        <linearGradient id="band-hot" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={C.heat1} />
          <stop offset="45%" stopColor={C.heat3} />
          <stop offset="70%" stopColor={C.heat4} />
          <stop offset="100%" stopColor={C.heat2} />
        </linearGradient>
        <linearGradient id="band-cold" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={COLD[1]} />
          <stop offset="50%" stopColor={C.ice} />
          <stop offset="100%" stopColor={COLD[2]} />
        </linearGradient>
        <linearGradient id="band-fade" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="#fff" stopOpacity="0" />
          <stop offset="85%" stopColor="#fff" stopOpacity="0.5" />
          <stop offset="100%" stopColor="#fff" stopOpacity="1" />
        </linearGradient>
        <mask id="band-mask">
          <rect x={0} y={0} width={180} height={H} fill="url(#band-fade)" />
        </mask>
      </defs>
      {live.map(({ w, x }, i) => (
        <g key={i} transform={`translate(${(x as number) - 180} 0)`}>
          <rect width={180} height={H} fill={`url(#band-${w.temp})`} mask="url(#band-mask)" opacity={0.42} />
          <rect x={176} width={4} height={H} fill={w.temp === "hot" ? C.heat5 : C.frost} />
        </g>
      ))}
    </svg>
  );
};
