// Shot 2, 0:09-0:15. One library: liblzma sits under a lot of Linux, kept up by one person.
import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import { C, alpha } from "../lib/color";
import { MONO, SANS } from "../lib/fonts";
import { ease, lerp, prog, springAt } from "../lib/motion";
import { Caption } from "../components/Type";
import { W, H } from "../components/Hud";
import { HEX_EXIT } from "./S3LongGame";

const CX = 960, CY = 430, R = 150;
// Packages that link liblzma (checked: dpkg, rpm, libsystemd, kmod, python3's lzma module, libarchive).
const DEPS: { name: string; deg: number }[] = [
  { name: "rpm", deg: -162 },
  { name: "dpkg", deg: -122 },
  { name: "libarchive", deg: -58 },
  { name: "libsystemd", deg: -18 },
  { name: "kmod", deg: 162 },
  { name: "python3", deg: 18 },
];
const RX = 540, RY = 250;

export const hexPath = (cx: number, cy: number, r: number) =>
  Array.from({ length: 6 }, (_, k) => {
    const a = (Math.PI / 3) * k + Math.PI / 6;
    return `${k ? "L" : "M"} ${(cx + r * Math.cos(a)).toFixed(1)} ${(cy + r * Math.sin(a)).toFixed(1)}`;
  }).join(" ") + " Z";

export const S2Library: React.FC<{ start: number }> = ({ start }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = start + frame / fps;

  const hexIn = springAt(t - 9.25, 140, 14);
  const dim = prog(t, 12.3, 12.9, ease.inOut);
  const exit = prog(t, 14.45, 15.0, ease.inOut);
  const hx = lerp(CX, HEX_EXIT.x, exit), hy = lerp(CY, HEX_EXIT.y, exit);
  const hs = lerp(1, 0.08, exit) * (0.6 + 0.4 * hexIn);
  const fadeAll = 1 - prog(t, 14.3, 14.7);
  const maint = springAt(t - 12.6, 160, 16);

  return (
    <AbsoluteFill>
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} style={{ position: "absolute", inset: 0 }}>
        <defs>
          <filter id="s2glow" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="14" />
          </filter>
        </defs>
        {/* dependency lines */}
        <g opacity={fadeAll * lerp(1, 0.28, dim)}>
          {DEPS.map((d, i) => {
            const a = (d.deg * Math.PI) / 180;
            const ex = CX + RX * Math.cos(a), ey = CY + RY * Math.sin(a);
            const sx = CX + (R + 6) * Math.cos(a), sy = CY + (R + 6) * Math.sin(a) * 0.9;
            const len = Math.hypot(ex - sx, ey - sy);
            const p = prog(t, 9.55 + i * 0.09, 10.25 + i * 0.09, ease.out);
            const pop = springAt(t - (10.05 + i * 0.09), 200, 13);
            const right = Math.cos(a) > 0;
            return (
              <g key={d.name}>
                <line x1={sx} y1={sy} x2={ex} y2={ey} stroke={C.steel} strokeWidth={2.5} strokeDasharray={len} strokeDashoffset={len * (1 - p)} />
                <circle cx={ex} cy={ey} r={9 * pop} fill={C.void} stroke={C.ice} strokeWidth={3} />
                <text
                  x={ex + (right ? 26 : -26)} y={ey + 12} textAnchor={right ? "start" : "end"} fill={C.frost} opacity={pop > 0 ? Math.min(1, pop) : 0}
                  style={{ fontFamily: MONO, fontSize: 38, fontVariationSettings: "'wdth' 87.5, 'wght' 400" }}
                >
                  {d.name}
                </text>
              </g>
            );
          })}
        </g>
        {/* maintainer */}
        <g opacity={fadeAll * Math.min(1, Math.max(0, maint))}>
          <line x1={CX} y1={CY + R} x2={CX} y2={CY + R + 118 * Math.min(1, maint)} stroke={alpha(C.ice, 0.7)} strokeWidth={2.5} />
          <circle cx={CX} cy={CY + R + 130} r={16 * maint} fill={C.void} stroke={C.ice} strokeWidth={4} />
          <circle cx={CX} cy={CY + R + 130} r={26} fill={C.ice} opacity={0.18 * maint} filter="url(#s2glow)" />
          <text x={CX + 40} y={CY + R + 142} fill={C.frost} style={{ fontFamily: SANS, fontSize: 38, fontWeight: 500 }}>
            Lasse Collin
          </text>
          <text x={CX - 40} y={CY + R + 142} textAnchor="end" fill={C.mist} style={{ fontFamily: SANS, fontSize: 30, fontWeight: 400 }}>
            maintainer
          </text>
        </g>
        {/* the library */}
        <g transform={`translate(${hx} ${hy}) scale(${hs}) translate(${-CX} ${-CY})`} opacity={Math.min(1, hexIn * 1.4) * (1 - exit * 0.6)}>
          <path d={hexPath(CX, CY, R)} fill={C.ice} opacity={0.14} filter="url(#s2glow)" />
          <path d={hexPath(CX, CY, R)} fill={C.deep} stroke={C.ice} strokeWidth={4} />
          <text x={CX} y={CY + 4} textAnchor="middle" fill={C.frost} style={{ fontFamily: MONO, fontSize: 44, fontVariationSettings: "'wdth' 87.5, 'wght' 400" }}>
            liblzma
          </text>
          <text x={CX} y={CY + 50} textAnchor="middle" fill={C.mist} style={{ fontFamily: SANS, fontSize: 28, fontWeight: 500 }}>
            from xz-utils
          </text>
        </g>
      </svg>
      <Caption
        t={t} t0={9.75} tOut={12.15} x={140} y={850} size={56} width={1640}
        text="xz-utils makes .xz files. Its library, `liblzma`, sits under package managers, systemd and more."
      />
      <Caption
        t={t} t0={12.45} tOut={14.3} x={140} y={850} size={56} width={1640}
        text="An unpaid hobby project, maintained largely by ~one person.~"
      />
    </AbsoluteFill>
  );
};
