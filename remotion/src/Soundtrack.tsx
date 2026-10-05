// Optional synthesised soundtrack. `node scripts/make-audio.mjs` writes public/soundtrack.wav;
// set HAS_SOUNDTRACK to false to render silently.
import React from "react";
import { Audio } from "@remotion/media";
import { staticFile } from "remotion";

export const HAS_SOUNDTRACK = true;

export const Soundtrack: React.FC = () => (HAS_SOUNDTRACK ? <Audio src={staticFile("soundtrack.wav")} /> : null);
