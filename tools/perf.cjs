// Real-GPU frame-rate check. Headless Chromium with --use-angle=metal renders on the Mac's GPU
// (WebGL via ANGLE/Metal, WebGPU via Dawn/Metal), so these numbers reflect real hardware.
//   node tools/perf.cjs [piece-prefix ...] [--w=1440 --h=900 --dpr=2 --secs=5]
// Plays each piece with __play(), warms up, then samples requestAnimationFrame intervals.
const path = require('path');
const fs = require('fs');
const { chromium } = require(path.join(require('child_process').execSync('npm root -g').toString().trim(), 'playwright'));

(async () => {
  const args = process.argv.slice(2);
  const opt = Object.fromEntries(args.filter(a => a.startsWith('--')).map(a => { const [k, ...v] = a.slice(2).split('='); return [k, v.join('=')]; }));
  const filters = args.filter(a => !a.startsWith('--'));
  const w = +(opt.w || 1440), h = +(opt.h || 900), dpr = +(opt.dpr || 2), secs = +(opt.secs || 5);
  const pieces = fs.readdirSync('pieces').filter(f => f.endsWith('.html')).map(f => f.slice(0, -5))
    .filter(n => !filters.length || filters.some(f => n.startsWith(f))).sort();

  const browser = await chromium.launch({ args: ['--use-angle=metal', '--enable-unsafe-webgpu', '--ignore-gpu-blocklist', '--enable-gpu', '--autoplay-policy=no-user-gesture-required'] });
  console.log(`viewport ${w}x${h} @${dpr}x, ${secs}s sample\n`);
  console.log('piece'.padEnd(26), 'median fps'.padStart(10), '5% low'.padStart(8), '>33ms'.padStart(7), '  note');
  for (const name of pieces) {
    const page = await browser.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: dpr });
    const errs = [];
    page.on('pageerror', e => errs.push(e.message));
    let note = '';
    try {
      await page.goto('file://' + path.resolve('pieces', name + '.html'));
      await page.waitForFunction(() => typeof window.__play === 'function', null, { timeout: 90000 });
      await page.waitForTimeout(2500);
      await page.evaluate(() => window.__play());
      await page.waitForTimeout(2000); // warm-up: shader compiles, adaptive quality settles
      const dts = await page.evaluate(secs => new Promise(res => {
        const out = []; let last = performance.now(); const end = last + secs * 1000;
        const tick = now => { out.push(now - last); last = now; if (now < end) requestAnimationFrame(tick); else res(out); };
        requestAnimationFrame(tick);
      }), secs);
      dts.shift();
      const s = [...dts].sort((a, b) => a - b);
      const med = s[Math.floor(s.length / 2)], p95 = s[Math.floor(s.length * 0.95)];
      const long = dts.filter(d => d > 33.4).length;
      if (errs.length) note = 'errors: ' + errs[0].slice(0, 60);
      console.log(name.padEnd(26), (1000 / med).toFixed(0).padStart(10), (1000 / p95).toFixed(0).padStart(8), String(long).padStart(7), ' ', note);
    } catch (e) {
      console.log(name.padEnd(26), 'n/a'.padStart(10), ''.padStart(8), ''.padStart(7), ' ', 'failed: ' + e.message.split('\n')[0].slice(0, 70));
    }
    await page.close();
  }
  await browser.close();
})();
