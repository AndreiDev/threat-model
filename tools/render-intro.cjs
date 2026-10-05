// Render the demoscene intro (pieces/07-zero-day-intro.html) to an MP4 with its own soundtrack.
// Every frame is a pure function of t, so several pages capture interleaved frames in parallel via
// window.__seek(t). The audio is not recorded: the page renders its OfflineAudioContext track again
// (deterministic), returns it as 16-bit PCM WAV in base64 chunks, and ffmpeg muxes H.264 + AAC.
// Usage:
//   node tools/render-intro.cjs [--fps=30 --from=0 --to=64 --w=1920 --h=1080 --workers=6]
//                               [--file=pieces/07-zero-day-intro.html --out=out/zero-day.mp4]
//                               [--crf=28 --maxrate=9M --frames=<tmp dir> --keep --gpu=swiftshader]
// Same Playwright resolution as tools/shot.cjs (global install via `npm root -g`).
const path = require('path');
const fs = require('fs');
const os = require('os');
const { execSync, spawnSync } = require('child_process');
const { chromium } = require(path.join(execSync('npm root -g').toString().trim(), 'playwright'));

const opt = Object.fromEntries(process.argv.slice(2).map(a => {
  const [k, ...v] = a.replace(/^--/, '').split('=');
  return [k, v.length ? v.join('=') : 'true'];
}));
const fps = +(opt.fps || 30);
const from = +(opt.from || 0);
const to = +(opt.to || 64);
const w = +(opt.w || 1920);
const h = +(opt.h || 1080);
const workers = Math.max(1, +(opt.workers || 6));
// the tunnel's fast-moving code texture is expensive to encode. CRF 28 + veryslow + aq-mode 3 gives ~35 MB, visually
// indistinguishable at 100% from CRF 23 (62 MB) and under GitHub's 50 MB recommended file size
const crf = String(opt.crf || 28);
const maxrate = opt.maxrate || '9M';
const file = opt.file || 'pieces/07-zero-day-intro.html';
const out = opt.out || 'out/zero-day.mp4';
const dir = opt.frames || path.join(os.tmpdir(), `zero-day-frames-${process.pid}`);
const n = Math.round((to - from) * fps);
// Headless Chromium can use the real GPU (Metal on macOS), which makes the raymarched shots fast;
// --gpu=swiftshader forces the software rasteriser used by tools/shot.cjs.
const gpuArgs = opt.gpu === 'swiftshader' || process.platform !== 'darwin'
  ? ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist']
  : ['--use-angle=metal', '--ignore-gpu-blocklist', '--enable-gpu'];

async function openPage(browser, k, errors){
  const context = await browser.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1 });
  const page = await context.newPage();
  page.on('pageerror', e => errors.push(`[page ${k}] ${e.message}`));
  page.on('console', m => { if (m.type() === 'error') errors.push(`[page ${k}] ${m.text()}`); });
  // clean: canvas only (no notes card, no start gate); t: start paused
  await page.goto('file://' + path.resolve(file) + `?clean=1&t=${from}`);
  await page.waitForFunction(() => window.__ready === true, null, { timeout: 60000 });
  return { context, page };
}

(async () => {
  if (!(n > 0)) throw new Error(`nothing to render: from=${from} to=${to} fps=${fps}`);
  fs.rmSync(dir, { recursive: true, force: true });
  fs.mkdirSync(dir, { recursive: true });
  fs.mkdirSync(path.dirname(out), { recursive: true });
  console.log(`${n} frames at ${fps} fps, ${w}x${h}, ${workers} workers (${gpuArgs[0]}) -> ${out}`);
  const started = Date.now();
  const browser = await chromium.launch({ args: gpuArgs });
  const errors = [];

  // 1. the soundtrack, as the page synthesises it
  const wavPath = path.join(dir, 'soundtrack.wav');
  {
    const { context, page } = await openPage(browser, 'audio', errors);
    const info = await page.evaluate(() => window.__wavPrepare());
    const parts = [];
    for (let i = 0; i < info.chunks; i++) parts.push(Buffer.from(await page.evaluate(i => window.__wavChunk(i), i), 'base64'));
    const wav = Buffer.concat(parts);
    if (wav.length !== info.bytes) throw new Error(`wav size mismatch ${wav.length} != ${info.bytes}`);
    fs.writeFileSync(wavPath, wav);
    console.log(`  soundtrack: ${(wav.length / 1e6).toFixed(1)} MB WAV in ${info.chunks} chunks`);
    await context.close();
  }

  // 2. frames, interleaved across workers
  let done = 0;
  const worker = async k => {
    const { context, page } = await openPage(browser, k, errors);
    for (let f = k; f < n; f += workers){
      const t = from + f / fps;
      await page.evaluate(t => new Promise(r => { window.__seek(t); requestAnimationFrame(() => r()); }), t);
      await page.screenshot({ path: path.join(dir, `f${String(f).padStart(5, '0')}.png`) });
      done++;
      if (done % 30 === 0 || done === n) process.stdout.write(`\r  captured ${done}/${n}`);
    }
    await context.close();
  };
  await Promise.all(Array.from({ length: workers }, (_, k) => worker(k)));
  await browser.close();
  process.stdout.write(`\n  capture took ${((Date.now() - started) / 1000).toFixed(1)}s\n`);
  if (errors.length) console.log(errors.join('\n'));

  // 3. mux: H.264 video + AAC audio, trimmed to the rendered range
  const dur = (n / fps).toFixed(3);
  const args = ['-y', '-hide_banner', '-loglevel', 'error',
    '-framerate', String(fps), '-i', path.join(dir, 'f%05d.png'),
    '-ss', String(from), '-t', dur, '-i', wavPath,
    '-map', '0:v:0', '-map', '1:a:0',
    '-c:v', 'libx264', '-preset', 'veryslow', '-crf', crf, '-x264-params', 'aq-mode=3', '-maxrate', maxrate, '-bufsize', String(parseFloat(maxrate) * 2) + 'M', '-pix_fmt', 'yuv420p',
    '-c:a', 'aac', '-b:a', '160k', '-ar', '44100',
    '-t', dur, '-movflags', '+faststart', out];
  console.log('ffmpeg ' + args.join(' '));
  const ff = spawnSync('ffmpeg', args, { stdio: 'inherit' });
  if (ff.status !== 0){ console.error('ffmpeg failed; frames kept in ' + dir); process.exit(1); }
  if (opt.keep !== 'true') fs.rmSync(dir, { recursive: true, force: true });
  else console.log('frames kept in ' + dir);

  // 4. report what was written
  const probe = spawnSync('ffprobe', ['-v', 'error', '-show_entries', 'stream=codec_type,codec_name,width,height,duration', '-of', 'compact', out]);
  console.log(probe.stdout.toString().trim());
  console.log(`wrote ${out} (${(fs.statSync(out).size / 1e6).toFixed(2)} MB) in ${((Date.now() - started) / 1000).toFixed(1)}s`);
})().catch(e => { console.error(e); process.exit(1); });
