// Shot 6, 0:58-1:12. Half a second: the discovery, measured cold.
import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import { C, alpha } from "../lib/color";
import { MONO, SANS } from "../lib/fonts";
import { ease, prog } from "../lib/motion";
import { Caption } from "../components/Type";
import { LatencyMeter, meterOvershoot, meterValue } from "../components/LatencyMeter";
import { W, H } from "../components/Hud";
import cues from "../cues.json";

const M = cues.meter2;
// Illustrative proportions: the disclosure says "lots of cpu time in liblzma", not a percentage.
const SEGS = [
  { name: "sshd", w: 0.13, col: "#2F4FA8" },
  { name: "libcrypto", w: 0.12, col: "#3E5FB8" },
  { name: "libc", w: 0.07, col: "#4E5A8C" },
  { name: "liblzma.so.5.6.0  [unknown]", w: 0.68, col: "hot" },
];

export const S6Half: React.FC<{ start: number }> = ({ start }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = start + frame / fps;
  const enter = 1; // revealed by the cold scan wipe at 58.0
  const profIn = prog(t, 58.9, 59.4, ease.out);
  const profOut = prog(t, 63.2, 63.6, ease.in);
  const meterIn = prog(t, 63.7, 64.1, ease.out);
  const meterOut = prog(t, 66.9, 67.3, ease.in);
  const v = meterValue(t, M);
  const caliper = prog(t, 65.8, 66.35);
  const datesIn = (i: number) => prog(t, 67.3 + i * 0.55, 67.8 + i * 0.55, ease.out);
  const datesDim = prog(t, 69.2, 69.7);

  return (
    <AbsoluteFill style={{ opacity: enter }}>
      <Caption
        t={t} t0={58.35} tOut={66.9} x={140} y={128} size={54} width={1600}
        text="March 2024. ~Andres Freund,~ a PostgreSQL developer, is micro-benchmarking on Debian unstable."
      />
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} style={{ position: "absolute", inset: 0 }}>
        <defs>
          <linearGradient id="hotseg" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor={C.heat1} />
            <stop offset="45%" stopColor={C.heat2} />
            <stop offset="100%" stopColor={C.heat3} />
          </linearGradient>
          <filter id="s6glow" x="-10%" y="-60%" width="120%" height="220%">
            <feGaussianBlur stdDeviation="14" />
          </filter>
        </defs>
        {/* profile bar */}
        {profIn > 0 && profOut < 1 ? (
          <g opacity={profIn * (1 - profOut)} transform={`translate(0 ${(1 - profIn) * 20 - profOut * 30})`}>
            <text x={140} y={392} fill={C.mist} style={{ fontFamily: SANS, fontSize: 30, fontWeight: 500 }}>
              Where sshd spent its CPU time (proportions illustrative)
            </text>
            {(() => {
              let x = 140;
              return SEGS.map((s, i) => {
                const w = 1600 * s.w;
                const grow = prog(t, 59.05 + i * 0.12, 59.5 + i * 0.12, ease.out);
                const bx = x;
                x += w;
                const hot = s.col === "hot";
                return (
                  <g key={s.name}>
                    {hot ? <rect x={bx} y={424} width={w * grow} height={92} rx={8} fill={C.heat2} opacity={0.35} filter="url(#s6glow)" /> : null}
                    <rect x={bx + 2} y={424} width={Math.max(0, w * grow - 4)} height={92} rx={8} fill={hot ? "url(#hotseg)" : s.col} />
                    <text x={bx + 18} y={482} fill={hot ? C.heat5 : C.frost} opacity={prog(grow, 0.6, 1)}
                      style={{ fontFamily: MONO, fontSize: 28, fontVariationSettings: "'wdth' 87.5, 'wght' 400", whiteSpace: "pre" }}>
                      {s.name}
                    </text>
                  </g>
                );
              });
            })()}
          </g>
        ) : null}
        {/* the meter, replayed with a cold caliper */}
        {meterIn > 0 && meterOut < 1 ? (
          <g opacity={meterIn * (1 - meterOut)}>
            <LatencyMeter id="m2" value={v} overshoot={meterOvershoot(t, M)} x={140} y={560} width={1600} caliper={caliper} />
          </g>
        ) : null}
        {/* dates */}
        {t > 67.2 ? (
          <g>
            {[
              { d: "28 Mar 2024", s: "Private report to Debian and the distros mailing list." },
              { d: "29 Mar 2024", s: "Public disclosure on oss-security. CVE-2024-3094, CVSS 10.0." },
            ].map((r, i) => {
              const a = datesIn(i);
              return (
                <g key={i} opacity={a * (1 - datesDim * 0.45)} transform={`translate(${(1 - a) * -30} 0)`}>
                  <circle cx={156} cy={388 + i * 130} r={13} fill={C.void} stroke={C.ice} strokeWidth={4} />
                  {i === 0 ? <line x1={156} x2={156} y1={403} y2={505} stroke={alpha(C.ice, 0.6)} strokeWidth={3} /> : null}
                  <text x={196} y={402 + i * 130} fill={C.ice} style={{ fontFamily: MONO, fontSize: 38, fontVariationSettings: "'wdth' 100, 'wght' 400" }}>
                    {r.d}
                  </text>
                  <text x={526} y={402 + i * 130} fill={C.frost} style={{ fontFamily: SANS, fontSize: 44, fontWeight: 500 }}>
                    {r.s}
                  </text>
                </g>
              );
            })}
          </g>
        ) : null}
      </svg>
      <Caption
        t={t} t0={59.35} tOut={63.2} x={140} y={600} size={52} width={1600}
        text="sshd burned CPU even on logins that failed at once. The profiler pointed into liblzma, *at code with no symbol name.*"
      />
      <Caption
        t={t} t0={64.0} tOut={66.9} x={140} y={850} size={54} width={1600}
        text="He remembered an odd valgrind error from a few weeks earlier, ~and kept digging.~"
      />
      <Caption t={t} t0={69.4} x={140} y={660} size={80} width={1600} color={C.frost} wght={500} text="“Really required a lot of coincidences.”" />
      <Caption t={t} t0={69.95} x={140} y={774} size={36} width={1600} color={C.mist} wght={400} text="Andres Freund, 29 March 2024" />
    </AbsoluteFill>
  );
};
