// Render settings for "Five hundred milliseconds".
// One command, from this folder:  npm run render
// (synthesises public/soundtrack.wav, then: npx remotion render FiveHundredMs ../out/five-hundred-ms.mp4)
import { Config } from "@remotion/cli/config";

Config.setVideoImageFormat("jpeg");
Config.setJpegQuality(92);
Config.setCodec("h264");
Config.setCrf(20);
Config.setPixelFormat("yuv420p");
Config.setOverwriteOutput(true);
