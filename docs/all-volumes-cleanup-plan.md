# `all-volumes.html` — code review & staged cleanup plan

*Reviewed at commit `85be403` (2026-07-27). All line numbers below refer to that
commit and WILL drift as stages land — always locate code by the quoted
identifier or code snippet, never by line number alone.*

This document is written to be executed by smaller/cheaper models, one stage at
a time. Every finding states its evidence and its exact change. If an
instruction conflicts with what you find in the file, **stop and re-verify with
grep before editing** — do not improvise.

---

## 1. Overall assessment

`all-volumes.html` is 6,537 lines (≈846 CSS, ≈360 HTML, ≈5,300 inline JS) and is
in better shape than its size suggests. Its comments are unusually good — they
record *measured* performance rationale, accessibility reasoning, and rejected
alternatives — and the hot paths (streaming CSV parse, filter memoization, page
index) were clearly profiled. **Those comments are load-bearing documentation.
Do not delete or "tidy" them** except for the specific stale ones listed in
§4.10.

The real problems, in priority order:

1. **~170 lines of dead code** inherited from the era when this file was
   generated from a template (`analysis/build_greenbook_explorer.py`) and then
   appended to. This includes a latent crash: `renderMetaStrip()` is called in
   two places and defined nowhere.
2. **A monkey-patching architecture** (`showDetail` / `renderFacetSidebar`
   wrappers + a second full boot render) that existed so appended code could
   extend generated code. The file is hand-maintained now, so the indirection
   only obscures control flow — and one of the two patches is a verified no-op.
3. **Large internal duplication**: two ~90%-identical stacked-column chart
   renderers, four near-identical trend-table builders, parallel
   sentinel/window/keyboard-nav code for the listings and establishments
   tables, three copies of a Tab focus trap, two copies of modal chrome.
4. **Cross-file duplication**: ~15 utility functions duplicated verbatim across
   `all-volumes.html`, `explorer.html`, `nyc.html`, `travel_guides_explorer.html`
   (e.g. `sha1hex`, the streaming CSV parser, `gbCachedFetch`). The repo already
   has the right pattern for this — `gb-matching.js`, `gb-categories.js`,
   `gb-geo.js` — it just hasn't been applied to these.

Estimated net effect of Stages 1–4: **≈450–550 lines removed (~9% of the JS),
zero behavior change.** Stage 5 (optional) removes several hundred more from
the repo overall.

---

## 2. Ground rules for implementers

- **Branch:** work on `claude/all-volumes-code-review-ez92sw` (or a branch the
  user designates). One stage per commit, using the commit message given in
  each stage. Push after each stage; every branch push gets a GitHub Pages
  preview at `…/previews/<branch-slug>/all-volumes.html` (see
  `.github/workflows/pages-deploy.yml`) for manual checks.
- **Behavior-identical refactor.** No visual, interaction, URL, or a11y
  changes. If a change would alter behavior, it is out of scope unless listed
  in §6 (small bug fixes).
- **Surgical diffs.** Never reflow, reformat, or re-indent lines you are not
  otherwise changing. No formatters.
- **Preserve comments.** Keep every rationale comment. When a refactor makes a
  comment false, update it minimally. Only the comments listed in §4.10 may be
  rewritten/removed outright.
- **Names that must not change:** `gbBrandHome` is called from an inline
  `onclick` in the HTML (`<p class="sidebar-brand">…`). Grep for `onclick=`
  before renaming anything.
- **Verification is mandatory** after every stage: run the smoke test (§3),
  run the stage's listed greps, and eyeball `git diff --stat`.
- Data facts you may rely on (verified against the committed CSVs):
  - Both CSVs' headers contain `volume_year`; **neither contains `year`**, and
    `year` is not in `GB_KEEP_COLUMNS`, so `row.year` is always `undefined`.
  - Only `name` exists as a name column (no `establishment_name`, `firm_name`,
    `business_name` in either CSV or in `hero-thumbs/manifest.json` records).
  - Neither CSV contains `neighborhood`, `borough`, `latitude`, `longitude`,
    `geocode_quality`, or `review_flag` columns.

---

## 3. Stage 0 — add a smoke test (safety net for everything after)

There are currently **no tests** for the explorers (`tests/` covers only the
`index.html` viewer). Create `tests/smoke_all_volumes.js` with exactly the
content below. It is run manually (`node tests/smoke_all_volumes.js` from the
`tests/` dir after a one-time `npm ci`); do **not** wire it into CI in this
task (the viewer workflow's path filters are deliberate).

In the Claude dev sandbox, Chromium is preinstalled — run with
`PW_CHROMIUM_PATH=/opt/pw-browsers/chromium`.

```js
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
```

**Verify:** run it once against the untouched file; it must print `SMOKE OK`.
If it fails on the pristine file, fix the *test*, not the page.

**Commit:** `Add manual Playwright smoke test for the all-volumes explorer`

---

## 4. Stage 1 — delete dead code (pure deletions, ~170 lines)

Every item below is verified-dead. Delete in one commit. After each item, the
listed grep must return zero matches.

### 4.1 The `VOLUMES` multi-volume machinery (never populated)
`const VOLUMES = {}` (L1243) is **only ever read** — no assignment anywhere
(`grep -n 'VOLUMES\[' `→ reads only). Everything gated on it is unreachable,
including two calls to **`renderMetaStrip()`, a function that does not exist
in this file** — a crash if the code ever ran.

Delete:
- `function loadVolume(label) {…}` (≈L1543–1567) and its section comment.
- The volume-selector IIFE `(function () { const volLabels = Object.keys(VOLUMES); …})()`
  (≈L1570–1606).
- `const VOLUMES = {};` (L1243).
- `let currentDocMeta = {};` (L1494) **and** the `currentDocMeta` branch inside
  `viewerUrl()` (≈L2203–2205: `if (currentDocMeta && currentDocMeta.resource_url) {…}`)
  — `currentDocMeta` is always `{}` there, so the branch never fires.
- The `vol` blocks in `stateToHash()` (≈L3419–3426, `const volLabels = …; if (volLabels.length > 1)…`)
  and `applyHashState()` (≈L3453–3464, `if (params.has("vol"))…`).
- Markup: `#volume-wrap` + `#volume-select` (≈L935–938), `#mobile-volume-select`
  (≈L961), the hidden write-only `#doc-title` / `#doc-sub` spans (≈L933–934) and
  their boot writes (≈L1530–1532, the two `document.getElementById("doc-title"|"doc-sub")…`
  statements).
- CSS: the `#volume-wrap` and `#volume-select` rules (≈L369–370).
- **Keep** `const DOC_TITLE = "Green Book and Travel Guides";` — still used for
  the CSV export filename.

Grep gates: `renderMetaStrip` → 0, `VOLUMES` → 0, `currentDocMeta` → 0,
`loadVolume` → 0, `volume-select` → 0, `doc-title` → 0.

### 4.2 `contentStateUrl()` and the viewer constants (constant no-op)
`const VIEWER_URL = ""` (L1352) makes `contentStateUrl()` return `""`
unconditionally, so the "View in source document ↗" link has never rendered on
this page. Delete:
- `contentStateUrl()` (≈L2229–2249) incl. its section comment.
- In `showDetail`: `const csUrl = contentStateUrl(row.canvas_fragment);` and
  `if (csUrl) links.push(…)` (≈L2476–2477).
- `const VIEWER_URL`, `const MANIFEST_URL`, `let activeManifestUrl` (L1352–1355).
- `const FULL_PAGE_THUMBS = false;` (L1354): in `liveIiifUrl()` change
  `if (!FULL_PAGE_THUMBS && cf.includes("#xywh="))` → `if (cf.includes("#xywh="))`.

Grep gates: `contentStateUrl|VIEWER_URL|MANIFEST_URL|activeManifestUrl|FULL_PAGE_THUMBS` → 0.

### 4.3 `HERO_THUMB_BY_CF` (written, never read)
Declared L6431, assigned L6441, nulled L6443 — zero reads. Its comment
("canvas_fragment -> local file, so thumbUrl() … serves pool entries from the
repo") describes behavior that does not exist (`thumbUrl()` never consults it;
hero thumbs come from the HF CDN via `thumbKey()`). Remove the identifier from
all three lines and delete the two comment lines above the assignment.

Grep gate: `HERO_THUMB_BY_CF` → 0.

### 4.4 `row.year` fallbacks and the `GB_YEAR_FIELD` auto-detect (provably dead)
Neither CSV has a `year` column and `year` is not in `GB_KEEP_COLUMNS`, so
`row.year` is always `undefined`; `FIELD_META` fixes the field name, so the
auto-detect IIFE always yields `"volume_year"`.

- Replace the IIFE (≈L4014–4017) with:
  `const GB_YEAR_FIELD = "volume_year";  // both CSVs use this column` (same
  position; keep the `GB_YEAR_FIELD` name — 24 call sites use it).
- Delete every `|| row.year`, `|| r.year`, `|| a.year`, `|| b.year` fallback
  (20 sites; find with `grep -n '|| *\(row\|r\|a\|b\)\.year' all-volumes.html`).
  Keep the surrounding `Number(…)`/`String(…)` coercions and `|| 0` / `|| ""`
  defaults exactly as they are. Example:
  `Number(r[GB_YEAR_FIELD] || r.year) || 0` → `Number(r[GB_YEAR_FIELD]) || 0`.

Grep gate: `\.year\b` matches only `volume_year`-related identifiers
(`r.volume_year` etc.) and CSS/comment text — zero `|| x.year` fallbacks.

### 4.5 Legacy multi-schema name ladders (only `name` exists)
`["name","establishment_name","firm_name","business_name"]` ladders are
template generality; only `name` exists in both CSVs and in
`hero-thumbs/manifest.json` records. Simplify five sites:
- `buildRowTr` (≈L1791): `const _rowName = row.name || "Entry";`
- `gbEnsureRowVisible` (≈L4285–4287): `const nfVal = targetRow.name;` (drop the
  `nf` find; keep the `if (nfVal)` ladder logic below unchanged).
- `gbRenderCoverage` (≈L4476–4478): `const nfVal = row.name;`
- `gbUpdateHero` featured picker (≈L6369): replace the `nf` find + `if (!nf) continue;`
  with `if (!r.name) continue;` and use `r.name` in the dedupe key.
- `gbUpdateHero` card builder (≈L6377): drop the `nf` lookup; use `r.name` in
  the card HTML.
- Same class of cleanup in `showDetail` (≈L2366–2370): `displayFields.find(f =>
  f.name.includes("name") || …)` always resolves to the `name` field. Replace
  with direct use: title text `row.name || "(entry)"`, and
  `const entryName = row.name || "entry";` — **preserve the two different
  fallback strings** (`"(entry)"` for the visible title, `"entry"` for labels).

Grep gate: `establishment_name|firm_name|business_name` → 0.

### 4.6 `ALL_INITIAL_ENTRIES` indirection
With `loadVolume()` gone (§4.1), `ALL_ENTRIES` is never reassigned. Replace
`const ALL_INITIAL_ENTRIES = [];` (L1242) with `const ALL_ENTRIES = [];` and
delete `let ALL_ENTRIES = ALL_INITIAL_ENTRIES;` (L1356).

Grep gate: `ALL_INITIAL_ENTRIES` → 0.

### 4.7 Inert geocode columns in `GB_KEEP_COLUMNS`
The set (≈L5077–5084) keeps `neighborhood, borough, latitude, longitude,
geocode_quality, review_flag` "for nyc.html's CSV" — but this page streams
`green_book_entries_all.csv` + `travel_guides_all.csv`, whose headers contain
none of them (verified). Delete those six names and the
`// nyc.html's CSV carries its geocode columns…` comment line. (`nyc.html` has
its own copy of the parser; this file's set is not shared.)

### 4.8 Orphan CSS / placeholder markup
- `.gb-tagline { display: none; }` (L368) — no element uses the class.
- `#search-scope-label { display: none; }` (L445) — no such element.
- `.gb-hero-eyebrow-dot` rule (L101) — its only markup is commented out
  (≈L892); delete the rule and, optionally, the three commented-out eyebrow
  lines (≈L891–893).
- The permanently hidden rule divs: delete `.gb-hero-caveat-rule` rule (L199) +
  element (≈L903), and `.trends-caveat-rule` rule (L230) + element (≈L1060).

### 4.9 The perpetual `_checkHero` poller
The 200 ms interval (≈L6519–6524) never stops if the user never returns to the
hero. It is triple-redundant: IntersectionObserver **always fires its callback
with the initial intersection state on `observe()`**, the hero-thumbs fetch
settlement re-calls `gbMaybeBuildHero()`, and the post-stream block calls it
again. Delete the interval block. (The smoke test's hero-card assertion covers
this.)

### 4.10 Stale comments (the only comments you may rewrite)
- The banner (≈L4008–4011) `Green Book extensions — … (appended by
  analysis/build_greenbook_explorer.py; do not edit the base template)` is
  false — the file is hand-maintained. Replace with:
  `// ── Green Book dataset extensions ─… (originally appended to a generated
  template; the whole file is hand-maintained now)`.
- The skip-link comment (≈L6507–6509) cites `hrefForState()`, which doesn't
  exist in this file. Reword to reference `stateToHash()` (which handles the
  same `<base href>` trap). (`nyc.html` has the same stale comment — out of
  scope here; noted in §9.)
- The `HERO_THUMB_BY_CF` comment — already deleted in §4.3.

**Verify:** smoke test passes; all grep gates above return 0; manual spot-check
of the preview deploy (page loads, no console exceptions).

**Commit:** `all-volumes: remove dead template-era code`

---

## 5. Stage 2 — fold the monkey-patches into their base functions

Background: the file was once generated, then extended by reassigning
`showDetail` / `renderFacetSidebar` to wrappers and re-running `renderAll()`.
Hand-maintained, this is pure indirection — and it makes boot render twice.

### 5.1 Delete the `renderFacetSidebar` wrapper (verified no-op)
The wrapper (≈L4421–4430, `const _gbOrigRFS = renderFacetSidebar; …`) moves the
`volume_year` facet to the front of `facetFields` — but `volume_year` is
**already first** in `FIELD_META`, and `Array.filter` preserves order. Delete
the whole block. **Verify:** sidebar facet order is unchanged
(Year, Publication, Category).

### 5.2 Fold the `showDetail` wrapper into `showDetail`
- Change the base declaration (≈L2361) to `function showDetail(row, opts) {`.
- Move the wrapper's body (≈L4437–4465: the `gcEvent('detail-open')` line, the
  estab-listings/`_gbLastDetailEstab`/`renderEstabRecord`/`gbRenderEstabNote`
  block, the `?cf=` history-sync block, and the `gbRenderCoverage(row);` call)
  to the **very end** of the base function, after `renderDetailMap(row);` —
  this preserves today's execution order exactly (wrapper ran the base to
  completion first).
- Delete `const _gbOrigSD = showDetail;` and the `showDetail = function (row,
  opts) {…}` wrapper shell. Keep the wrapper's explanatory comment lines that
  are still true, attached to the moved code.
- `gbRenderCoverage` (already a standalone function) is untouched.

### 5.3 Boot with a single render
Today boot renders twice: `applyHashState(); renderAll();` (≈L3996–3997) and a
second `renderAll();` (≈L4858–4862, "now that monkey-patches are in place").
With the patches folded in there is nothing to re-render:
- Delete the first `applyHashState(); renderAll();` **and** the
  `if (location.hash && location.hash.length > 1) {…}` hash-scroll block right
  after it (≈L3999–4006).
- Replace the second `renderAll()` block (including its now-false comment) with
  exactly what was deleted: `applyHashState(); renderAll();` followed by the
  hash-scroll block, verbatim. The `?cf=` deep-link IIFE stays where it is,
  immediately after.

### 5.4 Move the hoisting-workaround state up
Move `var gbNameIndex = new Map();` / `var gbRowToKey = new Map();`
(≈L4028–4029) and `var _gbLastDetailEstab = null;` (≈L4849) into the state
section (near `let gbDataLoaded = false;`, ≈L1512), declared with `let`.
Delete the comments that only explained the `var`-hoisting workaround
(≈L4025–4027, L4030) and shrink the `gbDataLoaded` placement excuse
(≈L1508–1511) to a plain one-liner — with a single boot render at the bottom
of the script, declaration order is no longer subtle.

**Verify:** smoke test; additionally load with `#view=est` in the URL before
data finishes (establishments note renders, then fills in), open `#trends` and
`#about` deep links, use browser Back after opening a detail panel (panel
closes), and confirm the sidebar still lists Year first.

**Commit:** `all-volumes: fold monkey-patches into base functions; boot with a single render`

---

## 6. Stage 3 — small bug fixes + micro-helpers

### Fixes (tiny, real)
1. **Sentinel colSpan off-by-one** — `renderSentinel` (≈L1891):
   `sentinelTd.colSpan = displayFields.length + 1;` → `+ 2` (rows have
   `displayFields` cells **plus** Source **plus** Details columns; the mobile
   card cell already uses `+ 2`).
2. **`_filterKey` separator** — (≈L1617): `.join("")` → `.join("")`.
   Adjacent free-text components (searchQuery, JSON, facet dump) could in
   principle alias two different states to one cache key.
3. **`showDetail` thumb-link guard** — the `if (url)` branch sets
   `thumbLink.href = 'index.html?cf=' + encodeURIComponent(row.canvas_fragment) …`
   even when `url` came from the no-`canvas_fragment` `row.image` fallback,
   producing `cf=undefined`. Wrap the three `thumbLink.*` assignments in
   `if (row.canvas_fragment) {…} else { thumbLink.removeAttribute("href");
   thumbLink.removeAttribute("aria-label"); }`.
4. **`gbValueLabel()`** — `VALUE_LABELS[val] || val` at the facet sidebar
   (≈L3163–3164) and filter chips (≈L3404) lacks the own-property guard the
   detail panel already uses (≈L2449, with a comment explaining why: a CSV cell
   reading `constructor` would render function source). Add next to
   `VALUE_LABELS`:
   ```js
   function gbValueLabel(v) {
     return Object.prototype.hasOwnProperty.call(VALUE_LABELS, v) ? VALUE_LABELS[v] : v;
   }
   ```
   and use it at all three sites (keep the detail panel's explanatory comment).

### Helpers (replace verbatim-repeated patterns; hoisted function declarations, so placement is flexible — put each near its subject)
5. **Adopt the existing `gbFieldLabel()`** (defined ≈L3344) at the 8 inline
   copies of `FIELD_LABELS[x] || x.replace(/_/g, " ")`: ≈L1983, L1985, L2005,
   L2046, L2086, L2135, L3125, L3131. (The `facet-more` aria-label at ≈L3181
   may also adopt it — minor wording improvement, allowed.)
6. **`closeDetailPanel()`** — one function for the repeated close sequence:
   ```js
   function closeDetailPanel() {
     document.getElementById("detail").classList.remove("open");
     document.getElementById("main").classList.remove("detail-open");
     gbCancelDetailMap();      // drop any pending geocode
     gbSyncDetailModality();   // release mobile inert/role state
   }
   ```
   Use it in the `#detail-close` listener (≈L2969–2974; its history/focus logic
   stays after the call), in `renderAll`'s auto-close (≈L3511–3516; the
   `selectedIdx = null;` line stays separate), and in the coverage
   "Search the table…" handler (≈L4834–4835). Move the good comments from the
   old sites onto the helper.
7. **`gbPubDot(pub)`** — returns a `span.pub-dot` colored
   `PUBLICATION_COLORS[pub] || "var(--gb-ink-faint)"`. Replace the six
   pub-keyed creation sites: provenance (≈L1451), mobile card (≈L1733), facet
   sidebar (≈L3158), estab timeline (≈L4215), coverage row label (≈L4669),
   year-chart legend (≈L5685). Leave the churn legend alone (it colors by raw
   hex, not publication).
8. **Allocation-free `escapeHtml`** (≈L1687) — it currently creates a DOM node
   per call and is on the row-render hot path via `highlightMatch`:
   ```js
   const _gbEscMap = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
   function escapeHtml(str) { return String(str).replace(/[&<>"']/g, c => _gbEscMap[c]); }
   ```
9. **`openRandomEntry()`** — extract the `#random-btn` listener body
   (≈L3560–3570, including `gcEvent('random-entry')`) into a named function and
   call it directly from all four entry points: the `#random-btn` listener →
   delete the hidden button entirely (element ≈L990, CSS rules ≈L471–472, and
   remove `, #random-btn` from the mobile rule `#export-btn, #random-btn {…}`
   ≈L848), `#gb-explore-btn` (≈L4949–4952), `#mobile-random-btn` (≈L1534), and
   `#random-btn-hero` (≈L6319–6323, which keeps its extra scroll lines). This
   removes the hidden-button-as-event-bus indirection.
10. *(Optional consistency)* Read `_gbAboutOnLoad` bare instead of
    `window._gbAboutOnLoad` (≈L4899) to match every other read; the `var`
    declarations at L1240–1241 stay.

**Verify:** smoke test; random-entry buttons (hero, sidebar, mobile) all open a
panel; facet sidebar labels/counts unchanged; export filename unchanged.

**Commit:** `all-volumes: fix small latent bugs; extract repeated micro-patterns into helpers`

---

## 7. Stage 4 — deduplicate the big structures (~350 lines)

Four independent workstreams; land as one commit or four, in this order.

### 7.1 One stacked-column chart renderer
`gbDrawYearChart` (≈L5527–5693) and `gbDrawChurnChart` (≈L5900–5988) are ~90%
identical (axis/step selection, bar stacking with the 2px segment gap and
rounded top, full-column hit targets with tooltip + click-to-filter + keyboard,
5-year x ticks, legend). Differences: height (274 vs 216), top margin (34 vs
12, the milestone band), series source/colors, tip/aria text, and the
year-chart-only annotations (milestones + wartime note).

Create:
```js
// One stacked-column chart. cfg:
//   hostId, legendHostId       – container ids
//   height, marginTop          – px (the year chart reserves an annotation band)
//   stacks(yr) -> [[key, n], …]  – ordered segments for one year (empty ok)
//   colorOf(key) -> css color
//   legendItems -> [[label, color], …]
//   tipLines(yr, segs, total) -> [[text, cls], …]
//   ariaLabel(yr, segs, total) -> string
//   onYearClick(yr)            – omit for no interaction on empty years
//   annotate(svg, geo)         – optional; geo = {years, slot, mL, mR, mT, innerH, yPix, totals, W, H}
function gbDrawStackedColumnChart(cfg) { … }
```
Port the shared body verbatim from `gbDrawYearChart`, parameterizing only the
listed differences. Rewrite both originals as thin adapters (~25 lines each);
the year chart's `annotate` callback owns the milestone rules/diamonds/labels
and the wartime in-plot note (move that code unchanged). `GB_MILESTONES`,
`CHURN_COLORS`, and both aggregate functions are untouched.

### 7.2 One trend-table builder
`gbBuildYearTable`, `gbBuildChurnTable`, `gbBuildHeatTable`, `gbBuildMultiTable`
(≈L5696, L5989, L5864, L6145) all hand-roll the same
table/thead/tbody/textContent scaffold. Add:
```js
function gbBuildTrendTable(hostId, headers, rows) { … } // rows: string[][]
```
and reduce each builder to data-prep + one call. Keep each builder's
value-formatting (`"–"` for zero, `%`, `toLocaleString`) exactly as-is in the
data-prep step.

### 7.3 Shared table mechanics (listings ⇄ establishments)
- **`gbAttachRowKeyNav(tr)`** — the `keydown` ArrowUp/ArrowDown roving-tabindex
  handlers in `buildRowTr` (≈L1864–1875) and `buildEstabTr` (≈L3793–3804) are
  byte-identical apart from the Enter/Space action; factor the arrow logic,
  keep the Enter/Space line at each site.
- **`gbRenderSentinelRow(tbody, o)`** with
  `o = {shownFrom, shownTo, total, unit, step, colSpan, onExtend}` — unifies
  `renderSentinel` (≈L1883) and `renderEstabSentinel` (≈L3894) including the
  IntersectionObserver lifecycle (`_sentinelObserver` disconnect/recreate).
  Text rules, derived uniformly (the listings mid-window case falls out
  naturally since establishments always have `shownFrom === 0`):
  - `remaining > 0` → `Showing {shownTo−shownFrom} of {total} {unit} ` + button
    `Show {min(step, remaining)} more`;
  - else if `shownFrom > 0` → `Showing entries {shownFrom+1}–{shownTo} of {total}`;
  - else → `Showing all {total} {unit}`.
  `extendWindow`/`extendEstabWindow` remain separate (different globals) but
  shrink to slice-append + one `gbRenderSentinelRow` call.
- Do **not** merge `buildRowTr`/`buildEstabTr` themselves — different data
  shapes; the mechanical parts above are the real duplication.

### 7.4 One focus trap + one modal chrome
- **`gbTrapTab(container, e)`**: replaces the three inline Tab traps (About
  ≈L4909–4921, detail ≈L4933–4945, Trends ≈L6303–6312). Use the superset
  selector `'a[href], button, summary, [tabindex]:not([tabindex="-1"])'` and
  always filter `!el.disabled && el.offsetParent !== null`. (Deltas are safe:
  About gains the visibility filter — all its focusables are visible when open
  — and gains `summary`, of which it has none.)
- **`gbSetupModal(o)`** with
  `o = {backdropEl, modalEl, closeSelector, openHash, restoreUrl, onOpen}`,
  returning `{open, close(skipFocus), isOpen}`: owns opener capture/restore,
  backdrop + close-button click handling, Escape, the Tab trap, and the
  pathname-anchored hash push on open / `restoreUrl()` on close. Rebuild the
  About IIFE (≈L4883–4923) and the Trends chrome (≈L6259–6315) on it:
  - About: `restoreUrl: () => location.pathname + location.search`.
  - Trends: `onOpen` runs `gcEvent("trends-open")` + `gbRenderTrends()`;
    `restoreUrl: stateToHash`; `gbTrendResetFilters` keeps calling
    `close(true)` (skipFocus).
  Keep the existing pathname-anchoring comments — they document a real preview-
  deploy trap.

**Verify:** smoke test, plus manually in the preview: both charts render and
filter on click (incl. keyboard Enter on a column), milestone tooltips, all
four "View as table" twins, sentinel texts in both views ("Show N more"
auto-extend on scroll), Tab cycling inside About/Trends/mobile-detail, Escape
closes each, focus returns to the opener.

**Commit:** `all-volumes: deduplicate chart renderers, trend tables, sentinels, focus traps, and modal chrome`

---

## 8. Stage 5 (optional) — extract `gb-explorer-core.js`

These functions are duplicated verbatim (or near-verbatim) across the explorer
pages (counts from grep of `function <name>`):

| Function(s) | Duplicated in |
|---|---|
| `sha1hex`, `thumbKey`, `attachThumb`, `liveIiifUrl`, `escapeHtml`, `highlightMatch`, `viewerUrl`, `canvasId` | all 4 explorers |
| `gbCreateStreamingCSVParser`, `gbCachedFetch` (+ `gbPruneOldCaches`) | all-volumes, explorer, nyc |
| `gbAttachTip`/`gbShowTip`/`gbHideTip`/`gbTipEl`, `svgEl`, `gbRoundedTopRect` | all-volumes, nyc |
| `gbSayStatus`, `gbCopyText`, `_gbLegacyCopy` | all-volumes only today, but generic |

Create `gb-explorer-core.js` (same pattern as `gb-matching.js` /
`gb-categories.js` / `gb-geo.js`: classic script, shared global scope, loaded
via `<script src>` before the inline script). Move the functions **verbatim
from `all-volumes.html`** (not from siblings — their copies may have drifted),
plus `HF_THUMB_BASE` and `GB_CACHE_NAME`. Two functions need a signature tweak
to stop reading page-local config:
- `gbStreamCsv(url, onRow)` → `gbStreamCsv(url, onRow, keepColumns)` (the page
  passes `GB_KEEP_COLUMNS`).
- `liveIiifUrl`/`viewerUrl` keep reading the global `CANVAS_MAP` — document at
  the top of the module that the host page must declare `CANVAS_MAP` (top-level
  `let` in any classic script is visible across scripts at call time).

**Adopt in `all-volumes.html` only** in this task: add the script tag (before
`gb-matching.js`), delete the moved definitions. Migrating
`explorer.html`/`nyc.html`/`travel_guides_explorer.html` is follow-up work —
each requires diffing its copies against the module first.

**Verify:** smoke test; `grep -n "function sha1hex" *.html` shows the function
gone from `all-volumes.html` only.

**Commit:** `Extract shared explorer utilities into gb-explorer-core.js (all-volumes adopts)`

---

## 9. Explicitly rejected / out of scope (do not "improve" these)

- **No build step, no framework, no TypeScript, no modules/bundler.** The
  no-build single-file architecture is a deliberate project constraint
  (CLAUDE.md); shared plain `<script>` files are the sanctioned escape hatch.
- **No CSS extraction.** The ~846 CSS lines are page-specific (hero, trends,
  coverage grid); splitting them buys nothing and costs a request.
- **No comment stripping or wholesale reordering of the script** beyond what
  Stages 2 moves. A "sections in logical order" mega-move was considered and
  rejected: enormous diff, high merge risk, near-zero behavior payoff.
- **Known behavior quirks noted, deliberately untouched** (each would be a
  behavior change needing its own decision):
  - `highlightMatch` matches the raw query while `getFiltered` matches a
    punctuation-normalized haystack, so some hits render without a `<mark>`.
  - The Establishments-view `showDetail` is reached via the most recent
    listing; ordinal position is intentionally not shown (documented in code).
  - `nyc.html` carries the same stale `hrefForState()` comment (§4.10) and its
    own copies of everything in §8 — fix when that file is migrated.

---

## 10. Final acceptance checklist (after the last stage you run)

1. `node tests/smoke_all_volumes.js` → `SMOKE OK`.
2. All Stage-1 grep gates still return 0.
3. Manual pass on the branch preview deploy, desktop + a phone-width viewport:
   load → search → facet → detail panel (map, coverage grid, timeline, page
   neighbours, copy link, citation) → establishments view → trends modal
   (click a bar, land filtered) → export CSV → `?cf=` deep link → Back button.
4. Keyboard-only pass: `/` focuses search, arrow keys move rows, Enter opens,
   Escape closes, Tab is trapped in modals and the mobile detail overlay,
   `←`/`→` step entries inside the panel.
5. `git diff main --stat` — expect roughly −450…−550 lines net for Stages 1–4,
   with `all-volumes.html` the only modified page file (plus the new test and,
   if Stage 5 ran, `gb-explorer-core.js`).
