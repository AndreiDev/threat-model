// Shot 3, 0:14.5-0:33.5. The long game: a timeline ribbon from Oct 2021 to Mar 2024.
// The persona's access climbs as a stepped hot line; the maintainer is a cold line underneath.
import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import { C, alpha, ironbow } from "../lib/color";
import { MONO, SANS } from "../lib/fonts";
import { clamp01, ease, keys, lerp, prog, springAt, hash } from "../lib/motion";
import { Caption } from "../components/Type";
import { W, H } from "../components/Hud";

// ---- world: dates to x -------------------------------------------------------------------
const DAY0 = Date.UTC(2021, 9, 1);
const days = (iso: string) => {
  const [y, m, d] = iso.split("-").map(Number);
  return (Date.UTC(y, m - 1, d) - DAY0) / 864e5;
};
const PX_PER_DAY = 4.2;
const wx = (iso: string) => 300 + days(iso) * PX_PER_DAY;
const AXIS = 720;
const MAINT_Y = 905;
const PLAYHEAD_X = 1250;
export const HEX_EXIT = { x: PLAYHEAD_X, y: AXIS };

// Persona access (steps), from Russ Cox's timeline.
const STEPS: { date: string; y: number; label: string }[] = [
  { date: "2021-10-29", y: 664, label: "first patch" },
  { date: "2022-02-07", y: 604, label: "first commit merged" },
  { date: "2022-06-29", y: 528, label: "“co-maintainer”" },
  { date: "2023-03-18", y: 452, label: "makes releases" },
  { date: "2024-02-24", y: 380, label: "ships 5.6.0" },
];
const STEP_END = "2024-03-29";

type Ev = {
  t: number; date: string; dateLabel: string; body: string; extra?: string; extraCold?: boolean;
  hot: boolean; onMaint?: boolean;
};
// Times are absolute seconds in the film.
const EVENTS: Ev[] = [
  { t: 14.75, date: "2021-10-29", dateLabel: "29 Oct 2021", hot: true, body: "A new contributor, *“Jia Tan”,* sends a first, harmless patch." },
  { t: 17.6, date: "2022-04-22", dateLabel: "Apr to Jun 2022", hot: true, body: "New accounts on the mailing list press the maintainer to move faster.", extra: "“Patches spend years on this mailing list.”" },
  { t: 20.6, date: "2022-06-08", dateLabel: "8 Jun 2022", hot: false, onMaint: true, body: "~“It's also good to keep in mind that this is an unpaid hobby project.”~", extra: "Lasse Collin, replying", extraCold: true },
  { t: 24.0, date: "2022-06-29", dateLabel: "29 Jun 2022", hot: true, body: "The maintainer calls Jia Tan *“practically a co-maintainer already.”*" },
  { t: 26.4, date: "2023-03-18", dateLabel: "18 Mar 2023", hot: true, body: "Jia Tan tags a release for the first time: *5.4.2.*" },
  { t: 28.8, date: "2024-02-23", dateLabel: "23 Feb 2024", hot: true, body: "Test files carrying a hidden payload are committed." },
  { t: 30.9, date: "2024-02-24", dateLabel: "24 Feb 2024", hot: true, body: "*xz 5.6.0* is released. *5.6.1* follows on 9\u00A0March." },
];
// Where the playhead travels to for each event (lets the line pass intermediate steps).
const PLAY_TO = ["2021-11-20", "2022-04-22", "2022-06-08", "2022-07-10", "2023-03-30", "2024-02-23", "2024-03-09"];
// Pressure messages landing on the maintainer line (illustrative positions, Apr to Jun 2022).
const CHIPS = ["2022-04-22", "2022-05-06", "2022-05-19", "2022-05-27", "2022-06-07", "2022-06-14"];

const camAndPlay = (t: number) => {
  const camT: [number, number, (x: number) => number][] = [[14.5, wx(EVENTS[0].date) - PLAYHEAD_X, ease.inOut]];
  const playT: [number, number, (x: number) => number][] = [[14.5, wx("2021-10-08"), ease.inOut]];
  EVENTS.forEach((e, i) => {
    const target = wx(PLAY_TO[i]);
    camT.push([e.t - 0.25, camT[camT.length - 1][1], ease.inOut]);
    camT.push([e.t + 0.75, target - PLAYHEAD_X, ease.inOut]);
    playT.push([e.t - 0.25, playT[playT.length - 1][1], ease.inOut]);
    playT.push([e.t + 0.75, target, ease.inOut]);
  });
  return { cam: keys(t, camT), play: keys(t, playT) };
};

const heatAt = (x: number) => ironbow(0.12 + 0.82 * clamp01((x - wx("2021-10-29")) / (wx("2024-02-24") - wx("2021-10-29"))));

const Card: React.FC<{ e: Ev; t: number; tOut: number }> = ({ e, t, tOut }) => {
  const a = prog(t, e.t + 0.1, e.t + 0.45, ease.out) * (1 - prog(t, tOut, tOut + 0.3));
  const dateCol = e.hot ? heatAt(wx(e.date)) : C.ice;
  return (
    <>
      <div
        style={{
          position: "absolute", left: 140, top: 128, opacity: a, color: dateCol,
          fontFamily: MONO, fontSize: 32, fontVariationSettings: "'wdth' 100, 'wght' 400",
          transform: `translateY(${(1 - a) * 10}px)`,
        }}
      >
        {e.dateLabel}
      </div>
      <Caption t={t} t0={e.t + 0.18} tOut={tOut} x={140} y={180} size={52} width={1040} text={e.body} hot={C.heat3} cold={C.frost} lineHeight={1.2} />
      {e.extra ? (
        <Caption
          t={t} t0={e.t + 0.7} tOut={tOut} x={140} y={e.onMaint ? 370 : 320} size={e.extraCold ? 32 : 38} width={980} text={e.extra}
          color={e.extraCold ? C.mist : C.heat2} wght={e.extraCold ? 400 : 500}
        />
      ) : null}
    </>
  );
};

export const S3LongGame: React.FC<{ start: number }> = ({ start }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = start + frame / fps;
  const { cam, play } = camAndPlay(t);
  const sx = (x: number) => x - cam;
  const enter = prog(t, 14.5, 14.9, ease.out);
  const flare = prog(t, 31.6, 32.1, ease.out) * (1 - prog(t, 32.4, 33.2, ease.in) * 0.5);

  // stepped access path in world space
  let d = `M ${wx(STEPS[0].date)} ${AXIS}`;
  STEPS.forEach((s, i) => {
    d += ` V ${s.y}`;
    const next = i < STEPS.length - 1 ? STEPS[i + 1].date : STEP_END;
    d += ` H ${wx(next)}`;
  });

  const years = [
    { y: "2022", x: wx("2022-01-01") },
    { y: "2023", x: wx("2023-01-01") },
    { y: "2024", x: wx("2024-01-01") },
  ];
  const months: number[] = [];
  for (let y = 2021; y <= 2024; y++) for (let m = 1; m <= 12; m++) {
    const iso = `${y}-${String(m).padStart(2, "0")}-01`;
    if (days(iso) >= 0 && days(iso) <= days("2024-04-01")) months.push(wx(iso));
  }

  return (
    <AbsoluteFill style={{ opacity: enter }}>
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} style={{ position: "absolute", inset: 0 }}>
        <defs>
          <linearGradient id="access" gradientUnits="userSpaceOnUse" x1={wx("2021-10-29")} y1={0} x2={wx("2024-02-24")} y2={0}>
            {[0, 0.25, 0.5, 0.75, 1].map((p) => (
              <stop key={p} offset={`${p * 100}%`} stopColor={ironbow(0.12 + 0.82 * p)} />
            ))}
          </linearGradient>
          <filter id="s3glow" x="-10%" y="-50%" width="120%" height="200%">
            <feGaussianBlur stdDeviation="8" />
          </filter>
          <filter id="s3flare" x="-100%" y="-100%" width="300%" height="300%">
            <feGaussianBlur stdDeviation="30" />
          </filter>
          <clipPath id="played">
            <rect x={-10000} y={0} width={10000 + play} height={H} />
          </clipPath>
        </defs>
        <g transform={`translate(${-cam} 0)`}>
          {/* months and years */}
          {months.map((x, i) => (
            <line key={i} x1={x} x2={x} y1={AXIS - 8} y2={AXIS + 8} stroke={alpha(C.steel, 0.6)} strokeWidth={1.5} />
          ))}
          <line x1={wx("2021-10-01") - 1600} x2={wx("2021-10-01")} y1={AXIS} y2={AXIS} stroke={alpha(C.steel, 0.5)} strokeWidth={2} strokeDasharray="4 10" />
          <line x1={wx("2021-10-01")} x2={wx("2024-04-01")} y1={AXIS} y2={AXIS} stroke={C.steel} strokeWidth={2.5} />
          {years.map((yr) => (
            <g key={yr.y}>
              <line x1={yr.x} x2={yr.x} y1={AXIS - 22} y2={AXIS + 22} stroke={C.mist} strokeWidth={2.5} />
              <text x={yr.x + 14} y={AXIS + 74} fill={C.mist} style={{ fontFamily: MONO, fontSize: 56, fontVariationSettings: "'wdth' 112.5, 'wght' 200" }}>
                {yr.y}
              </text>
            </g>
          ))}
          <text x={wx("2021-10-01") + 4} y={AXIS + 74} fill={alpha(C.mist, 0.7)} style={{ fontFamily: MONO, fontSize: 40, fontVariationSettings: "'wdth' 112.5, 'wght' 200" }}>
            2021
          </text>
          {/* maintainer line (cold) */}
          <line x1={wx("2021-10-01") - 1600} x2={wx("2024-04-01")} y1={MAINT_Y} y2={MAINT_Y} stroke={alpha(C.ice, 0.55)} strokeWidth={3} />
          {/* pressure chips */}
          {CHIPS.map((c, i) => {
            const t0 = 18.2 + i * 0.28;
            const p = prog(t, t0, t0 + 0.55, ease.in);
            if (p <= 0) return null;
            const land = springAt(t - (t0 + 0.55), 260, 12);
            // the messages pile up on the maintainer
            const x1 = wx("2022-05-20") + (i % 2 ? 22 : -22), y1 = MAINT_Y - 26 - i * 30;
            const x0 = x1 + 520 + hash(i, 3) * 200, y0 = 260 + hash(i, 9) * 120;
            const x = lerp(x0, x1, p), y = lerp(y0, y1, p) + (p >= 1 ? (1 - land) * 10 : 0);
            const fade = 1 - prog(t, 23.6, 24.4) * 0.6;
            return (
              <g key={c} transform={`translate(${x} ${y}) rotate(${(1 - p) * (hash(i, 4) * 40 - 20)})`} opacity={fade}>
                <rect x={-26} y={-17} width={52} height={34} rx={5} fill={alpha(C.heat2, 0.2)} stroke={C.heat2} strokeWidth={2.5} />
                <path d="M -26 -15 L 0 4 L 26 -15" fill="none" stroke={C.heat2} strokeWidth={2.5} />
              </g>
            );
          })}
          {/* the access line, revealed up to the playhead */}
          <g clipPath="url(#played)">
            <path d={d} stroke="url(#access)" strokeWidth={10} fill="none" opacity={0.55} filter="url(#s3glow)" />
            <path d={d} stroke="url(#access)" strokeWidth={4.5} fill="none" strokeLinejoin="round" />
          </g>
          {STEPS.map((s, i) => {
            const x = wx(s.date);
            const on = prog(play, x - 10, x + 60);
            return (
              <text key={s.label} x={x + 16} y={s.y - 18} fill={heatAt(x)} opacity={on}
                style={{ fontFamily: SANS, fontSize: 30, fontWeight: 500 }}>
                {s.label}
              </text>
            );
          })}
          {/* event markers */}
          {EVENTS.map((e, i) => {
            const x = wx(e.date);
            const pop = springAt(t - (e.t + 0.5), 220, 12);
            if (pop <= 0) return null;
            const y = e.onMaint ? MAINT_Y : AXIS;
            const col = e.hot ? heatAt(x) : C.ice;
            return (
              <g key={i}>
                <circle cx={x} cy={y} r={13 * pop} fill={C.void} stroke={col} strokeWidth={4} />
                <circle cx={x} cy={y} r={5 * pop} fill={col} />
              </g>
            );
          })}
          {/* 5.6.0 flare */}
          {flare > 0 ? (
            <g>
              <circle cx={wx("2024-02-24")} cy={380} r={140 * flare} fill={C.heat4} opacity={0.45 * flare} filter="url(#s3flare)" />
              <circle cx={wx("2024-02-24")} cy={380} r={18 + 10 * flare} fill={C.heat5} opacity={flare} />
            </g>
          ) : null}
        </g>
        {/* playhead (screen space) */}
        <line x1={PLAYHEAD_X} x2={PLAYHEAD_X} y1={130} y2={MAINT_Y + 20} stroke={alpha(C.mist, 0.45)} strokeWidth={2} strokeDasharray="4 8" />
      </svg>
      {/* pinned labels */}
      <div style={{ position: "absolute", left: 140, top: MAINT_Y + 22, fontFamily: SANS, fontSize: 30, fontWeight: 500, color: C.ice }}>
        Lasse Collin, maintainer
      </div>
      {EVENTS.map((e, i) => (
        <Card key={i} e={e} t={t} tOut={i < EVENTS.length - 1 ? EVENTS[i + 1].t - 0.35 : 99} />
      ))}
    </AbsoluteFill>
  );
};
