# green-books

Published data and explorer UI for the digitized *Green Book* volumes (and related African American travel guides). Hosted on GitHub Pages at `hadro.github.io/green-books`. This repo is the front-end companion to `directory-pipeline`, which produces the CSVs and IIIF manifests consumed here.

## Key files

| File | What it is |
|------|-----------|
| `explorer.html` | Main Green Books explorer (faceted search table, ~1,600 lines of vanilla JS) |
| `green_book_entries_all.csv` | Combined data for all 24 Green Book editions (~67k entries; includes the LOC-digitized 1946 edition, volume_id 2016298176) |
| `image_to_volume.json` | Maps NYPL image IDs and LOC IIIF service IDs → volume IDs (used by IIIF viewer for deep links) |
| `travel_guides_image_to_volume.json` | Same, for the 22 sibling travel guide volumes (not yet built) |
| `index.html` | IIIF viewer entry point — all JS is inline in this file, no build step (the `react_clover` branch has a separate Vite/Clover rewrite in `viewer-src/`, not yet merged) |
| `manifests/{uuid}/manifest.json` | Per-volume IIIF manifests (one per Green Book edition; the LOC 1946 volume's manifest lives at `manifests/2016298176/manifest.json`) |
| `green_book_entries_all_fixed.csv` | Scratch/working copy; `green_book_entries_all.csv` is the canonical one |

## Branch overview

| Branch | Status |
|--------|--------|
| `main` | Production. Has inference-patched CSV (11,972 category inferences; 0 U+FFFD chars). No category sidebar facet. |
| `new_facets` | Has category sidebar facet (`type: "facet"` in FIELD_META, top-20 checkboxes). Needs the updated CSV pulled from main before merging. |
| `react_clover` | React + `@samvera/clover-iiif@3.9.2` rewrite of the IIIF viewer. Image loading works; fragment zoom implemented but not yet browser-tested. |
| `sibling_viewer` | Stub for the 22 travel guide volumes explorer (not yet started). |
| `holistic_viewer` | Earlier viewer experiment; ignore. |

## Explorer architecture (`explorer.html`)

Single self-contained HTML file — no build step. All JS is inline vanilla. Key globals:

- `GB_CSV_URL` — path to the CSV fetched on load
- `FIELD_META` — JSON blob (inlined, ~line 710) describing every column: `type` (`"facet"`, `"search"`, `"id"`), `top_values` (for facets), cardinality, fill rate. **Facet `top_values` are hard-coded at build time** — recompute from the CSV when the data changes.
- `FIELD_LABELS` — human-readable column labels
- `facetFields` — derived from FIELD_META; drives the left sidebar checkboxes
- `displayFields` — drives the table columns

To add a new facet field: change its `type` from `"search"` to `"facet"` in FIELD_META and add a `top_values` array computed from the CSV.

## Category facet (current state)

The `category` field has two implementations depending on branch:
- **`main`**: `type: "search"` — a text filter, no sidebar checkboxes
- **`new_facets`**: `type: "facet"` — sidebar with top-20 category checkboxes

Top-20 categories after inference patch (use these counts for `top_values` when updating):

```
HOTELS 14527, TOURIST HOMES 11382, RESTAURANTS 7797, TAVERNS 5328,
BEAUTY PARLORS 4402, SERVICE STATIONS 2174, BARBER SHOPS 2130, NIGHT CLUBS 1756,
"Hotels - Motels - Tourist Homes - Restaurants" 1523, TAILOR SHOPS 1213,
DRUG STORES 1176, WINE & LIQUOR STORES 1142, VACATION RESORTS 1128,
GARAGES 904, General 581, TAXI CABS 516, SUMMER RESORTS 418,
ROAD HOUSES 266, VACATION SECTION 242, BEAUTY CULTURE SCHOOLS 233
```

**To finish merging new_facets → main:**
```bash
git checkout new_facets
git checkout main -- green_book_entries_all.csv
git commit -m "Pull updated CSV from main"
# review in browser, then:
git checkout main && git merge new_facets
```

## IIIF viewer (`index.html`)

The production viewer is entirely inline in `index.html` (no build step). It accepts a `?cf=<canvas_fragment_url>` query parameter encoding which IIIF image and region to show. The viewer looks up the image ID (or LOC service ID) in `image_to_volume.json` → fetches the manifest → builds an IIIF content state → passes it to Clover.

**How the viewer works:** For NYPL volumes, the canvas fragment URL encodes the NYPL image ID; the viewer extracts it, looks up the volume in `image_to_volume.json`, and fetches `manifests/<uuid>/manifest.json`. For the LOC 1946 volume, the fragment encodes the LOC IIIF service ID; the lookup resolves to volume_id 2016298176 and fetches `manifests/2016298176/manifest.json`.

**Known issue:** NYPL `info.json` responses return `"id": "http://iiif.nypl.org:443/..."` (HTTP + port 443), which breaks OSD tile construction. This is fixed by a `window.fetch` monkey-patch inline in `index.html` that rewrites the URL before OSD sees it.

**react_clover branch status:** A React rewrite with `@samvera/clover-iiif@3.9.2` exists in the `react_clover` branch. Image loading and canvas navigation work; fragment zoom is implemented (via `customDisplays` + `viewport.fitBounds`) but needs browser testing. No entry highlight overlay yet.

## LOC 1946 volume

The first non-NYPL volume in the collection. Key details:
- **volume_id**: the LOC item id `2016298176` (not a UUID)
- **canvas_fragment/image URLs**: use `https://tile.loc.gov/image-services/iiif/service:gdc:...` service IDs
- **Local manifest**: committed at `manifests/2016298176/manifest.json`
- **Integration**: added via `scripts/append_loc_1946.py`; full plan at `docs/loc-1946-integration-plan.md`

## Thumbnail CDN (all entries → Hugging Face)

Every entry's cropped snippet thumbnail (all 109,163 across both CSVs, incl. the
LOC 1946 volume) is pre-cropped and served from the **`hadro/green-books-thumbnails`**
HF dataset repo, so the explorers make effectively zero live NYPL/LOC image requests.

- **Filename is content-addressed**: `sha1(canvas_fragment)[:12]`, sharded by the
  first two hex chars → repo path `<tid[:2]>/<tid>.webp`. Front-end URL base is
  `https://huggingface.co/datasets/hadro/green-books-thumbnails/resolve/main`.
- **No per-entry manifest**: the explorers compute the URL in-browser via a
  synchronous `sha1hex()` (`thumbKey(cf)` in each of `all-volumes.html`,
  `explorer.html`, `nyc.html`, `travel_guides_explorer.html`). Must stay
  byte-identical to Python `hashlib.sha1`. `thumbUrl()` returns the CDN URL;
  `liveIiifUrl()` + `attachThumb()`'s `onerror` fall back to a live IIIF crop for
  any CDN miss.
- **Build** (crops from LOCAL page scans, no NYPL/LOC fetches; WebP q75, 400px,
  ~4.2 KB avg, ~450 MB total; resumable, ~18 min on 7 cores):
  ```bash
  /Users/joshhadro/github/directory-pipeline/.venv/bin/python scripts/build_all_thumbs.py \
    --images-dir /Users/joshhadro/github/directory-pipeline/output/green_books_and_related \
    --images-dir /Users/joshhadro/github/directory-pipeline/output/the_negro_motorist_green_book_2016298176/2016298176 \
    --format webp --jobs 7
  ```
  Local scans are joined by the CSV `image` column (an exact filename for both
  NYPL and LOC) — this is what pulls the LOC volume in. `scripts/build_hero_thumbs.py`
  (the curated ~300-thumb featured pool) is unchanged and still shares its crop
  primitives (`crop_box`, `thumb_id`, etc.) with the full builder.
- **Publish**: `python scripts/publish_thumbs.py` (needs HF write auth). The `thumbs/`
  tree is gitignored — HF is the sole host, never GitHub Pages. **Do NOT use
  `upload_large_folder`/Xet** — its Xet backend hangs on the 100k-file folder, and
  per-file LFS uploads blow HF's 3000-req/5-min API quota. The script instead commits a
  `.gitattributes` that keeps `*.webp` out of LFS (so each 4 KB file is inlined into the
  commit, ~2 API calls per commit) and uploads one commit per 2-hex shard (256 commits).
  `--reset` gives a clean slate; `--resume` skips shards already present. The dataset
  card is tracked at `hf-dataset-thumbs/README.md` and uploaded as the repo README.
- The `hero-thumbs/` committed pool + `manifest.json` still exist, but only to
  *select* which entries are featured on the hero — the images themselves now
  come from the CDN.

## Companion repo: directory-pipeline

Raw pipeline code at `/Users/joshhadro/github/directory-pipeline`. It produces the CSVs and manifests that feed this repo. After a pipeline run, copy `green_book_entries_all.csv` and `image_to_volume.json` here and commit.

## Pending work (as of 2026-05-15)

1. Browser-test the `react_clover` viewer zoom fix
2. Merge `new_facets` → `main` (category sidebar facet)
3. Build sibling explorer for 22 travel guide volumes (full plan: `directory-pipeline/docs/sibling-explorer-plan.md`)
4. Add cross-links between Green Books explorer and future sibling explorer
