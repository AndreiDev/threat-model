// Homepage preview loops: 4 seconds of each piece, rendered frame by frame through its own
// __seek(t) on the real GPU (headless Chromium with --use-angle=metal), then encoded with ffmpeg.
//   node tools/previews.cjs [piece-prefix ...] [--workers=3 --fps=20 --secs=4]
// Output: out/previews/<piece>.mp4 (720x450, H.264, no audio, faststart).
const path = require('path');
const fs = require('fs');
const os = require('os');
const { execFileSync } = require('child_process');
const { chromium } = require(path.join(require('child_process').execSync('npm root -g').toString().trim(), 'playwright'));

// Centre of each loop (seconds), and extra query parameters for a fast, deterministic render.
const PIECES = {
  '01-commit-guard': [5.3], '02-zero-trust-mesh': [9.5], '03-cipher-lock': [5.4], '04-injection-film': [9.6],
  '05-token-swarm': [8.6], '06-secure-pipeline': [13], '07-zero-day-intro': [45.6], '08-threat-hunters': [17.2],
  '09-unsafe-eval': [3.7], '10-worm': [11.4], '11-approve-once': [8.4], '12-defense-in-depth': [12],
  '13-transitive': [9.9], '14-rotate-your-keys': [10.5], '15-injection-radar': [22.8, 'fallback=1'],
  '16-codebase-nebula': [15], '17-dark-repo': [13.1], '18-thirty-six-views': [3.55], '20-integrity': [6.9],
  '21-known-exploited': [60.95, 'offline=1'], '22-prompt-injected-1989': [35.5], '23-sandbox': [16.2],
  '24-security-key': [24.25], '26-containment': [16.3], '27-soft-perimeter': [11.2], '28-curve-secret': [249.7],
  '29-keep-the-secret': [22.5], '30-hands-on': [17.5],
};
// Pieces whose page wraps a rendered video: cut the loop straight from the MP4 (start second).
const FROM_VIDEO = { '19-vanitas': ['out/vanitas-timelapse.mp4', 26], '25-five-hundred-ms': ['out/five-hundred-ms.mp4', 1] };

const args = process.argv.slice(2);
const opt = Object.fromEntries(args.filter(a => a.startsWith('--')).map(a => { const [k, ...v] = a.slice(2).split('='); return [k, v.join('=')]; }));
const filters = args.filter(a => !a.startsWith('--'));
const FPS = +(opt.fps || 20), SECS = +(opt.secs || 4), WORKERS = +(opt.workers || 3);
const pick = n => !filters.length || filters.some(f => n.startsWith(f));
fs.mkdirSync('out/previews', { recursive: true });

const encode = (dir, out) => execFileSync('ffmpeg', ['-v', 'error', '-y', '-framerate', String(FPS), '-i', path.join(dir, 'f%03d.jpg'),
  '-vf', 'scale=720:-2:flags=lanczos', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '28', '-preset', 'slow', '-movflags', '+faststart', '-an', out]);

(async () => {
  for (const [name, [src, start]] of Object.entries(FROM_VIDEO)) if (pick(name)) {
    execFileSync('ffmpeg', ['-v', 'error', '-y', '-ss', String(start), '-t', String(SECS), '-i', src, '-vf', `fps=${FPS},scale=720:-2:flags=lanczos`,
      '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '28', '-preset', 'slow', '-movflags', '+faststart', '-an', `out/previews/${name}.mp4`]);
    console.log(`out/previews/${name}.mp4 (from video)`);
  }
  const queue = Object.entries(PIECES).filter(([n]) => pick(n));
  const browser = await chromium.launch({ args: ['--use-angle=metal', '--enable-unsafe-webgpu', '--ignore-gpu-blocklist', '--enable-gpu', '--autoplay-policy=no-user-gesture-required'] });
  const worker = async () => {
    for (let job; (job = queue.shift());) {
      const [name, [centre, query]] = job;
      const t0 = Math.max(0, centre - SECS / 2);
      const dir = fs.mkdtempSync(path.join(os.tmpdir(), `prev-${name}-`));
      const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
      try {
        await page.goto('file://' + path.resolve('pieces', name + '.html') + (query ? '?' + query : ''));
        await page.waitForFunction(() => typeof window.__seek === 'function', null, { timeout: 120000 });
        await page.addStyleTag({ content: '.notes,.show-notes{display:none!important}' });
        await page.waitForTimeout(3000);
        const n = Math.round(SECS * FPS);
        for (let i = 0; i < n; i++) {
          await page.evaluate(t => window.__seek(t), t0 + i / FPS);
          await page.evaluate(() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r))));
          await page.screenshot({ path: path.join(dir, `f${String(i).padStart(3, '0')}.jpg`), type: 'jpeg', quality: 88 });
        }
        encode(dir, `out/previews/${name}.mp4`);
        console.log(`out/previews/${name}.mp4`);
      } catch (e) {
        console.log(`${name} failed: ${e.message.split('\n')[0]}`);
      }
      await page.close();
      fs.rmSync(dir, { recursive: true, force: true });
    }
  };
  await Promise.all(Array.from({ length: WORKERS }, worker));
  await browser.close();
})();
