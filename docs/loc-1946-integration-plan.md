# Incorporate the LOC 1946 Green Book into the site + HF dataset

*Status: implemented 2026-07-19/20 (uncommitted). Actual numbers: 3,462 rows appended (15 skipped for missing `#xywh=` anchors), master CSV 67,052 rows, merged HF dataset 109,163 across 46 volumes. Verified: full Playwright viewer suite green; live LOC deep-link zooms to the entry with tiles + CORS working; explorer and all-volumes facets, LOC thumbnails, and source links confirmed in headless Chrome. HF upload to hadro/green-books-travel-guides remains a manual step; eyeball the LOC item page's Rights & Access wording (loc.gov blocks non-browser fetches) before publishing.*

## Context

A previously-missing edition — *The Negro Motorist Green Book: 1946*, digitized by the **Library of Congress** (item `2016298176`) — has been run through directory-pipeline. Its output lives at
`/Users/joshhadro/github/directory-pipeline/output/the_negro_motorist_green_book_2016298176/2016298176/entries_gemini-3.1-flash-lite_fixed_drift_flagged.csv`
(3,477 entries, 46 states, drift-scored: 3,394 clean / 83 flagged; no hallucination/unanchored flags; every row has a pixel `#xywh=` canvas_fragment).

This is the first **non-NYPL** volume in a corpus where all 45 existing volumes are NYPL. It fills the wartime gap (existing GB editions jump 1939 → 1947). Decisions made with the user:

- **One-shot scripted append** onto the reviewed master CSV (a full pipeline re-combine would destroy the manual `Fixed or checked` review baked into `green_book_entries_all.csv`). Pipeline generalization is out of scope.
- **Include all 3,477 rows** with drift columns populated, consistent with existing volumes.
- **Defer hero-thumbs** LOC support (but verify the hero build doesn't crash on LOC rows).
- **Rebuild the HF dataset in the same pass**, generalizing the rights table for a second source institution. Upload to HF remains a manual step by the user.

### Key facts discovered (drive the design)

- **Schema drift**: the LOC CSV has `description` (→ maps to master `notes`, same mapping combine_volumes.py uses at `analysis/combine_volumes.py:85`), an extra `flag_hallucinated` (all empty; master schema lacks it — drop), and lacks `sub_region, amenities_services, rates, personnel, reference_number, is_recommended, Fixed or checked` (fill empty). `volume_id` is `2016298176` (not a UUID) — fine, it's just a string key.
- **Master CSV**: 63,590 rows; header at [green_book_entries_all.csv:1](green_book_entries_all.csv#L1).
- **LOC manifest alignment is perfect**: the pipeline output already contains the LOC IIIF **v2** manifest (`output/.../2016298176/manifest.json`, 84 canvases, `attribution: "Provided by the Library of Congress"`), and its canvas `@id` == image `service @id` == the CSV `canvas_fragment` base (`https://tile.loc.gov/image-services/iiif/service:gdc:gdcscd:...:NNNNN`). So the viewer's `buildCanvasIndex` matching ([index.html:207-220](index.html#L207-L220), `:471-477`) works unmodified once the manifest is served locally.
- **The one hard viewer break**: [index.html:526](index.html#L526) — `cf.match(/\/iiif\/\d+\/(\d+)\//)` only matches NYPL numeric IDs; a `tile.loc.gov/...iiif/service:gdc:...` cf → "Unrecognised canvas fragment URL". `viewer-src/App.jsx` mentioned in CLAUDE.md **does not exist** — the viewer is fully inline in `index.html`.
- **Categories fold cleanly**: only two new folded labels appear — `CABINS FOR TOURISTS` (2 rows-ish) and `NEWSPAPERS` (119 rows). No `gb-categories.json` change required unless we want to fold them into existing groups (recommended: add `CABINS FOR TOURISTS` as a variant of TOURIST HOMES-adjacent? No — leave both as their own labels; they're legitimate distinct categories).
- **LOC blocks non-browser clients** (curl → 403 on loc.gov manifest URL) — one more reason to serve a committed local manifest copy, like every NYPL volume already does. Browser-side CORS on `tile.loc.gov` info.json/tiles must be verified in the browser test.
- **Explorer link plumbing is mostly source-agnostic**: explorer/all-volumes build `index.html?cf=` links from the raw `canvas_fragment` and use `canvas_map.json` for thumbs. A LOC branch of `viewerUrl()` **already exists** ([explorer.html:1303-1321](explorer.html#L1303-L1321), [all-volumes.html:1955-1968](all-volumes.html#L1955-L1968)) — currently dead code, activated once LOC entries appear.

---

## Step 1 — Append script + master CSV update

Write a one-off script `scripts/append_loc_1946.py` (committed for provenance) that:

1. Reads the LOC CSV, maps columns to the exact master header (`description`→`notes`, drop `flag_hallucinated`, empty-fill missing columns), sets `volume_title` = `The Negro Motorist Green Book: 1946`, `volume_year` = `1946`.
2. Skips any row lacking `#xywh=` in `canvas_fragment` (same filter as `combine_volumes.py:285-291`; currently 0 rows affected).
3. Appends to `green_book_entries_all.csv` → new total **67,067 rows** (verify exact count at run time).
4. Is idempotent (refuses to run if `volume_id 2016298176` already present).

## Step 2 — Viewer plumbing (index.html + JSON artifacts)

1. **`manifests/2016298176/manifest.json`** — copy the LOC v2 manifest from the pipeline output. Follow the existing convention: rewrite the manifest `@id` to `https://hadro.github.io/green-books/manifests/2016298176/manifest.json`; leave image/service `@id`s pointing at `tile.loc.gov` (do NOT rewrite canvas `@id`s — they must keep matching the cf base, and Clover normalizes v2). If Clover's v2 handling misbehaves in the browser test, fall back to a minimal v2→v3 conversion.
2. **`image_to_volume.json`** — add entries mapping each LOC image key → `"2016298176"`. Key = the full `service:gdc:gdcscd:...:NNNNN` token (extracted from cf), one per page that has entries.
3. **[index.html:519-530](index.html#L519-L530)** — generalize the cf parser: keep the NYPL regex, add a LOC branch matching `/image-services\/iiif\/(service:[^/#]+)/` and use the captured service token as the lookup key. Error message unchanged for anything that matches neither.
4. **`canvas_map.json`** — add one entry per LOC page: `"<cf base>": [service_base, width, height, viewer_url]` using w/h from the LOC manifest canvases and viewer_url `https://www.loc.gov/resource/00212275098/?sp=<n>` (or omit slot 3 and rely on the existing LOC `viewerUrl()` branch — prefer explicit slot 3 since `currentDocMeta.resource_url` is never populated). This powers detail-panel thumbnails (`thumbUrl()` is IIIF-generic) and the "View page ↗" external link.

Generate items 2 and 4 inside `append_loc_1946.py` (single script, reads the LOC manifest for dimensions) rather than by hand.

## Step 3 — explorer.html (data + copy)

- **FIELD_META** ([explorer.html:765](explorer.html#L765)): add `["1946", 3477]` to `volume_year.top_values` in year order, bump its `cardinality` 22→23. Recompute `category.top_values` (top-25 folded) and per-field `fill_rate`s from the updated CSV — small Python snippet, same method as the comment at `:756-763` documents.
- **Copy**:
  - `:596` + `:722` hero/about entry stat `63,185` → new total
  - `:597` `23` volumes → `24`; `:726-728` about volume stat
  - `:704-707` about modal: currently "earliest edition digitized here is 1937" and NYPL-only sourcing — update to note the 1946 edition comes from the **Library of Congress** ("Page scans for the 1946 edition provided by the Library of Congress" alongside the existing NYPL credit, with a link to https://www.loc.gov/item/2016298176/)
  - `:577` + `:735` hero/footer source credit: amend "Source material held by the New York Public Library…" to acknowledge LOC for 1946
  - `:8`/`:16` og/twitter descriptions (note pre-existing "1933-1966" inconsistency — fix to 1937 while there)
  - About-modal publication link list: add the LOC item link for 1946 (the modal links each publication to its NYPL source per commit `1b63fba` — the 1946 line should point at LOC)

## Step 4 — all-volumes.html (copy only)

Facets (`volume_year`, `publication`) are computed at runtime — no FIELD_META edit. Copy:
- `:8`/`:16` meta descriptions "more than 105,000 entries" → still true, but verify phrasing
- `:914` "the 45 volumes in this dataset" → 46; `:1038` "45 digitized volumes" → 46
- `:783` + `:1071` NYPL source credits → add LOC acknowledgment
- `:1025-1033` per-publication edition list: Green Book row gains the 1946 edition with an LOC link (year range 1937–1966 unchanged)
- `:1035` "Page scans provided by the New York Public Library Digital Collections" → "…and the Library of Congress"
- `:3724-3725` update the baked count comment (63,590 → 67,067 GB rows)
- Hero/about stat tiles for entry totals, mirroring Step 3

## Step 5 — Hugging Face dataset (hf-dataset/)

1. **`build.py`** generalize rights handling ([hf-dataset/build.py:34-35](hf-dataset/build.py#L34-L35), `:104-122`):
   - Rename `nypl_copyright_status` → `copyright_status` (or add `source_institution` column — recommended: add `source_institution` with values `NYPL` / `LOC` and keep a generic `copyright_status`).
   - LOC volume row: `source_institution=LOC`, rights statement `NoC-US` (http://rightsstatements.org/vocab/NoC-US/1.0/), `public_domain=true` — 1946 US publication, copyright not renewed; LOC provides it with no known restrictions. Verify against the LOC item page rights note before publishing and record what it says.
   - Keep the existing NYPL orphan-work special case untouched.
2. Run `build.py` → regenerated `travel_guides_green_book_all.csv` (105,701 → ~109,178 rows), `volume_rights.csv` (46 rows), `_hf_build_stats.json`.
3. **`README.md` dataset card**: front-matter `num_examples`; body counts (`:75` "45 volumes" → 46, Green Book table row 63,590 → 67,067); `:93` sources — add LOC/GPO provenance sentence; `:103` `volume_id` description ("NYPL Digital Collections UUID, or LOC item ID for the 1946 edition"); `:120` `image` column description; `:129-133` rights section — rewrite "44 of 45" math (45 of 46 PD + 1 orphan), note the LOC volume's provenance and add "From the Library of Congress" courtesy line alongside NYPL's.
4. User uploads to `hadro/green-books-travel-guides` manually (no publish script exists; out of scope).

## Step 6 — Docs + housekeeping

- `README.md` (repo): `:14` (~63,000/23 editions → ~67,000/24), `:15`, `:23` (image_to_volume.json now "NYPL image IDs and LOC service IDs"), `:51-55` viewer flow, `:66`, source acknowledgments.
- `CLAUDE.md` / `AGENTS.md`: update volume counts, note the LOC volume + its ID scheme, and **fix the stale `viewer-src/App.jsx` references** (viewer is inline in index.html).
- Verify `scripts/build_hero_thumbs.py` won't crash if rerun later: `load_candidates()` filters on canvas_map membership *before* the NYPL regex is applied — but we are now **adding** LOC entries to `canvas_map.json`, so LOC rows will pass that filter and hit `IMAGE_ID_RE.search(cf).group(1)` → AttributeError ([scripts/build_hero_thumbs.py:63](scripts/build_hero_thumbs.py#L63), `:347`). Add a two-line guard that skips rows whose cf doesn't match `IMAGE_ID_RE` (deferring real LOC support).

## Verification

1. **Data**: row count check; `python3 -c` spot checks that appended rows parse with the master header, all have `volume_year=1946`, and folded categories/states look sane; re-run the FIELD_META recompute and diff against what's baked.
2. **Explorer** (`python3 -m http.server`): 1946 appears in the year facet with count 3,477; filter to it; open a detail panel → thumbnail renders from `tile.loc.gov` (canvas_map path); "View page ↗" goes to the right loc.gov resource page.
3. **Viewer deep link**: `index.html?cf=<encoded tile.loc.gov cf>` → manifest loads, Clover renders the LOC page, zooms to the `#xywh` region. Also regression-test one NYPL cf link. Watch the console for CORS errors from `tile.loc.gov` (the fetch monkey-patch is a no-op for LOC; if CORS fails, that's a stop-ship for the viewer piece and we discuss options).
4. **all-volumes.html**: 1946 shows under publication "The Negro Motorist Green Book"; runtime facets correct; stats/copy read correctly.
5. **HF build**: run `build.py`; check `_hf_build_stats.json` totals and the new `volume_rights.csv` row; `pandas.read_csv` the output to confirm schema.

## Execution strategy — delegate to cheaper subagents where possible

Per user request, mechanical work goes to cheaper subagents (Agent tool with `model: "haiku"` for rote edits, `model: "sonnet"` for scripted-but-careful work); the main model handles only the judgment-heavy pieces and final verification.

| Work item | Who |
|---|---|
| Step 1 append script + run (schema map is fully specified above) | **sonnet** subagent |
| Step 2.1–2.2, 2.4: manifest copy/patch + `image_to_volume.json` + `canvas_map.json` generation (part of the same script) | **sonnet** subagent (same one as Step 1) |
| Step 2.3: `index.html` cf-parser LOC branch | **main model** (small but load-bearing; breaks all deep links if wrong) |
| Step 3 FIELD_META recompute + all copy edits in explorer.html | **haiku** subagent for the copy edits, given exact line refs + replacement text drafted by main model; FIELD_META values computed by the Step 1 script |
| Step 4 all-volumes.html copy edits | **haiku** subagent (same pattern) |
| Step 5.1 build.py rights generalization | **main model** (rights/licensing logic — worth the care) |
| Step 5.2–5.3 run build.py + README card count/provenance edits | **sonnet** subagent, with main model reviewing the rights-section prose |
| Step 6 README/CLAUDE.md/AGENTS.md updates + hero-thumbs crash guard | **haiku** subagent |
| Verification (browser tests, regression checks) | **main model** |

Main model drafts the exact copy replacements (attribution language especially) before handing edit batches to haiku agents, and reviews all subagent diffs before commit.

## Lift estimate

**Moderate — roughly a day of focused work, most of it mechanical.** The data appends and copy edits are easy; the genuinely new engineering is small and well-localized: one regex branch in `index.html`, one generator script for the three JSON artifacts, and the rights-table generalization in `build.py`. The LOC manifest aligning exactly with the CSV canvas_fragment bases removes what would otherwise have been the hard part. The main risk is browser-side (Clover v2 handling + tile.loc.gov CORS), which is why the viewer deep-link test is the gating check.
