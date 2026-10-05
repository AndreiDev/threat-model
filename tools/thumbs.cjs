// Gallery thumbnails: capture each piece at its hero time with the notes card hidden.
//   node tools/thumbs.cjs [only-this-prefix]
const path = require('path');
const { chromium } = require(path.join(require('child_process').execSync('npm root -g').toString().trim(), 'playwright'));
const HEROES = [
  ['01-commit-guard', 5.3],
  ['02-zero-trust-mesh', 9.5],
  ['03-cipher-lock', 5.4],
  ['04-injection-film', 9.6],
  ['05-token-swarm', 8.6],
  ['06-secure-pipeline', 13],
];
(async () => {
  const only = process.argv[2];
  const browser = await chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist', '--enable-unsafe-webgpu'] });
  for (const [name, t] of HEROES.filter(([n]) => !only || n.startsWith(only))) {
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    page.on('pageerror', e => console.log(`[${name}] pageerror ${e.message}`));
    await page.goto('file://' + path.resolve('pieces', name + '.html'));
    await page.waitForFunction(() => typeof window.__seek === 'function', null, { timeout: 20000 });
    await page.addStyleTag({ content: '.notes,.show-notes{display:none!important}' });
    await page.waitForTimeout(2500);
    await page.evaluate(t => window.__seek(t), t);
    await page.waitForTimeout(600);
    const out = `out/thumbs/${name}.png`;
    await page.screenshot({ path: out });
    console.log(out, `t=${t}`);
    await page.close();
  }
  await browser.close();
})();
