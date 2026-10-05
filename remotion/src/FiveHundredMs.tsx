/*
 * "Five hundred milliseconds": the xz-utils backdoor (CVE-2024-3094) as a Remotion film.
 * 1920x1080, 30 fps, 89 s. Every frame is a pure function of the frame number.
 *
 * Render (from remotion/):   npm install && npm run render
 *   which runs:              node scripts/make-audio.mjs   (synthesises public/soundtrack.wav)
 *                            npx remotion render FiveHundredMs ../out/five-hundred-ms.mp4
 * Preview:                   npx remotion studio
 * Silent render:             set HAS_SOUNDTRACK = false in src/Soundtrack.tsx
 *
 * Shot timings live in src/cues.json, shared with the audio script. Sources: SOURCES.md.
 */
import React from "react";
import { AbsoluteFill, Sequence, useCurrentFrame, useVideoConfig } from "remotion";
import { Backdrop, ScanBand, ThermalScale, W, wipeX } from "./components/Hud";
import { S1Tell } from "./scenes/S1Tell";
import { S2Library } from "./scenes/S2Library";
import { S3LongGame } from "./scenes/S3LongGame";
import { S4Shipped } from "./scenes/S4Shipped";
import { S5Sshd } from "./scenes/S5Sshd";
import { S6Half } from "./scenes/S6Half";
import { S7Caught, S8Change, S9End } from "./scenes/S7to9";
import { Soundtrack } from "./Soundtrack";
import cues from "./cues.json";
import "./lib/fonts";

const COMPONENTS: Record<string, React.FC<{ start: number }>> = {
  tell: S1Tell, library: S2Library, longgame: S3LongGame, shipped: S4Shipped,
  sshd: S5Sshd, half: S6Half, caught: S7Caught, change: S8Change, end: S9End,
};

/** Clips a scene during a scan-band wipe: the outgoing shot is cut away left of the band. */
const WipeClip: React.FC<{ t: number; start: number; end: number; children: React.ReactNode }> = ({ t, start, end, children }) => {
  let clip: string | undefined;
  for (const w of cues.wipes) {
    const x = wipeX(t, w);
    if (x == null) continue;
    if (Math.abs(w.t - start) < 1e-6) clip = `inset(0 ${Math.max(0, W - x)}px 0 0)`;
    if (Math.abs(w.t + w.dur - end) < 1e-6) clip = `inset(0 0 0 ${Math.max(0, x)}px)`;
  }
  return <AbsoluteFill style={{ clipPath: clip }}>{children}</AbsoluteFill>;
};

export const FiveHundredMs: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const t = frame / fps;
  return (
    <AbsoluteFill style={{ background: "#100C2A" }}>
      <Backdrop />
      {cues.scenes.map((s) => {
        const Comp = COMPONENTS[s.id];
        return (
          <Sequence key={s.id} name={s.title} from={Math.round(s.start * fps)} durationInFrames={Math.round((s.end - s.start) * fps)} premountFor={fps}>
            <WipeClip t={t} start={s.start} end={s.end}>
              <Comp start={s.start} />
            </WipeClip>
          </Sequence>
        );
      })}
      <ScanBand t={t} />
      <ThermalScale t={t} />
      <Soundtrack />
    </AbsoluteFill>
  );
};
