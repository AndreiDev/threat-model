/*
 * Registers the composition. Render with one command from remotion/:
 *   npm run render   (= node scripts/make-audio.mjs && npx remotion render FiveHundredMs ../out/five-hundred-ms.mp4)
 */
import React from "react";
import { Composition } from "remotion";
import { FiveHundredMs } from "./FiveHundredMs";
import cues from "./cues.json";

export const RemotionRoot: React.FC = () => (
  <Composition
    id="FiveHundredMs"
    component={FiveHundredMs}
    durationInFrames={Math.round(cues.duration * cues.fps)}
    fps={cues.fps}
    width={1920}
    height={1080}
  />
);
