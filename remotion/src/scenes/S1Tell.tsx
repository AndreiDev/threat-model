// Shot 1, 0:00-0:09.5. The tell: a failed SSH login reaches its usual 0.299 s and keeps going.
import React from "react";
import { AbsoluteFill, useCurrentFrame, useVideoConfig } from "remotion";
import { C, alpha } from "../lib/color";
import { MONO, SANS } from "../lib/fonts";
import { ease, prog, lerp } from "../lib/motion";
import { Caption, KineticType, Typed } from "../components/Type";
import { LatencyMeter, meterOvershoot, meterValue, valueColor } from "../components/LatencyMeter";
import { W, H } from "../components/Hud";
import cues from "../cues.json";

const M = cues.meter1;

export const S1Tell: React.FC<{ start: number }> = ({ start }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = start + frame / fps;

  const v = meterValue(t, M);
  const col = valueColor(v);
  const hot = v > M.usual + 0.004;
  const exitTop = prog(t, 5.9, 6.6, ease.in); // terminal + counter leave
  const slim = prog(t, 6.0, 6.9, ease.inOut);
  const meterY = lerp(742, 640, slim);
  const bracket = prog(t, M.tStop + 0.15, M.tStop + 0.75, ease.out) * (1 - prog(t, 5.9, 6.4));

  const termStyle: React.CSSProperties = {
    fontFamily: MONO, fontSize: 32, fontVariationSettings: "'wdth' 87.5, 'wght' 400", lineHeight: 1.5,
  };
  return (
    <AbsoluteFill>
      {/* terminal */}
      <div style={{ position: "absolute", left: 140, top: 104, opacity: 1 - exitTop, transform: `translateY(${-exitTop * 40}px)` }}>
        <Typed
          t={t} t0={0.02} cps={64} caret={t < M.tStop}
          text="time ssh nonexistant@localhost"
          prefix={<span style={{ color: C.mist }}>$ </span>}
          style={{ ...termStyle, color: C.frost }}
        />
        <Typed t={t} t0={M.tStop + 0.08} cps={260} text="nonexistant@localhost: Permission denied (publickey)." style={{ ...termStyle, color: C.mist }} />
        {t >= M.tStop + 0.3 ? (
          <div style={{ ...termStyle, color: C.frost, whiteSpace: "pre" }}>
            {"real    0m"}
            <span style={{ color: C.heat3 }}>0.807s</span>
          </div>
        ) : null}
      </div>

      {/* counter */}
      <div
        style={{
          position: "absolute", left: 128, top: 300, opacity: 1 - exitTop, transform: `translateY(${-exitTop * 60}px)`,
          display: "flex", alignItems: "baseline", gap: 24,
        }}
      >
        <span
          style={{
            fontFamily: MONO, fontSize: 236, lineHeight: 1, color: col,
            fontVariationSettings: `'wdth' 100, 'wght' ${hot ? 340 : 280}`,
            textShadow: hot ? `0 0 60px ${alpha(C.heat2, 0.35 * prog(v, 0.3, 0.8))}` : "none",
          }}
        >
          {v.toFixed(3)}
        </span>
        <span style={{ fontFamily: MONO, fontSize: 84, color: C.mist, fontVariationSettings: "'wdth' 100, 'wght' 300" }}>s</span>
        <span style={{ fontFamily: SANS, fontSize: 34, fontWeight: 500, color: C.mist, marginLeft: 36, maxWidth: 520, lineHeight: 1.25, alignSelf: "center" }}>
          one login that fails,
          <br />
          timed end to end
        </span>
      </div>

      {/* meter */}
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} style={{ position: "absolute", inset: 0 }}>
        <LatencyMeter
          id="m1" value={v} overshoot={meterOvershoot(t, M)} x={140} y={meterY} width={1600}
          furniture={1 - slim * 0.55} bracket={bracket} slim={slim}
        />
      </svg>

      <Caption
        t={t} t0={M.tStop + 0.75} tOut={5.75} x={140} y={862} size={62}
        text="Same failed login. *Half a second slower.*"
      />

      {/* title */}
      <div style={{ position: "absolute", left: 132, top: 230 }}>
        <KineticType t={t} t0={6.25} text="Five hundred" size={156} />
        <KineticType t={t} t0={6.25 + 12 * (1.1 / 30)} text="milliseconds" size={156} />
      </div>
      <Caption
        t={t} t0={7.25} x={140} y={720} size={44} color={C.mist} width={1560}
        text="How an extra half second exposed the backdoor in xz-utils, `CVE-2024-3094`"
      />
    </AbsoluteFill>
  );
};
