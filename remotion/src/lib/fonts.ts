// Fonts are local woff2 files (downloaded from Google Fonts, SIL OFL) so renders work offline.
// Martian Mono is the variable build with both axes: wdth 75-112.5 and wght 100-800.
import { loadFont } from "@remotion/fonts";
import { staticFile } from "remotion";

export const MONO = "'Martian Mono', ui-monospace, monospace";
export const SANS = "'Schibsted Grotesk', system-ui, sans-serif";

loadFont({
  family: "Martian Mono",
  url: staticFile("fonts/MartianMono-latin-var.woff2"),
  weight: "100 800",
  stretch: "75% 112.5%",
});
loadFont({
  family: "Schibsted Grotesk",
  url: staticFile("fonts/SchibstedGrotesk-latin-var.woff2"),
  weight: "400 600",
});

/** Inline style for Martian Mono at a given width/weight (axes are animatable material). */
export const mono = (size: number, wght = 400, wdth = 100): React.CSSProperties => ({
  fontFamily: MONO,
  fontSize: size,
  fontVariationSettings: `'wdth' ${wdth}, 'wght' ${wght}`,
  fontWeight: wght,
});
export const sans = (size: number, wght = 500): React.CSSProperties => ({
  fontFamily: SANS,
  fontSize: size,
  fontWeight: wght,
});
