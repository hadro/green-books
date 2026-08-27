// Viewer test suite for the green-books Clover integration (viewer.html).
//
// Run via tests/run.sh (which builds the serving copy and starts server.py).
// Chromium resolution: PW_CHROMIUM_PATH or CHROMIUM_BIN env var wins;
// otherwise Playwright's own installed browser is used.
//
// Four scenarios (fresh browser context each): desktop/mobile x fast/slow.
// "Slow" delays every fake-IIIF response by 7s to reproduce the cold-NYPL
// load that historically broke zoom-to-segment. The observable "zoomed to
// segment" signal is the content-state overlay button's bounding rect
// occupying a substantial, centered portion of the viewer.
const { chromium } = require('playwright');
const http = require('http');

const PORT = Number(process.env.TEST_PORT || 8765);
const ORIGIN = `http://127.0.0.1:${PORT}`;
const CANVAS_ID = `${ORIGIN}/manifests/9999-test/manifest.json/canvas/0`;

// Each scenario runs against one fragment spec on the 2000x3000 test canvas.
// - BIG: a large block, the original scenario.
// - TINY: a single-directory-line sliver at real-entry scale (regression for
//   the Dew Drop Inn report: xywh=1535,3000,94,31 — the highlight rendered
//   but the page never zoomed). Post-zoom a sliver only ever spans ~13% of
//   the viewer width (Clover pads its fitBounds target by fixed world units
//   that dwarf the rect), so tiny specs assert a width fraction + centering
//   instead of the BIG spec's area ratio.
function makeSpec(fragment, tiny) {
  const m = /^xywh=(\d+),(\d+),(\d+),(\d+)$/.exec(fragment);
  return {
    fragment,
    tiny: !!tiny,
    aspect: Number(m[3]) / Number(m[4]),
    stateId: `${CANVAS_ID}#${fragment}/content-state`,
    cfUrl: `${ORIGIN}/iiif/2/9990001/full/max/0/default.jpg#${fragment}`,
  };
}
const BIG = makeSpec('xywh=400,600,600,400');
const TINY = makeSpec('xywh=1535,2400,94,31', true);

const ASPECT_TOLERANCE = 0.2;

function httpGet(path) {
  return new Promise((resolve, reject) => {
    http.get(ORIGIN + path, res => {
      let body = '';
      res.on('data', c => body += c);
      res.on('end', () => resolve({ status: res.statusCode, body }));
    }).on('error', reject);
  });
}

function setDelay(ms) {
  return httpGet(`/_control/delay?ms=${ms}`);
}

async function readOverlay(page, spec) {
  return page.evaluate((id) => {
    const el = document.getElementById(id);
    if (!el) return null;
    const r = el.getBoundingClientRect();
    // Style-based size mirrors the driver: OSD's inline style is the exact
    // world-derived rect; the bounding rect adds the highlight's border
    // (+4px per axis), which skews the aspect of tiny fragments.
    return {
      width: r.width, height: r.height, x: r.x, y: r.y,
      styleWidth: parseFloat(el.style.width), styleHeight: parseFloat(el.style.height),
    };
  }, spec.stateId);
}

function isSane(info, spec) {
  if (!info || !Number.isFinite(info.width) || !Number.isFinite(info.height) ||
      info.width <= 0 || info.height <= 0) {
    return false;
  }
  const actual = (Number.isFinite(info.styleWidth) && Number.isFinite(info.styleHeight) &&
                  info.styleWidth > 0 && info.styleHeight > 0)
    ? info.styleWidth / info.styleHeight
    : info.width / info.height;
  return Math.abs(actual - spec.aspect) / spec.aspect <= ASPECT_TOLERANCE;
}

// Wait for the overlay to have a sane rect, then keep sampling for a settle
// window: the sane rect first appears mid zoom-animation (OSD's fitBounds
// animates the viewport), and we want the rect after the animation settles.
async function pollOverlay(page, spec, timeoutMs, settleMs = 4000) {
  const start = Date.now();
  let firstSane = null;
  while (Date.now() - start < timeoutMs) {
    const info = await readOverlay(page, spec);
    if (isSane(info, spec)) { firstSane = info; break; }
    await page.waitForTimeout(300);
  }
  if (!firstSane) return null;
  let last = firstSane;
  const settleStart = Date.now();
  while (Date.now() - settleStart < settleMs) {
    await page.waitForTimeout(250);
    const info = await readOverlay(page, spec);
    if (isSane(info, spec)) last = info;
  }
  return last;
}

// Watch the panel-flash suppression (gb-zoom-pending): while the driver is
// pending AND Clover's aside is mounted, the aside's computed opacity must
// be 0. Samples every 50ms until the pending window ends (or timeout).
// Returns counts so callers can assert (a) the window was observed at all
// and (b) the aside was never visible inside it.
// Recorder for the gb-zoom-pending window, installed via addInitScript so it is
// running before any page script — see installFlashRecorder's note on why this
// cannot be driven from Node.
const FLASH_RECORDER = () => {
  const state = { pendingAsideSamples: 0, visiblePendingAsideSamples: 0, sawPending: false, ended: false };
  window.__gbFlash = state;
  const tick = () => {
    const cv = document.querySelector('clover-viewer');
    if (cv) {
      const pending = cv.classList.contains('gb-zoom-pending');
      if (pending) {
        state.sawPending = true;
        const aside = cv.querySelector('aside[data-aside-active]');
        if (aside) {
          state.pendingAsideSamples++;
          if (getComputedStyle(aside).opacity !== '0') state.visiblePendingAsideSamples++;
        }
      } else if (state.sawPending) {
        state.ended = true;
        return;  // window over, stop sampling
      }
    }
    setTimeout(tick, 16);
  };
  tick();
};

// The pending window is short — on desktop Clover's info panel is already open,
// so the overlay registers on the driver's first 250ms poll and the class comes
// straight back off. Sampling it from Node at 50ms per round trip, starting only
// once page.goto() resolved, was a race: the same viewer.html scored 2 samples in
// one CI run and 0 in the next, and 0 every time on a fast machine. The window
// itself was never the problem — the observation was. Recording in-page from
// document start at ~16ms makes it deterministic.
async function watchFlashHidden(page, timeoutMs) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const s = await page.evaluate(() => window.__gbFlash || null);
    if (s && s.ended) return s;
    await page.waitForTimeout(50);
  }
  return (await page.evaluate(() => window.__gbFlash || null)) ||
         { pendingAsideSamples: 0, visiblePendingAsideSamples: 0 };
}

async function getViewerRect(page) {
  return page.evaluate(() => {
    const wrap = document.getElementById('viewer-wrap');
    const r = wrap.getBoundingClientRect();
    return { width: r.width, height: r.height, x: r.x, y: r.y };
  });
}

async function getPanelOpen(page) {
  return page.evaluate(() => {
    const el = document.querySelector('clover-viewer');
    if (!el) return null;
    const inner = el.querySelector('[data-information-panel-open]');
    return inner ? inner.getAttribute('data-information-panel-open') : null;
  });
}

async function getManifestBackExists(page) {
  return page.evaluate(() => {
    const el = document.querySelector('clover-viewer');
    if (!el) return false;
    return !!el.querySelector('[data-value="manifest-back"]');
  });
}

async function getPendingCleared(page) {
  return page.evaluate(() => {
    const el = document.querySelector('clover-viewer');
    return el ? !el.classList.contains('gb-zoom-pending') : null;
  });
}

async function checkGhostLabel(page, spec) {
  return page.evaluate((id) => {
    const el = document.getElementById(id);
    if (!el) return null;
    return (el.textContent || '').trim();
  }, spec.stateId);
}

async function checkNoDownloadOrBadge(page) {
  return page.evaluate(() => {
    const el = document.querySelector('clover-viewer');
    if (!el) return { downloadEls: -1, badgeEls: -1 };
    const dl = el.querySelectorAll('[aria-label*="ownload" i], [data-testid*="download" i]');
    const badge = el.querySelectorAll('[aria-label*="IIIF" i], [data-testid*="iiif-badge" i], [class*="iiif-logo" i]');
    return { downloadEls: dl.length, badgeEls: badge.length };
  });
}

function fmtRect(r) {
  if (!r) return 'null';
  return `x=${r.x.toFixed(1)} y=${r.y.toFixed(1)} w=${r.width.toFixed(1)} h=${r.height.toFixed(1)}`;
}

function assertOverlaySane(overlay, viewer, spec, label, results) {
  if (!overlay) {
    results.push([false, `${label}: overlay never appeared / never got a sane rect`]);
    return;
  }
  const areaRatio = (overlay.width * overlay.height) / (viewer.width * viewer.height);
  const widthFrac = overlay.width / viewer.width;
  const dxFrac = Math.abs((overlay.x + overlay.width / 2) - (viewer.x + viewer.width / 2)) / viewer.width;
  const dyFrac = Math.abs((overlay.y + overlay.height / 2) - (viewer.y + viewer.height / 2)) / viewer.height;
  // BIG fragments fill a meaningful share of the viewer area post-zoom. TINY
  // fragments can't (see makeSpec comment) — for them, post-zoom width lands
  // at ~8-15% of the viewer vs ~2% at OSD's home view, so a 5% width
  // fraction separates zoomed from not-zoomed with margin on both sides.
  const substantial = spec.tiny ? widthFrac > 0.05 : areaRatio > 0.05;
  const centered = dxFrac < 0.25 && dyFrac < 0.25;
  results.push([substantial && centered,
    `${label}: overlay=${fmtRect(overlay)} viewer=${fmtRect(viewer)} areaRatio=${areaRatio.toFixed(3)} widthFrac=${widthFrac.toFixed(3)} dxFrac=${dxFrac.toFixed(3)} dyFrac=${dyFrac.toFixed(3)}`]);
}

async function newPage(browser, viewport) {
  const context = await browser.newContext({ viewport });
  const page = await context.newPage();
  await page.addInitScript(FLASH_RECORDER);
  const consoleErrors = [];
  const pageErrors = [];
  const requestFailures = [];
  page.on('console', msg => { if (msg.type() === 'error') consoleErrors.push(msg.text()); });
  page.on('pageerror', err => pageErrors.push(err.message));
  page.on('requestfailed', req => requestFailures.push(req.url() + ' :: ' + (req.failure() && req.failure().errorText)));
  return { context, page, consoleErrors, pageErrors, requestFailures };
}

// External resources viewer.html references that are unreachable (or
// pointless) from the test sandbox / CI: analytics, web fonts, favicon.
// net::ERR_ABORTED is a cancellation, not a failure: the driver closes the
// info panel as soon as the overlay registers, which unmounts the panel's
// region-thumbnail <img> and aborts its (delay-simulated) in-flight request.
function isBenignNoise(text) {
  return /gc\.zgo\.at|goatcounter|fonts\.googleapis|fonts\.gstatic|favicon\.ico|net::ERR_ABORTED/i.test(text);
}

// The viewer used to live at the site root, so links shared before it moved to
// viewer.html arrive at index.html carrying their ?cf= entry parameter. A shim
// in index.html's <head> forwards those. This case guards it: without the shim
// every entry link already in the wild lands on the home page instead of the
// entry, and the failure is invisible from the explorers (which link straight
// to viewer.html) — nothing else in this suite would catch it.
async function runCaseRootRedirect(browser, { label }) {
  console.log(`\n=== ${label} ===`);
  await setDelay(0);
  const { page } = await newPage(browser, { width: 1280, height: 800 });
  const results = [];
  const query = `?cf=${encodeURIComponent(BIG.cfUrl)}&name=TestEntry&from=all-volumes`;

  await page.goto(`${ORIGIN}/index.html${query}`);
  await page.waitForFunction(
    () => location.pathname.endsWith('/viewer.html'), null, { timeout: 15000 }
  ).catch(() => {});
  const landed = new URL(page.url());
  results.push([landed.pathname.endsWith('/viewer.html'),
    `?cf= link to the root forwards to the viewer (landed on ${landed.pathname})`]);
  results.push([landed.searchParams.get('cf') === BIG.cfUrl,
    'cf parameter survives the forward intact']);
  results.push([landed.searchParams.get('name') === 'TestEntry' &&
                landed.searchParams.get('from') === 'all-volumes',
    'the other query parameters survive too']);

  // A bare root visit must render the home page and stay there — the shim
  // keys on ?cf=, so an over-eager match would redirect real visitors away.
  await page.goto(`${ORIGIN}/index.html`);
  await page.waitForLoadState('load');
  const stayed = new URL(page.url());
  results.push([stayed.pathname.endsWith('/index.html'),
    `a bare root visit stays on the home page (is ${stayed.pathname})`]);
  const heroText = await page.evaluate(() => {
    const h = document.querySelector('h1');
    return h ? h.textContent.replace(/\s+/g, ' ').trim() : '';
  });
  results.push([/welcomed Black travelers/i.test(heroText),
    `home page renders its heading (got: "${heroText.slice(0, 60)}")`]);
  const navCount = await page.evaluate(() =>
    document.querySelectorAll('.gb-sitenav a').length);
  results.push([navCount >= 5,
    `home page carries the site nav (${navCount} links)`]);

  await page.context().close();
  return { results };
}

async function runCaseDesktop(browser, { delayMs, label, timeoutMs, spec = BIG }) {
  console.log(`\n=== ${label} ===`);
  await setDelay(delayMs);
  const { page, consoleErrors, pageErrors, requestFailures } = await newPage(browser, { width: 1280, height: 800 });
  const url = `${ORIGIN}/viewer.html?cf=${encodeURIComponent(spec.cfUrl)}&name=TestEntry`;
  const t0 = Date.now();
  await page.goto(url);
  const flashWatch = delayMs > 0 ? watchFlashHidden(page, timeoutMs) : null;
  const overlay = await pollOverlay(page, spec, timeoutMs);
  const elapsed = Date.now() - t0;
  const flash = flashWatch ? await flashWatch : null;
  const viewer = await getViewerRect(page);
  const panelOpen = await getPanelOpen(page);
  const manifestBackExists = await getManifestBackExists(page);
  const pendingCleared = await getPendingCleared(page);
  const ghostText = await checkGhostLabel(page, spec);
  const dlBadge = await checkNoDownloadOrBadge(page);
  const subtitlePresent = await page.evaluate(() =>
    !!document.querySelector('.gb-entry-subtitle') &&
    document.querySelector('.gb-entry-subtitle').textContent === 'Entry: TestEntry');
  const spamPresent = consoleErrors.concat(pageErrors).some(t => /viewportToImageRectangle/i.test(t));

  const results = [];
  if (delayMs > 0) {
    results.push([elapsed >= 6000, `total load time exceeded 6s (was ${elapsed}ms) — cold-load regression scenario`]);
  }
  results.push([elapsed < timeoutMs, `zoom detected+settled within ${elapsed}ms (cap ${timeoutMs}ms)`]);
  assertOverlaySane(overlay, viewer, spec, 'overlay geometry', results);
  results.push([panelOpen === 'false', `info panel closed (data-information-panel-open=${panelOpen})`]);
  results.push([!manifestBackExists, `manifest-back button removed from DOM (exists=${manifestBackExists})`]);
  results.push([pendingCleared === true, `gb-zoom-pending cleared after driver finished (cleared=${pendingCleared})`]);
  if (flash) {
    results.push([flash.pendingAsideSamples > 0, `observed the pending window with the aside mounted (${flash.pendingAsideSamples} samples)`]);
    results.push([flash.visiblePendingAsideSamples === 0, `aside computed opacity stayed 0 for the whole pending window (${flash.visiblePendingAsideSamples} visible samples)`]);
  }
  results.push([ghostText === '', `no ghost label text in overlay (got: "${ghostText}")`]);
  results.push([dlBadge.downloadEls === 0, `no download button (found ${dlBadge.downloadEls})`]);
  results.push([dlBadge.badgeEls === 0, `no IIIF badge (found ${dlBadge.badgeEls})`]);
  results.push([subtitlePresent, `header subtitle "Entry: TestEntry" present`]);
  const realErrors = pageErrors.concat(requestFailures.filter(f => !isBenignNoise(f)));
  results.push([realErrors.length === 0, `no page errors / non-benign request failures (${realErrors.length}): ${realErrors.join(' | ')}`]);

  console.log('viewportToImageRectangle console spam present:', spamPresent);
  await setDelay(0);
  await page.context().close();
  return { results, spamPresent };
}

// Clover 3.11.0 initializes the info panel closed below its ~768px window-
// width breakpoint, which would mean the content-state item never mounts and
// no zoom happens on phones. viewer.html's driver counters that by clicking
// Clover's aside toggle (button[data-aside-active]) while waiting for the
// overlay, closing the panel as soon as the overlay registers (an open panel
// covers the viewer at phone widths and stalls OSD), then zooming. These
// cases assert the full desired behavior at 400x800.
async function runCaseMobile(browser, { delayMs, label, timeoutMs, spec = BIG }) {
  console.log(`\n=== ${label} ===`);
  await setDelay(delayMs);
  const { page, consoleErrors, pageErrors, requestFailures } = await newPage(browser, { width: 400, height: 800 });
  const url = `${ORIGIN}/viewer.html?cf=${encodeURIComponent(spec.cfUrl)}&name=TestEntry`;
  const t0 = Date.now();
  await page.goto(url);
  const flashWatch = delayMs > 0 ? watchFlashHidden(page, timeoutMs) : null;
  const overlay = await pollOverlay(page, spec, timeoutMs);
  const elapsed = Date.now() - t0;
  const flash = flashWatch ? await flashWatch : null;
  const viewer = await getViewerRect(page);
  await page.waitForTimeout(500);
  const panelOpen = await getPanelOpen(page);
  const manifestBackExists = await getManifestBackExists(page);
  const pendingCleared = await getPendingCleared(page);
  const realErrors = pageErrors.concat(requestFailures.filter(f => !isBenignNoise(f)));

  const results = [];
  if (delayMs > 0) {
    results.push([elapsed >= 6000, `total load time exceeded 6s (was ${elapsed}ms) — mobile + cold-load scenario`]);
  }
  results.push([elapsed < timeoutMs, `zoom detected+settled within ${elapsed}ms (cap ${timeoutMs}ms)`]);
  assertOverlaySane(overlay, viewer, spec, 'overlay geometry (400px viewport)', results);
  results.push([panelOpen === 'false', `info panel closed after zoom (data-information-panel-open=${panelOpen})`]);
  results.push([!manifestBackExists, `manifest-back button removed from DOM (exists=${manifestBackExists})`]);
  results.push([pendingCleared === true, `gb-zoom-pending cleared after driver finished (cleared=${pendingCleared})`]);
  if (flash) {
    results.push([flash.pendingAsideSamples > 0, `observed the pending window with the aside mounted (${flash.pendingAsideSamples} samples)`]);
    results.push([flash.visiblePendingAsideSamples === 0, `aside computed opacity stayed 0 for the whole pending window (${flash.visiblePendingAsideSamples} visible samples)`]);
  }
  results.push([realErrors.length === 0, `no page errors / non-benign request failures (${realErrors.length}): ${realErrors.join(' | ')}`]);

  await setDelay(0);
  await page.context().close();
  return { results };
}

(async () => {
  const executablePath = process.env.PW_CHROMIUM_PATH || process.env.CHROMIUM_BIN;
  const browser = await chromium.launch({
    ...(executablePath ? { executablePath } : {}),
    headless: true,
  });
  let allPass = true;
  let spamSeen = false;
  try {
    const r1 = await runCaseDesktop(browser, { delayMs: 0, label: 'Test 1: desktop 1280x800, fast load', timeoutMs: 25000 });
    const r2 = await runCaseDesktop(browser, { delayMs: 7000, label: 'Test 2: desktop 1280x800, slow load (regression case)', timeoutMs: 45000 });
    const r3 = await runCaseMobile(browser, { delayMs: 0, label: 'Test 3: mobile 400x800, fast load', timeoutMs: 25000 });
    const r4 = await runCaseMobile(browser, { delayMs: 7000, label: 'Test 4: mobile 400x800, slow load', timeoutMs: 45000 });
    const r5 = await runCaseDesktop(browser, { delayMs: 0, label: 'Test 5: desktop, fast load, tiny fragment', timeoutMs: 25000, spec: TINY });
    const r6 = await runCaseDesktop(browser, { delayMs: 7000, label: 'Test 6: desktop, slow load, tiny fragment', timeoutMs: 45000, spec: TINY });
    const r7 = await runCaseMobile(browser, { delayMs: 0, label: 'Test 7: mobile, fast load, tiny fragment', timeoutMs: 25000, spec: TINY });
    const r8 = await runCaseRootRedirect(browser, { label: 'Test 8: site root forwards legacy ?cf= links to the viewer' });
    spamSeen = r1.spamPresent || r2.spamPresent;
    for (const [name, r] of [['Test1-desktop-fast', r1], ['Test2-desktop-slow', r2], ['Test3-mobile-fast', r3], ['Test4-mobile-slow', r4],
                             ['Test5-desktop-fast-tiny', r5], ['Test6-desktop-slow-tiny', r6], ['Test7-mobile-fast-tiny', r7], ['Test8-root-redirect', r8]]) {
      console.log(`\n--- ${name} results ---`);
      for (const [ok, msg] of r.results) {
        console.log((ok ? 'PASS' : 'FAIL'), '-', msg);
        if (!ok) allPass = false;
      }
    }
  } finally {
    await browser.close();
  }
  console.log('\n=== SUMMARY ===');
  console.log(allPass ? 'ALL TESTS PASSED' : 'SOME TESTS FAILED');
  console.log('viewportToImageRectangle console spam observed:', spamSeen);
  process.exit(allPass ? 0 : 1);
})();
