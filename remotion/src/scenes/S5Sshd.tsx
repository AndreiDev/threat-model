// Shot 5, 0:47-0:58.5. Into sshd: the dependency arrows point one way, the heat travels the other.
import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import { C, alpha, ironbow, mix } from "../lib/color";
import { MONO, SANS } from "../lib/fonts";
import { clamp01, ease, lerp, prog, springAt } from "../lib/motion";
import { Caption } from "../components/Type";
import { W, H } from "../components/Hud";

const NY = 380, NH = 160, NW = 400;
const NODES = {
  sshd: { x: 150, label: "sshd", sub: "OpenSSH server" },
  sysd: { x: 760, label: "libsystemd", sub: "systemd client library" },
  lzma: { x: 1370, label: "liblzma", sub: "xz-utils 5.6.0 or 5.6.1" },
};
// Heat level of each node over time (0 cold, 1 white-hot), travelling from liblzma to sshd.
const heatOf = (t: number, who: "sshd" | "sysd" | "lzma") => {
  const t0 = who === "lzma" ? 53.2 : who === "sysd" ? 53.75 : 54.3;
  return prog(t, t0, t0 + 0.6, ease.out);
};

const Node: React.FC<{ n: { x: number; label: string; sub: string }; a: number; heat: number; dy?: number }> = ({ n, a, heat, dy = 0 }) => {
  const stroke = heat > 0.02 ? ironbow(0.45 + 0.4 * heat) : C.ice;
  const fill = heat > 0.02 ? mix(C.deep, C.heat0, heat * 0.9) : C.deep;
  return (
    <g opacity={clamp01(a * 1.5)} transform={`translate(0 ${dy + (1 - Math.min(1, a)) * -40})`}>
      {heat > 0.05 ? <rect x={n.x - 6} y={NY - 6} width={NW + 12} height={NH + 12} rx={22} fill={C.heat2} opacity={0.35 * heat} filter="url(#s5glow)" /> : null}
      <rect x={n.x} y={NY} width={NW} height={NH} rx={18} fill={fill} stroke={stroke} strokeWidth={4} />
      <text x={n.x + NW / 2} y={NY + 76} textAnchor="middle" fill={heat > 0.3 ? C.heat5 : C.frost} style={{ fontFamily: MONO, fontSize: 50, fontVariationSettings: "'wdth' 100, 'wght' 400" }}>
        {n.label}
      </text>
      <text x={n.x + NW / 2} y={NY + 122} textAnchor="middle" fill={heat > 0.3 ? C.heat4 : C.mist} style={{ fontFamily: SANS, fontSize: 28, fontWeight: 500 }}>
        {n.sub}
      </text>
    </g>
  );
};

export const S5Sshd: React.FC<{ start: number }> = ({ start }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = start + frame / fps;

  const aSshd = springAt(t - 47.55, 170, 15);
  const aLzma = springAt(t - 47.75, 170, 15);
  const aSysd = springAt(t - 50.2, 210, 12);
  const direct = prog(t, 48.0, 48.8, ease.out);
  const strike = prog(t, 49.0, 49.35, ease.out);
  const directOut = 1 - prog(t, 49.9, 50.4);
  const link1 = prog(t, 50.6, 51.15, ease.out);
  const link2 = prog(t, 50.95, 51.5, ease.out);
  const fn = prog(t, 54.0, 54.5, ease.out);
  const reroute = prog(t, 54.6, 55.35, ease.inOut);
  const shrink = 0; // shot 6 arrives by a cold scan wipe

  const yMid = NY + NH / 2;
  const l1x0 = NODES.sshd.x + NW + 10, l1x1 = NODES.sysd.x - 10;
  const l2x0 = NODES.sysd.x + NW + 10, l2x1 = NODES.lzma.x - 10;
  const linkHot = (x0: number, x1: number, tA: number) => {
    // heat runs right to left along a link between tA and tA + 0.55
    const p = prog(t, tA, tA + 0.55, ease.inOut);
    return { p, xEdge: lerp(x1, x0, p) };
  };
  const h2 = linkHot(l2x0, l2x1, 53.45);
  const h1 = linkHot(l1x0, l1x1, 54.0);

  const Link: React.FC<{ x0: number; x1: number; draw: number; hot: { p: number; xEdge: number }; id: string }> = ({ x0, x1, draw, hot, id }) => (
    <g>
      <line x1={x0} x2={lerp(x0, x1 - 14, draw)} y1={yMid} y2={yMid} stroke={C.steel} strokeWidth={4} />
      {draw > 0.95 ? <path d={`M ${x1} ${yMid} l -18 -11 v 22 z`} fill={C.mist} /> : null}
      {draw > 0.5 ? (
        <text x={(x0 + x1) / 2} y={yMid - 22} textAnchor="middle" fill={C.mist} opacity={prog(draw, 0.5, 1)} style={{ fontFamily: SANS, fontSize: 26, fontWeight: 500 }}>
          links
        </text>
      ) : null}
      {hot.p > 0 ? (
        <g>
          <line x1={hot.xEdge} x2={x1} y1={yMid} y2={yMid} stroke={C.heat3} strokeWidth={7} />
          <line x1={hot.xEdge} x2={x1} y1={yMid} y2={yMid} stroke={C.heat2} strokeWidth={18} opacity={0.4} filter="url(#s5glow)" />
          {Array.from({ length: 3 }, (_, k) => {
            const q = ((t * 0.8 + k / 3) % 1);
            const px = lerp(x1, x0, q);
            return px > hot.xEdge ? <circle key={k} cx={px} cy={yMid} r={7} fill={C.heat5} /> : null;
          })}
        </g>
      ) : null}
    </g>
  );

  return (
    <AbsoluteFill>
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} style={{ position: "absolute", inset: 0 }}>
        <defs>
          <filter id="s5glow" x="-30%" y="-80%" width="160%" height="260%">
            <feGaussianBlur stdDeviation="16" />
          </filter>
        </defs>
        <g transform={`translate(${lerp(0, 560, shrink)} ${lerp(0, -230, shrink)}) scale(${lerp(1, 0.42, shrink)})`} opacity={1 - shrink * 0.85}>
          {/* the direct link that does not exist */}
          {direct > 0 && directOut > 0 ? (
            <g opacity={directOut}>
              <path
                d={`M ${NODES.sshd.x + NW / 2} ${NY - 14} C ${NODES.sshd.x + NW / 2} ${NY - 170}, ${NODES.lzma.x + NW / 2} ${NY - 170}, ${NODES.lzma.x + NW / 2} ${NY - 14}`}
                stroke={C.ice} strokeWidth={3} fill="none" strokeDasharray="10 12" pathLength={1000}
                opacity={direct}
                style={{ strokeDasharray: direct < 1 ? `${direct * 1000} 1000` : "12 14" }}
              />
              {strike > 0 ? (
                <g transform={`translate(${(NODES.sshd.x + NODES.lzma.x + NW) / 2} ${NY - 142})`} stroke={C.ice} strokeWidth={6} strokeLinecap="round">
                  <line x1={-26 * strike} y1={-26 * strike} x2={26 * strike} y2={26 * strike} />
                  <line x1={26 * strike} y1={-26 * strike} x2={-26 * strike} y2={26 * strike} />
                </g>
              ) : null}
            </g>
          ) : null}
          <Link id="l1" x0={l1x0} x1={l1x1} draw={link1} hot={h1} />
          <Link id="l2" x0={l2x0} x1={l2x1} draw={link2} hot={h2} />
          <Node n={NODES.sshd} a={aSshd} heat={heatOf(t, "sshd")} />
          <Node n={NODES.sysd} a={aSysd} heat={heatOf(t, "sysd")} />
          <Node n={NODES.lzma} a={aLzma} heat={heatOf(t, "lzma")} />
          {/* function slot inside sshd, rerouted into liblzma */}
          {fn > 0 ? (
            <g opacity={fn}>
              <rect x={NODES.sshd.x} y={NY + NH + 48} width={NW} height={64} rx={10} fill={alpha(C.deep, 0.9)} stroke={reroute > 0.5 ? C.heat2 : C.steel} strokeWidth={2.5} />
              <text x={NODES.sshd.x + 20} y={NY + NH + 90} fill={C.frost} style={{ fontFamily: MONO, fontSize: 27, fontVariationSettings: "'wdth' 87.5, 'wght' 400" }}>
                RSA_public_decrypt
              </text>
              <line x1={NODES.sshd.x + NW / 2} x2={NODES.sshd.x + NW / 2} y1={NY + NH + 4} y2={NY + NH + 46} stroke={C.steel} strokeWidth={2.5} />
              {/* the original target, libcrypto */}
              <g opacity={1 - reroute * 0.75}>
                <line x1={NODES.sshd.x + NW + 4} x2={NODES.sshd.x + NW + 150} y1={NY + NH + 80} y2={NY + NH + 80} stroke={C.ice} strokeWidth={3} strokeDasharray={reroute > 0 ? "6 8" : undefined} />
                <text x={NODES.sshd.x + NW + 166} y={NY + NH + 90} fill={C.ice} style={{ fontFamily: MONO, fontSize: 27, fontVariationSettings: "'wdth' 87.5, 'wght' 400" }}>
                  libcrypto
                </text>
              </g>
              {reroute > 0 ? (
                <path
                  d={`M ${NODES.sshd.x + NW + 4} ${NY + NH + 80} C ${NODES.sshd.x + NW + 520} ${NY + NH + 230}, ${NODES.lzma.x + 60} ${NY + NH + 230}, ${NODES.lzma.x + NW / 2} ${NY + NH + 10}`}
                  stroke={C.heat3} strokeWidth={5} fill="none" pathLength={1000}
                  style={{ strokeDasharray: `${reroute * 1000} 1000` }}
                />
              ) : null}
              {reroute > 0.98 ? <path d={`M ${NODES.lzma.x + NW / 2} ${NY + NH + 8} l -11 18 h 22 z`} fill={C.heat3} /> : null}
            </g>
          ) : null}
        </g>
      </svg>
      <Caption t={t} t0={47.8} tOut={49.9} x={140} y={820} size={56} text="OpenSSH's server, `sshd`, doesn't use liblzma ~directly.~" />
      <Caption t={t} t0={50.1} tOut={52.95} x={140} y={820} size={54} text="But Debian and other distributions patch sshd to notify systemd, and *libsystemd links liblzma.*" />
      <Caption t={t} t0={53.2} tOut={55.4} x={140} y={820} size={54} text="Inside sshd, it hijacks `RSA_public_decrypt`, *before anyone has authenticated.*" />
      <Caption t={t} t0={55.6} x={140} y={820} size={54} text="Setting that up meant parsing symbol tables in memory each time sshd started. *That was the slow part.*" />
    </AbsoluteFill>
  );
};
