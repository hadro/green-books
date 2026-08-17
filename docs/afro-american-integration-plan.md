# Integrate the four Afro-American's Travel Guide volumes (1954 / 1956 / 1957 / 1958)

*Status: implemented 2026-08-16. Actual numbers: 4,664 rows appended (50 dropped by the unanchored/hallucinated/no-xywh filter), `travel_guides_all.csv` 46,775 rows, merged corpus 113,827 across 50 volumes and 8 publications; +178 keys each in `travel_guides_image_to_volume.json` / `travel_guides_canvas_map.json`; 4 manifests written with real dims patched from aligned sidecars (2 entry-less 1957 canvases keep placeholder dims, warned). Pre-flight `rescale_canvas_fragments.py --dry-run` showed 0 pages needing rescale. Colors: `#713471` deep plum (all-volumes + nyc; passes pairwise vs all 7 at CVD ΔE ≥ 8 / normal ≥ 15), `#a83a68` deep rose (travel_guides_explorer — its palette differs by design; #713471 collides with its Travelers purple at normal ΔE 7.8). NYC geocoding re-run cost only 34 Google + 47 GeoSearch calls (cache); `nyc_entries_geocoded.csv` 8,108 rows, `nyc_geo.json` 7,996 entries; 5 new review-flagged rows inspected, all correctly flagged. 4,664 thumbs built (0 errors, crops visually verified) and published to HF. Rights: all 4 volumes PDREN/NoC-US via NYPL API; `volume_rights.csv` 50 rows, still exactly 1 orphan work. Verified: full Playwright viewer suite green; live deep link into the 1956 volume zooms exactly onto its entry with the highlight box; all-volumes/travel-guides/nyc explorers load 113,827 / 46,775 / 8,108 rows with the new facets and colors and zero console errors. HF upload of the main dataset to `hadro/green-books-travel-guides` remains a manual step.*

## Context

NYPL digitized a new publication — *Afro-American's Travel Guide*, published by the Travel Bureau of the Afro-American newspapers (Baltimore) — and all four volumes have been run through directory-pipeline. Output lives at `/Users/joshhadro/github/directory-pipeline/output/afro-american-travel-guide-{1954,1956,1957,1958}/` (`entries_gemini-3.1-flash-lite_fixed.csv` in each, written 2026-08-13).

This becomes the **8th publication** and volumes **47–50** of the corpus: ~4,714 raw rows, **4,664 after the standard combine filter** (drop `flag_unanchored`, `flag_hallucinated`, and rows lacking `#xywh=`). Totals move: `travel_guides_all.csv` 42,111 → **~46,775**; merged corpus 109,163 → **~113,827**; volumes 46 → **50**; publications 7 → **8**. Year ranges (1930–1966 corpus, 1930–1962 travel guides) are unchanged, but **1958 becomes a data-bearing year for the first time**.

Poetic detail: the about-modal copy in `all-volumes.html:1260` and `nyc.html:1228` currently cites *"the Afro-American's Travel Guide … not digitized here"* as the canonical example of a gap in the corpus. That sentence gets rewritten.

Decisions made with the user (2026-08-13):
- **Full sweep**: all-volumes.html fully, plus travel_guides_explorer.html, nyc.html, HF dataset cards, and all docs in one pass.
- **NYC geocoding re-run is IN scope** (not deferred): extend `nyc_entries_geocoded.csv` and rebuild `nyc_geo.json` so new NYC rows get map pins.
- **`publication` = `Afro-American's Travel Guide`**, short display name **`Afro-American`** (matches NYPL catalog title and the existing about-modal reference).
- Follow the `scripts/append_loc_1946.py` precedent: one-off committed append script, no pipeline `combine_volumes.py` generalization (the flat `output/afro-american-travel-guide-YYYY/` layout doesn't fit its `<collection>/<uuid>/` glob anyway).

## Key facts (drive the design)

Per-volume inventory (all IIIF **v3** manifests, `id`/`items` — not the v2 `sequences` path `append_loc_1946.py` reads):

| Year | NYPL item UUID | canvases | fixed rows | rows after filter | distinct `image` |
|---|---|---|---|---|---|
| 1954 | `b5f95f60-7256-013f-3691-0242ac110002` | 52 | 1,287 | 1,287 | 48 |
| 1956 | `e36a5750-7256-013f-f2b2-0242ac110002` | 40 | 1,114 | 1,113 | 39 |
| 1957 | `fb4f57d0-7256-013f-8933-0242ac110003` | 48 | 1,159 | 1,127 | 45 |
| 1958 | `2a3699e0-7257-013f-019f-0242ac110003` | 48 | 1,154 | 1,137 | 46 |

NYPL collection UUID (all four): `52af6e40-7256-013f-1a2f-0242ac110002` → `https://digitalcollections.nypl.org/collections/52af6e40-7256-013f-1a2f-0242ac110002` (use for the about-modal legend link).

- **Schema**: raw CSVs have 16 columns, no volume metadata. Map to the 28-column `travel_guides_all.csv` schema exactly as `combine_volumes.py` does: `details`→`notes`, `state_country`→`state`; add `volume_id` (UUID), `volume_title` (manifest `label.en[0]`), `volume_year`, `publication`; empty-fill `sub_region, proprietor, amenities_services, rates, personnel, reference_number, is_advertisement, is_recommended`. All 7 flag columns carry over as-is. (No drift columns — those are GB-only.)
- **THE hard gotcha — placeholder canvas dims**: the four manifests report **every canvas as 2560×2560** (the known square-placeholder bug). Real dims (e.g. 3560×7780; six distinct sizes in 1954 alone) live in the per-page `*_gemini-3.1-flash-lite_aligned.json` sidecars as `canvas_width`/`canvas_height`, and the CSV `#xywh=` coords are in **that** space. Verified: for existing volume `0b8da6b0-…` the sidecar dims exactly equal `travel_guides_canvas_map.json` slots 1–2. So canvas-map entries **and** the copied manifests must take dims from the sidecars, never from the shipped manifest — otherwise Clover fragment zoom, the `liveIiifUrl()` pct-crop fallback, and `build_all_thumbs.py` crops are all wrong.
- **Existing repair tool for exactly this**: `directory-pipeline/tools/rescale_canvas_fragments.py` fixes aligned JSON written against the placeholder canvas size (fetches natural dims from `info.json`, rescales every `#xywh=`, updates sidecar `canvas_width/height` in place; `align_ocr.py` warns and names it when it detects the fallback). For these four volumes the sidecars already hold natural dims, so it runs as a **pre-flight verifier in `--dry-run`** — and as the fix if any individual page did silently fall back. It does **not** patch manifest dims; that stays in the append script.
- **`index.html` viewer needs zero code changes**: the NYPL cf regex (`index.html:601`) matches, and the dual lookup `gbLookup[imageId] || tgLookup[imageId]` + manifest fetch (`index.html:624-633`) already covers travel guides. Only data files change.
- **all-volumes.html facets are runtime-computed** (`gbBuildFacets()`, [all-volumes.html:1392](all-volumes.html#L1392)) — no baked FIELD_META there. `travel_guides_explorer.html` **does** bake FIELD_META at `:733`, and it's already stale today (year top_values sum to 43,365 vs the CSV's 42,111) — this pass fixes that too.
- **Palette**: `PUBLICATION_COLORS` needs an 8th color, and the comment at [all-volumes.html:1340-1348](all-volumes.html#L1340-L1348) documents the palette as CVD-validated (dataviz `validate_palette`, surface `#faf8f3`, closest pair ΔE 9.3 protan). The new color must be validated against all seven existing. There are **three divergent palette copies**: `all-volumes.html:1349`, `travel_guides_explorer.html:757` (different hexes by design), `nyc.html:1321` (matches all-volumes).
- **Data quirks**: 1954 contains non-listing content (a fishing-license calendar, `flag_header_row=1` rows); 1,442 rows across the four have blank `category` (folds to "Blank or no specific category"). Keep all rows with flags set, per existing convention. New pass-through category labels appear (YMCA 82, YWCA 57, CAMPS 55, ROOMING HOUSES 12, TRAVEL AGENCIES 12, BARS AND COCKTAIL LOUNGES 6) — leave them as legitimate distinct labels; **no `gb-categories.json` change** unless review says otherwise.
- **Geocoding is cache-safe**: `directory-pipeline/scripts/geocode_nyc_neighborhoods.py` reads both master CSVs (defaults point at the green-books repo) and caches every API result, so a re-run after the append only geocodes the ~new NYC rows; nothing existing re-bills.

---

## Step 1 — `scripts/append_afro_american.py` (data + all JSON artifacts)

**Step 0 — pre-flight dims check** (before any artifact is generated): run the existing repair tool per volume dir,
```bash
cd /Users/joshhadro/github/directory-pipeline
uv run python tools/rescale_canvas_fragments.py output/afro-american-travel-guide-1954/ --aligned-model gemini-3.1-flash-lite --dry-run   # × 4 dirs
```
Expected: every page reports natural dims already matching `info.json` (no rescale). If any page *did* fall back to 2560×2560, drop `--dry-run` to fix it in place, then re-run the volume's `fix_entries.py` step only if the tool rewrote CSV-facing fragments (it rescales the aligned JSON; the fixed CSVs were generated from those, so a rewrite here means regenerating that volume's `_fixed.csv` before appending).

One committed one-off script mirroring `scripts/append_loc_1946.py` (module-constant paths, run once):

1. **Idempotency guard**: abort if any of the 4 UUIDs already appear in `travel_guides_all.csv`'s `volume_id` column.
2. For each volume: read `entries_gemini-3.1-flash-lite_fixed.csv`, apply the combine filter (`flag_unanchored`, `flag_hallucinated`, missing `#xywh=`), map to the 28-column header (per Key facts), and **append** to `travel_guides_all.csv`. Expected ≈46,775 rows; record the exact count.
3. **`travel_guides_image_to_volume.json`**: add `{<numeric image id>: <uuid>}` for every distinct image id per volume (~178 new keys; extraction regex `/iiif/\d+/(\d+)/` on `canvas_fragment`, same as `index.html:601`).
4. **`travel_guides_canvas_map.json`**: one entry per page with entries: `"<cf base>": [service_base, real_w, real_h, "https://digitalcollections.nypl.org/items/<uuid>?canvasIndex=<n>"]` — **w/h from the `*_aligned.json` sidecars** (match sidecar `canvas_uri` to the cf base), `canvasIndex` from manifest canvas order. Warn on any cf base with no sidecar match.
5. **`manifests/<uuid>/manifest.json>` × 4**: copy each pipeline manifest, rewrite top-level `id` to `https://hadro.github.io/green-books/manifests/<uuid>/manifest.json` per repo convention (v3 `items` traversal — do not reuse the LOC script's v2 `sequences` code), and **patch every canvas/image `width`/`height` from the sidecars** (fall back to leaving a canvas untouched + warning if a page has no sidecar, i.e. pages with no entries).
6. **FIELD_META recompute** for `travel_guides_explorer.html`: year distribution, top-6→7 publications, folded top-25 categories (via `gb_categories.gb_category_group`), per-column fill rates and cardinalities → write a scratch JSON for review (like `append_loc_1946.py`'s `recompute_field_meta()`; the HTML edit stays manual).

## Step 2 — `all-volumes.html`

**Config** (all runtime facets self-update; these are the only code edits):
- [all-volumes.html:1349-1357](all-volumes.html#L1349-L1357) `PUBLICATION_COLORS`: add `"Afro-American's Travel Guide"`. Load the **dataviz skill** first, pick a candidate distinct from all 7 (a warm brown/tan or slate region of the space is open), run `validate_palette` against surface `#faf8f3`, and **update the comment block** at `:1340-1348` with the new validation result.
- [all-volumes.html:1361-1369](all-volumes.html#L1361-L1369) `PUBLICATION_SHORT_NAMES`: `"Afro-American"`.
- [all-volumes.html:5226](all-volumes.html#L5226) `MERGED_ENTRIES_TOTAL_APPROX = 109163` → new exact total; refresh the recipe comment at `:5220-5225` with the new per-CSV counts.

**Copy** (old → new):
- `:8` / `:16` og/twitter descriptions: "more than 109,000 entries" → "more than 113,000"; "six other Black travel guides" → "seven".
- `:940` commented-out eyebrow "109,163 ENTRIES · 46 VOLUMES" → new numbers.
- `:966` `#hero-stat-entries` 109,163 → new total; `:967` editions 46 → 50 (both are overwritten at runtime by `gbUpdateStats()` but the SSR values should match).
- `:968` states `89` and `:970` categories `43`: recompute per the recipes in the adjacent comments (states+countries count may shift slightly; categories = folded labels ≥100 entries excl. blank — YMCA at 82 may or may not cross later, check).
- `:1136` trends caveat "the 46 volumes" → 50.
- `:1243` about lede "six other travel guides published … between 1930 and 1962" → "seven other travel guides…" (range unchanged).
- `:1247` "searches across seven publications" → "eight".
- `:1249-1256` publication legend: add an 8th `<li>` — pub-dot with the new hex, *Afro-American's Travel Guide* linking to the NYPL collection (`52af6e40-…`), "1954–1958".
- `:1260` **the rewrite**: "45 digitized volumes across these seven publications" → "50 digitized volumes across these eight publications"; remove *Afro-American's Travel Guide (1939)* from the not-digitized examples (keep *The Black American Travel Guide* (1971); optionally note the 1939 Afro-American edition specifically remains undigitized).
- `:1275` about entries stat; `:1280` volumes 46 → 50; `:1281` "across 7 publications" → 8.
- `:4849` coverage-grid comment citing "isolated dead years (e.g. 1958)" — pick a different example year (1958 now has data).
- `GB_MILESTONES` (`:5726-5737`): no change needed, but note 1954/1956 milestone labels now coincide with new-volume years on the stacked chart — eyeball for collision in verification.

## Step 3 — `travel_guides_explorer.html`

- `:733` **rebake the full FIELD_META blob** from the Step 1 scratch JSON (this also fixes today's staleness; year top_values must sum to the new CSV total, `publication.cardinality` 6 → 7).
- `:757-764` `PUBLICATION_COLORS`: add a 7th color **in this page's own palette** (its hexes intentionally differ from all-volumes) — validate with dataviz against this page's surface.
- `VOLUMES` map + `#volume-select` dropdown (`:732`, `:800`, `:827-859`): add the four volumes.
- Copy: `:8`/`:16` meta; `:551` eyebrow "43,365 ENTRIES · 22 VOLUMES" → new/26; `:577` entries stat; `:578` "23 published volumes" → **26** (fixing the pre-existing off-by-one — actual is currently 22); `:579-580` states/categories recompute; `:595` sidebar year range check; `:684-693` "These six guides" / "six publications" → seven + add the legend `<li>`; `:711-715` about stats (entries / 26 volumes / "across 7 publications, covering 1930 — 1962").

## Step 4 — NYC geocoding re-run + `nyc.html`

Run **after** Step 1 lands (the scripts read the updated master CSVs):

1. `directory-pipeline/scripts/geocode_nyc_neighborhoods.py --geojson /Users/joshhadro/github/green-books/nyc-neighborhoods/nyc-neighborhoods.geojson --cache /Users/joshhadro/github/green-books/nyc-neighborhoods/nyc_geocode_cache.json --out /Users/joshhadro/github/green-books/nyc-neighborhoods/nyc_full_results.json` — needs `GOOGLE_MAPS_API_KEY` in the pipeline `.env`; the cache means only new NYC rows hit the APIs (~a few hundred at most out of 377 NY-state rows; only NYC-city rows qualify via `is_nyc()`).
2. `directory-pipeline/scripts/merge_nyc_geocode_csv.py --cache <same cache> --out /Users/joshhadro/github/green-books/nyc-neighborhoods/nyc_entries_geocoded.csv` (its `--csv` defaults already point at both green-books master CSVs).
3. In green-books: `python3 scripts/build_nyc_geo.py` → regenerated `nyc_geo.json`; review any newly review-flagged rows (manual queue) before committing.
4. `nyc.html` edits: `PUBLICATION_COLORS` `:1321` + `PUBLICATION_SHORT_NAMES` `:1333` (the map legend at `:4069-4070` generates itself from the colors object); copy at `:17`, `:25`, `:955`, `:1104`, `:1211`, `:1215`, `:1228` (same "Afro-American's … not digitized here" rewrite as Step 2), `:1243`.
5. `nyc.html`'s hero/about counts reflect the NYC subset — recompute from the new `nyc_entries_geocoded.csv` row count.

## Step 5 — Thumbnails (must follow Step 1: `load_candidates()` needs valid canvas-map dims)

1. Build (resumable; only the ~4,664 new tids get cropped):
   ```bash
   /Users/joshhadro/github/directory-pipeline/.venv/bin/python scripts/build_all_thumbs.py \
     --images-dir /Users/joshhadro/github/directory-pipeline/output/afro-american-travel-guide-1954 \
     --images-dir /Users/joshhadro/github/directory-pipeline/output/afro-american-travel-guide-1956 \
     --images-dir /Users/joshhadro/github/directory-pipeline/output/afro-american-travel-guide-1957 \
     --images-dir /Users/joshhadro/github/directory-pipeline/output/afro-american-travel-guide-1958 \
     --format webp --jobs 7
   ```
   Local scans are 2048px wide; the `sx = iw/cw` rescale is correct once canvas-map dims are real. Sanity-check a few crops visually before publishing (the dims bug would show up here as garbage crops).
2. Publish: `python scripts/publish_thumbs.py --resume` (only shards with new files commit; also re-uploads `hf-dataset-thumbs/README.md` — so update that card **first**, see Step 6).
3. Hero thumbs: no rebuild required (curated pool; `IMAGE_ID_RE` matches the new cfs fine). Optional later refresh to feature new-volume entries.

## Step 6 — Hugging Face datasets

1. `hf-dataset/build.py` needs **no code change** — the four NYPL volumes inherit the default `NYPL / PDREN / NoC-US / public_domain=true` rights row. **But verify first**: check each of the 4 UUIDs' rights via the NYPL MCP `get_rights_info` (as done for the original 45) and eyeball the item pages; if any differ from PDREN, add a special case next to `ORPHAN_UUID`.
2. Run `build.py` → `travel_guides_green_book_all.csv` (~113,827), `volume_rights.csv` (50 rows), `_hf_build_stats.json`.
3. `hf-dataset/README.md` card: `:70` `num_examples`; `:75` "109,163 … 46 volumes … six lesser-known companion publications" → new totals / "seven"; `:93` sources; `:103` volume_id desc; `:109` + `:145` category/state fold counts (recompute — new raw labels shift "759 → 462"); `:120`; `:129-131` rights math ("45 NYPL volumes" → 49; "45 of 46" → "49 of 50"; orphan line "1 of 46" → "1 of 50"); `:135`; `:154`; `:166`; `:182` citation "46 digitized volumes" → 50.
4. `hf-dataset-thumbs/README.md`: `:22` thumb count/volumes/date range; `:38` companion-dataset row 109,163 → new; `:74` "45 of 46"; `:100` citation.
5. Upload of the main dataset to `hadro/green-books-travel-guides` stays a **manual user step** (per LOC precedent).

## Step 7 — Docs + housekeeping

- `README.md`: `:3` "six other … 1930 and 1962" → seven; `:7` "~109,200 … 46 volumes and seven publications" → new; file table `:11-34`; `:94` corpus paragraph (six-guide enumeration gains Afro-American's Travel Guide 1954–1958; totals).
- `CLAUDE.md` + `AGENTS.md`: volume/entry counts throughout; **also fix stale claims found during exploration** — `travel_guides_image_to_volume.json` "not yet built" (it's built and on main), "22 sibling travel guide volumes" → 26, sibling explorer "not yet started" (it's live), pending-work list.
- `.claude/skills/green-books-data/SKILL.md`: "109,163 … 46 volumes" (`:3,:8,:13,:45,:47,:146,:157`) → new totals/counts; then rerun `scripts/build_query_db.py` (its docstring counts at `:13,:20` too) so the skill's query DB includes the new rows.
- `index.html:151` "Search across all seven publications" → eight; `index.html:542` stale ratio comment.
- `docs/mcp-server-plan.md` + `docs/ia-mirroring-notes.md` counts (low priority, but full sweep).
- Commit this plan as `docs/afro-american-integration-plan.md` (provenance, mirroring the LOC plan), updating its status line with actual numbers post-run.
- Skip: `address-keying-test.html` (scratch), directory-pipeline `_COLLECTION_LABELS`/`green_books_and_related.csv` (append-script pattern doesn't need them; note as known-stale).

## Verification

1. **Data**: `travel_guides_all.csv` row count = old + appended; every new row parses against the 28-col header with correct `volume_id/volume_year/publication`; spot-check a 1954 `flag_header_row` row survived with its flag; JSON artifacts key counts (+~178 each).
2. **Viewer deep link (the gating check for the dims fix)**: `python3 -m http.server`, open `index.html?cf=<encoded new-volume cf>` → manifest loads, Clover zooms to the exact `#xywh` region (wrong dims ⇒ zoom lands in the wrong place). Regression-test one existing Travelguide cf and one LOC cf.
3. **all-volumes.html**: progress bar reaches ~100% (new APPROX total); publication facet shows 8 values with the new color; year facet gains 1958; coverage grid has 8 rows with Afro-American active 1954–58 (and 1958 no longer renders as a break column); trends stack + tooltips; detail panel thumbnail (live-IIIF fallback pre-publish — this independently validates the pct-crop dims); "Source ↗" opens `digitalcollections.nypl.org/items/<uuid>?canvasIndex=<n>` on the right page; about modal reads correctly.
4. **travel_guides_explorer.html**: baked facet counts match runtime data (no console mismatch); volume dropdown shows 26; new color on rows.
5. **nyc.html**: new pins/rows present; publication legend shows 8; neighborhood joins hold (`build_nyc_geo.py --check` passes).
6. **Thumbs**: after publish, ~10 random new tids load from the HF CDN in all-volumes detail panels.
7. **HF build**: `_hf_build_stats.json` totals; `volume_rights.csv` = 50 rows with 4 new NYPL/PDREN lines; `pandas.read_csv` schema check.
8. `tests/run.sh` manually (viewer CI path filter doesn't trigger on manifests/JSON).

## Execution strategy — delegate mechanical work to cheaper subagents

| Work item | Who |
|---|---|
| Step 1 pre-flight `rescale_canvas_fragments.py --dry-run` × 4 | **haiku** subagent (run + report; escalate to main model if any page needs rescaling) |
| Step 1 append script (schema map fully specified; sidecar-dims logic is the careful part) | **sonnet** subagent, main model reviews the dims-patching code |
| Step 2 palette pick + validation (dataviz skill) | **main model** |
| Steps 2–4 copy edits (exact old→new drafted by main model first) | **haiku** subagents |
| Step 3 FIELD_META rebake (values from Step 1 scratch JSON) | **sonnet** subagent |
| Step 4 geocoding runs + merge + build_nyc_geo | **sonnet** subagent (API-billed — main model reviews the command + new-row count before running) |
| Step 5 thumb build/publish commands | **sonnet** subagent after main model eyeballs sample crops |
| Step 6 rights verification (MCP) + card prose | **main model** (rights/licensing care), counts by **haiku** |
| Step 7 docs sweep | **haiku** subagent |
| All verification | **main model** |

## Lift estimate

**Moderate — comparable to the LOC 1946 integration, roughly a day.** The genuinely new engineering is small: the sidecar-dims patching in the append script (the one real gotcha), one CVD-validated palette addition ×3 files, and the FIELD_META rebake. The NYC geocoding re-run adds half a day of babysitting (API run + review queue) but the cache keeps it cheap. Everything else is mechanical copy/count edits with exact line anchors. Main risks: canvas-dims mistakes (caught by the viewer deep-link test) and any of the four volumes' NYPL rights differing from PDREN (caught by the MCP check before HF publish).
