# Integrate the 1958 Green Book (NYPL b4affe50-7ca3-013f-af86-0242ac110002)

*Status: implemented 2026-10-20/21. 2,169 rows appended, `green_book_entries_all.csv` 67,052 → 69,221, merged corpus 113,827 → 115,996 across 51 volumes and 8 publications (publications unchanged). +75 keys each in `image_to_volume.json` / `canvas_map.json`; manifest written with real dims on all 84 canvases. Drift: 2,089 rows score 0 and 80 score 1. NYC geocoding re-run: 3 Google + 3 GeoSearch calls, `nyc_entries_geocoded.csv` 8,108 → 8,163 rows; 1 new review-flagged row (160 Reid Ave., flagged the same way in every edition 1953–1961). Rights: PDREN / NoC-US via the NYPL API; `volume_rights.csv` 51 rows, still exactly 1 orphan work. Thumbnails: 2,169 to build, 0 missing scans.*

## Context

NYPL digitized *The Negro Travelers' Green Book: 1958* ("Spring 1958", "1958 EDITION" on the title page). The pipeline output directory was first referred to as the 1948 edition; it is not. The corpus already had 1948 (`3a67a6d0-…`) and was missing 1958, so this fills the 1957 → 1959 gap. It is the Green Book's 25th digitized edition.

Pipeline output: `directory-pipeline/output/b4affe50-7ca3-013f-af86-0242ac110002/` (84 canvases, flat layout like the Afro-American volumes, not under `green_books_and_related/`).

Precedents followed: `docs/loc-1946-integration-plan.md` (Green Book master target, drift columns, `explorer.html` FIELD_META) and `docs/afro-american-integration-plan.md` (NYPL IIIF v3 manifest, placeholder canvas dims, NYC geocoding, thumbnails, HF cards).

## What was different this time

1. **The extraction ran with a 9-column NER schema and no category field.** `state, city, section, business_name, address, notes, is_advertiser, canvas_fragment, image`. The 1958 book has no per-category headings anyway: each state prints one combined "Hotels — Motels — Tourist Homes — Restaurants" line. Categories therefore come from name-based inference, as they did for 1957 and 1959. Re-running NER would not have added them.
2. **`fix_entries.py` silently dropped the inferred categories.** Its schema detection knew `category` and `section_category` but not `section`, so inference wrote to a column the writer never emitted. Fixed in `directory-pipeline/analysis/fix_entries.py` by adding `section` to the category candidates (tests pass). With the fix: 1,816 inferences, HOTELS 930 / TOURIST HOMES 494 / RESTAURANTS 336, close to 1957's 900 / 492 / 321.
3. **Five pages' aligned sidecars had fallen back to the 2560×2560 placeholder** (0009, 0040, 0056, 0077, 0078). Fixed with `tools/rescale_canvas_fragments.py` then `tools/patch_canvas_fragments.py`. The patch moved exactly the 106 entries on those pages and nothing else. Backups: `directory-pipeline/output/_ocr_backups/b4affe50_pre_rescale_2026-10-20/`.
4. **Page 0078 had never gone through NER** (no entries cache, no error file). A non-forced `extract_entries.py --mode multimodal` re-ran only 0078 and 0056 (whose sidecar the rescale had made newer than its cache). NER returned 31 of 41 listings, dropping every one without a leading town name. The 10 were added by hand to the page's entries cache with their exact aligned lines, and carry `Fixed or checked` = TRUE in the master CSV. Cause: page 0077's cached `page_context` says HOLLY although its last entries are IDLEWILD, so 0078 started from the wrong town. That cache is still wrong; it only matters if 0078 is re-run.
5. **Drift scoring needs every edition.** `detect_geographic_drift.py` needs master columns (`volume_id`, `volume_year`, `name`), and its cross-volume check compares a business across editions. So `scripts/append_green_book_1958.py` runs in two phases: `stage` writes the 1958 rows in master format plus a copy of the master with them appended, the drift script scores that combined file, and `apply` takes only the 1958 rows' drift columns (after checking row order matches) before appending.

## Steps as run

```bash
# directory-pipeline
V=output/b4affe50-7ca3-013f-af86-0242ac110002
.venv/bin/python tools/rescale_canvas_fragments.py $V/ --aligned-model gemini-3.1-flash-lite
.venv/bin/python tools/patch_canvas_fragments.py $V/ --aligned-model gemini-3.1-flash-lite
.venv/bin/python pipeline/extract_entries.py $V --model gemini-3.1-flash-lite \
  --aligned-model gemini-3.1-flash-lite --mode multimodal --flex
# (hand-add of the 10 page-0078 listings, then rebuild the CSV from caches)
.venv/bin/python analysis/fix_entries.py $V/entries_gemini-3.1-flash-lite.csv --infer-categories

# green-books
python3 scripts/append_green_book_1958.py stage
# directory-pipeline
.venv/bin/python collections/greenbook/detect_geographic_drift.py \
  $V/drift_input_all_plus_1958.csv --aligned-dir $V --output $V/drift_output_all_plus_1958.csv
# green-books
python3 scripts/append_green_book_1958.py apply

# NYC
.venv/bin/python scripts/geocode_nyc_neighborhoods.py --geojson … --cache … --out …   # directory-pipeline
.venv/bin/python scripts/merge_nyc_geocode_csv.py --cache … --out …
python3 scripts/build_nyc_geo.py                                                       # green-books

# HF dataset + query DB
python3 hf-dataset/build.py
python3 scripts/build_query_db.py

# thumbnails
…/directory-pipeline/.venv/bin/python scripts/build_all_thumbs.py \
  --images-dir …/output/b4affe50-7ca3-013f-af86-0242ac110002 \
  --only-volume b4affe50-7ca3-013f-af86-0242ac110002 --format webp --jobs 7
python scripts/publish_thumbs.py --resume
```

## Mapping onto the master header

`business_name` → `name`, `section` → `category`, `is_advertiser` → `is_advertisement` (uppercased to `TRUE`/`FALSE`); `state` uppercased (nine rows came back title-case); `sub_region, phone, proprietor, amenities_services, rates, personnel, reference_number, is_recommended` empty; `flag_hallucinated` used only for the combine filter (0 rows dropped); `hand_added` → `Fixed or checked`.

## Copy and counts updated

- `explorer.html`: FIELD_META rebaked (24 years, category top-25, fill rates, cardinalities); 69,221 entries / 25 volumes; `GB_ENTRIES_TOTAL_APPROX`.
- `all-volumes.html`: 115,996 / 51 volumes in meta, hero, trends caveat, about modal; `MERGED_ENTRIES_TOTAL_APPROX`; hero categories 45 → 46 (YWCA crosses 100). States unchanged (no new state values).
- `nyc.html`: corpus prose (115,996 / 51); baked NYC stats 8,163 rows, publications 7 → 8 (stale since the Afro-American integration); progress total and its comment, which described the wrong recipe.
- `hf-dataset/README.md`, `hf-dataset-thumbs/README.md`: totals, Green Book row (25 editions), fold counts 761 → 464, rights math 50 of 51.
- README, CLAUDE.md, AGENTS.md, green-books-data skill, `build_query_db.py` docstring, `index.html` comment, `docs/mcp-server-plan.md`.

No change needed: `index.html` viewer code, `travel_guides_explorer.html`, `gb-categories.json`, `hf-dataset/build.py` (NYPL default rights row applies).

## Known leftovers

- NYPL's rights record for this volume also says "Right of Publicity Issues Present" (likenesses in photographs); copyright status is PDREN like the other editions. Not reflected in the dataset card.
- Two page-0078 boxes (BACKUS, BELMAR) cover only the town name, and eleven span both columns: the aligner merged the left-column town names with their first listing. They point at the right line but crop loosely.
- `directory-pipeline/scripts/fix_and_rebuild.sh` calls `pipeline/rescale_canvas_fragments.py` and `pipeline/patch_canvas_fragments.py`; both now live in `tools/`.
