// Shots 7-9, 1:11.5-1:29. Caught early; what to change; end card.
import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import { C, alpha, mix } from "../lib/color";
import { MONO, SANS } from "../lib/fonts";
import { clamp01, ease, lerp, prog, springAt } from "../lib/motion";
import { Caption, KineticType } from "../components/Type";
import { LatencyMeter } from "../components/LatencyMeter";
import { W, H } from "../components/Hud";

// ---------------------------------------------------------------- shot 7: caught early
// Red Hat: Fedora Rawhide and Fedora 40 beta received 5.6.x; RHEL not affected.
// Debian DSA-5649-1: testing, unstable and experimental affected; no stable version.
const GOT = ["Fedora Rawhide", "Fedora 40 beta", "Debian testing", "Debian unstable", "Debian experimental"];
const SAFE = ["Debian stable", "Red Hat Enterprise Linux"];

export const S7Caught: React.FC<{ start: number }> = ({ start }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = start + frame / fps;
  const enter = prog(t, 71.5, 72.1, ease.out) * (1 - prog(t, 77.0, 77.5));
  const waveX = lerp(60, 1200, prog(t, 74.3, 75.6, ease.inOut));
  const waveOn = t > 74.3 && t < 75.7;

  const chip = (label: string, x: number, y: number, w: number, a: number, cool: number, safe: boolean, key: string) => {
    const stroke = safe ? C.ice : mix(C.heat2, C.ice, cool);
    const fill = safe ? alpha(C.deep, 0.85) : mix(mix(C.void, C.heat0, 0.8), C.deep, cool);
    return (
      <g key={key} opacity={clamp01(a * 1.4)} transform={`translate(${x} ${y + (1 - Math.min(1, a)) * 30})`}>
        {!safe && cool < 1 ? <rect x={-4} y={-4} width={w + 8} height={94} rx={16} fill={C.heat2} opacity={0.25 * (1 - cool)} filter="url(#s7glow)" /> : null}
        <rect width={w} height={86} rx={14} fill={fill} stroke={stroke} strokeWidth={3} />
        <text x={24} y={56} fill={C.frost} style={{ fontFamily: MONO, fontSize: 32, fontVariationSettings: "'wdth' 87.5, 'wght' 400" }}>{label}</text>
        {!safe && cool > 0.4 ? (
          <path d={`M ${w - 46} 46 l 10 10 l 20 -22`} fill="none" stroke={C.ice} strokeWidth={4.5} strokeLinecap="round" strokeLinejoin="round"
            pathLength={100} style={{ strokeDasharray: `${prog(cool, 0.4, 1) * 100} 100` }} />
        ) : null}
      </g>
    );
  };

  return (
    <AbsoluteFill style={{ opacity: enter }}>
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} style={{ position: "absolute", inset: 0 }}>
        <defs>
          <filter id="s7glow" x="-20%" y="-50%" width="140%" height="200%"><feGaussianBlur stdDeviation="12" /></filter>
          <linearGradient id="s7wave" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor={C.ice} stopOpacity="0" />
            <stop offset="100%" stopColor={C.ice} stopOpacity="0.4" />
          </linearGradient>
        </defs>
        <text x={140} y={360} fill={C.heat2} opacity={prog(t, 72.4, 72.9)} style={{ fontFamily: SANS, fontSize: 32, fontWeight: 600 }}>Received 5.6.0 or 5.6.1</text>
        <text x={1200} y={360} fill={C.ice} opacity={prog(t, 73.3, 73.8)} style={{ fontFamily: SANS, fontSize: 32, fontWeight: 600 }}>Not affected</text>
        {GOT.map((g, i) => {
          const col = i % 2, row = Math.floor(i / 2);
          const x = 140 + col * 520, y = 392 + row * 110;
          const a = springAt(t - (72.5 + i * 0.12), 200, 14);
          const cool = prog(waveX, x + 60, x + 260);
          return chip(g, x, y, 500, a, cool, false, g);
        })}
        {SAFE.map((g, i) => chip(g, 1200, 392 + i * 110, 560, springAt(t - (73.4 + i * 0.14), 200, 14), 1, true, g))}
        {waveOn ? (
          <g>
            <rect x={waveX - 200} y={300} width={200} height={460} fill="url(#s7wave)" />
            <rect x={waveX - 2} y={300} width={4} height={460} fill={C.frost} />
          </g>
        ) : null}
      </svg>
      <Caption t={t} t0={71.9} x={140} y={128} size={56} width={1600}
        text="It reached development and pre-release versions, ~not Debian stable or Red Hat Enterprise Linux.~" />
      <Caption t={t} t0={75.0} x={140} y={850} size={56} width={1600} text="Within days, distributions rolled back to ~xz 5.4.x.~" />
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- shot 8: what to change
const CARDS = [
  { title: ["Reproducible", "builds"], body: "Rebuild from source and get the same bytes, so anyone can check." },
  { title: ["Check artefacts", "against source"], body: "A release tarball that differs from git is a question, not a detail." },
  { title: ["Support", "maintainers"], body: "One tired volunteer shouldn't be the last line of defence." },
];

export const S8Change: React.FC<{ start: number }> = ({ start }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = start + frame / fps;
  const enter = prog(t, 77.0, 77.5, ease.out) * (1 - prog(t, 84.5, 84.95));
  const l1 = "What shipped wasn't";
  const l2 = "what was reviewed.";
  return (
    <AbsoluteFill style={{ opacity: enter }}>
      <div style={{ position: "absolute", left: 132, top: 112 }}>
        <KineticType t={t} t0={77.3} text={l1} size={92} colorAt={(i) => (i >= 5 && i < 12 ? C.heat3 : undefined)} />
        <KineticType t={t} t0={77.3 + l1.length * (1.1 / 30)} text={l2} size={92} colorAt={(i) => (i >= 9 && i < 17 ? C.ice : undefined)} />
      </div>
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} style={{ position: "absolute", inset: 0 }}>
        {CARDS.map((c, i) => {
          const a = springAt(t - (79.0 + i * 0.4), 190, 14);
          const x = 140 + i * 560;
          const tick = prog(t, 79.6 + i * 0.4, 80.1 + i * 0.4, ease.out);
          return (
            <g key={i} opacity={clamp01(a * 1.5)} transform={`translate(${x} ${388 + (1 - Math.min(1, a)) * 50})`}>
              <rect width={500} height={330} rx={20} fill={alpha(C.deep, 0.75)} stroke={alpha(C.ice, 0.75)} strokeWidth={2.5} />
              <path d="M 432 52 l 14 14 l 26 -30" fill="none" stroke={C.ice} strokeWidth={5} strokeLinecap="round" strokeLinejoin="round" pathLength={100} style={{ strokeDasharray: `${tick * 100} 100` }} />
              {c.title.map((ln, k) => (
                <text key={k} x={34} y={70 + k * 44} fill={C.ice} style={{ fontFamily: MONO, fontSize: 34, fontVariationSettings: "'wdth' 87.5, 'wght' 400" }}>{ln}</text>
              ))}
            </g>
          );
        })}
      </svg>
      {CARDS.map((c, i) => (
        <Caption key={i} t={t} t0={79.3 + i * 0.4} x={140 + i * 560 + 34} y={388 + 142} size={36} width={432} wght={400} lineHeight={1.3} text={c.body} />
      ))}
      <Caption t={t} t0={81.9} x={140} y={790} size={54} width={1600}
        text="Whether a person or a model reviews the change, ~verify what actually ships.~" />
    </AbsoluteFill>
  );
};

// ---------------------------------------------------------------- shot 9: end card
export const S9End: React.FC<{ start: number }> = ({ start }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = start + frame / fps;
  const enter = prog(t, 85.0, 85.3, ease.out);
  return (
    <AbsoluteFill style={{ opacity: enter }}>
      <Caption t={t} t0={85.3} x={140} y={300} size={64} width={1600} color={C.mist} text="More than two years of patient work." />
      <div style={{ position: "absolute", left: 136, top: 410 }}>
        <KineticType t={t} t0={86.1} text="Given away by half a second." size={78} wght={300} wdthFrom={75} wdthTo={100} color={C.ice} />
      </div>
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} style={{ position: "absolute", inset: 0 }}>
        <g opacity={prog(t, 86.6, 87.0)}>
          <LatencyMeter id="m3" value={0.807 * prog(t, 86.6, 87.5, ease.inOut)} x={140} y={600} width={1600} slim={1} furniture={0.6} />
        </g>
      </svg>
      <div style={{ position: "absolute", left: 140, top: 820, opacity: prog(t, 87.0, 87.6, ease.out) }}>
        <div style={{ fontFamily: MONO, fontSize: 34, fontVariationSettings: "'wdth' 112.5, 'wght' 300", color: C.frost, marginBottom: 14 }}>
          Five hundred milliseconds
        </div>
        <div style={{ fontFamily: SANS, fontSize: 26, fontWeight: 400, color: C.mist, lineHeight: 1.4 }}>
          Sources: Andres Freund on oss-security, 29 March 2024; CVE-2024-3094;
          <br />
          Russ Cox, research.swtch.com/xz-timeline. Full list in remotion/SOURCES.md.
        </div>
      </div>
    </AbsoluteFill>
  );
};
