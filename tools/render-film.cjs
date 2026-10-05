// Render a deterministic film to MP4. Every frame is a pure function of t, so frames are
// independent: several pages capture interleaved frames in parallel, then ffmpeg encodes them.
// Usage:
//   node tools/render-film.cjs [--fps=30 --from=0 --to=24 --w=1920 --h=1080 --workers=4]
//                              [--file=pieces/04-injection-film.html --out=out/hidden-instruction.mp4 --keep]
// The page is opened with ?clean=1&t=<from> (canvas only, paused), and each frame is painted
// with window.__seek(t) before a screenshot. Same approach as tools/shot.cjs (global Playwright).
const path = require('path');
const fs = require('fs');
const { execSync, spawnSync } = require('child_process');
const { chromium } = require(path.join(execSync('npm root -g').toString().trim(), 'playwright'));

const opt = Object.fromEntries(process.argv.slice(2).map(a => {
  const [k, ...v] = a.replace(/^--/, '').split('=');
  return [k, v.length ? v.join('=') : 'true'];
}));
const fps = +(opt.fps || 30);
const from = +(opt.from || 0);
const to = +(opt.to || 24);
const w = +(opt.w || 1920);
const h = +(opt.h || 1080);
const workers = Math.max(1, +(opt.workers || 4));
const file = opt.file || 'pieces/04-injection-film.html';
const out = opt.out || 'out/hidden-instruction.mp4';
const dir = opt.frames || 'out/frames';
const n = Math.round((to - from) * fps);

(async () => {
  if (!(n > 0)) throw new Error(`nothing to render: from=${from} to=${to} fps=${fps}`);
  fs.rmSync(dir, { recursive: true, force: true });
  fs.mkdirSync(dir, { recursive: true });
  fs.mkdirSync(path.dirname(out), { recursive: true });
  const url = 'file://' + path.resolve(file) + `?clean=1&t=${from}`;
  console.log(`${n} frames at ${fps} fps, ${w}x${h}, ${workers} workers: ${url}`);

  const started = Date.now();
  const browser = await chromium.launch();
  let done = 0;
  const errors = [];
  const worker = async k => {
    // one context per worker: separate renderer processes, so frames really render in parallel
    const context = await browser.newContext({ viewport: { width: w, height: h }, deviceScaleFactor: 1 });
    const page = await context.newPage();
    page.on('pageerror', e => errors.push(`[worker ${k}] ${e.message}`));
    page.on('console', m => { if (m.type() === 'error') errors.push(`[worker ${k}] ${m.text()}`); });
    await page.goto(url);
    await page.waitForFunction(() => typeof window.__seek === 'function', null, { timeout: 30000 });
    for (let f = k; f < n; f += workers) {
      const t = from + f / fps;
      // paint the frame, then wait one animation frame so the compositor has it
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

  const args = ['-y', '-hide_banner', '-loglevel', 'error', '-framerate', String(fps), '-i', path.join(dir, 'f%05d.png'),
    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '18', out];
  console.log('ffmpeg ' + args.join(' '));
  const ff = spawnSync('ffmpeg', args, { stdio: 'inherit' });
  if (ff.status !== 0) { console.error('ffmpeg failed; frames kept in ' + dir); process.exit(1); }
  if (opt.keep !== 'true') fs.rmSync(dir, { recursive: true, force: true });
  const size = fs.statSync(out).size;
  console.log(`wrote ${out} (${(size / 1e6).toFixed(2)} MB) in ${((Date.now() - started) / 1000).toFixed(1)}s`);
})().catch(e => { console.error(e); process.exit(1); });
