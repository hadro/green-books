// tests/smoke_all_volumes.js
//
// Manual smoke test for all-volumes.html. Serves the repo over HTTP, drives
// the page headless, and asserts the load → search → detail → establishments
// → trends → deep-link loop works with zero uncaught page errors.
//
//   cd tests && npm ci                 # once
//   node smoke_all_volumes.js          # PW_CHROMIUM_PATH=<bin> to pin Chromium
//
// Network beyond localhost is not required: font/analytics/CDN-thumbnail
// fetches may fail (console noise) — only `pageerror` (uncaught exceptions)
// and the functional assertions below gate the result.
const { chromium } = require('playwright');
const { spawn } = require('child_process');

const PORT = Number(process.env.TEST_PORT || 8901);
const ORIGIN = `http://127.0.0.1:${PORT}`;
const wait = ms => new Promise(r => setTimeout(r, ms));

async function main() {
  const server = spawn('python3', ['-m', 'http.server', String(PORT)],
    { cwd: __dirname + '/..', stdio: 'ignore' });
  const errors = [];
  let browser;
  try {
    await wait(1000);
    const opts = {};
    const bin = process.env.PW_CHROMIUM_PATH || process.env.CHROMIUM_BIN;
    if (bin) opts.executablePath = bin;
    browser = await chromium.launch(opts);
    const page = await browser.newPage({ viewport: { width: 1280, height: 800 } });
    page.on('pageerror', e => errors.push('pageerror: ' + e.message));

    // 1. Full load: the Establishments button enables only when gbDataLoaded.
    await page.goto(`${ORIGIN}/all-volumes.html`, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('#view-estabs-btn:not([disabled])', { timeout: 120000 });
    const count = await page.textContent('#count-label');
    if (!/of [\d,]+ entries/.test(count)) throw new Error('count label wrong: ' + count);

    // 2. Hero built its three featured cards (placeholder card says "Loading entries…").
    await page.waitForFunction(() =>
      document.querySelectorAll('#hero-featured-stack .gb-hero-card').length >= 3,
      { timeout: 15000 });

    // 3. Search narrows the result set.
    await page.fill('#search', 'idlewild');
    await page.waitForFunction(() => {
      const n = parseInt(document.getElementById('count-label').textContent.replace(/,/g, ''), 10);
      return n > 0 && n < 5000;
    }, { timeout: 5000 });
    await page.fill('#search', '');
    await wait(400); // search debounce + re-render

    // 4. Row click opens the detail panel and syncs ?cf= into the URL.
    await page.click('#table-body tr');
    await page.waitForSelector('#detail.open', { timeout: 5000 });
    const cfUrl = page.url();
    if (!cfUrl.includes('cf=')) throw new Error('?cf= not synced: ' + cfUrl);
    await page.keyboard.press('Escape');
    await page.waitForSelector('#detail:not(.open)', { state: 'attached', timeout: 5000 });

    // 5. Establishments view renders grouped rows.
    await page.click('#view-estabs-btn');
    await page.waitForSelector('table.est-mode #table-body tr', { timeout: 20000 });
    await page.click('#view-listings-btn');

    // 6. Trends modal renders its SVG charts.
    await page.click('#trends-btn');
    await page.waitForSelector('#trend-years svg', { timeout: 10000 });
    await page.keyboard.press('Escape');

    // 7. The ?cf= deep link restores the panel on a fresh load.
    await page.goto(cfUrl, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('#detail.open', { timeout: 120000 });

    if (errors.length) throw new Error('page errors:\n' + errors.join('\n'));
    console.log('SMOKE OK');
  } finally {
    if (browser) await browser.close();
    server.kill();
  }
}
main().catch(e => { console.error('SMOKE FAILED:', e.message || e); process.exit(1); });
