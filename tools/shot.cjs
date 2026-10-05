// Deterministic frame capture: every piece exposes window.__seek(t) which paints
// the exact frame for time t and pauses. Usage:
//   node tools/shot.cjs <file.html> <t1,t2,...> [--w=1280 --h=800 --out=out/shots/name]
//   --q=low        appends ?q=low          --query=a=1&b=2  appends a raw query string
//   --clean        hides the notes card    --name=path.png  exact output path (single time only)
const path = require('path');
const { chromium } = require(path.join(require('child_process').execSync('npm root -g').toString().trim(), 'playwright'));
(async () => {
  const [file, times = '0', ...rest] = process.argv.slice(2);
  const opt = Object.fromEntries(rest.map(a => { const [k, ...v] = a.replace(/^--/, '').split('='); return [k, v.join('=')]; }));
  const w = +(opt.w || 1280), h = +(opt.h || 800);
  const base = opt.out || path.join('out/shots', path.basename(file, '.html'));
  const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--enable-unsafe-webgpu'] });
  const page = await browser.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: +(opt.dpr || 1) });
  const logs = [];
  page.on('console', m => logs.push(`[${m.type()}] ${m.text()}`));
  page.on('pageerror', e => logs.push(`[pageerror] ${e.message}`));
  const qs = [opt.q && 'q=' + opt.q, opt.query].filter(Boolean).join('&');
  await page.goto('file://' + path.resolve(file) + (qs ? '?' + qs : ''));
  await page.waitForFunction(() => typeof window.__seek === 'function', null, { timeout: 20000 }).catch(() => logs.push('[warn] no __seek'));
  if ('clean' in opt) await page.addStyleTag({ content: '.notes,.show-notes{display:none!important}' });
  await page.waitForTimeout(+(opt.wait || 600));
  for (const t of times.split(',').map(Number)) {
    await page.evaluate(t => window.__seek && window.__seek(t), t);
    await page.waitForTimeout(+(opt.settle || 120));
    const out = opt.name || `${base}_t${String(t).replace('.', 'p')}.png`;
    await page.screenshot({ path: out });
    console.log(out);
  }
  if (logs.length) console.log(logs.join('\n'));
  await browser.close();
})();
