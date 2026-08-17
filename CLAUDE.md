# green-books

Published data and explorer UI for the digitized *Green Book* volumes (and related African American travel guides). Hosted on GitHub Pages at `hadro.github.io/green-books`. This repo is the front-end companion to `directory-pipeline`, which produces the CSVs and IIIF manifests consumed here.

## Key files

| File | What it is |
|------|-----------|
| `explorer.html` | Main Green Books explorer (faceted search table, ~1,600 lines of vanilla JS) |
| `green_book_entries_all.csv` | Combined data for all 24 Green Book editions (~67k entries; includes the LOC-digitized 1946 edition, volume_id 2016298176) |
| `image_to_volume.json` | Maps NYPL image IDs and LOC IIIF service IDs → volume IDs (used by IIIF viewer for deep links) |
| `travel_guides_image_to_volume.json` | Same, for the 26 sibling travel guide volumes (built and live; drives `travel_guides_explorer.html`) |
| `index.html` | IIIF viewer entry point — all JS is inline in this file, no build step (the `react_clover` branch has a separate Vite/Clover rewrite in `viewer-src/`, not yet merged) |
| `manifests/{uuid}/manifest.json` | Per-volume IIIF manifests (one per Green Book edition; the LOC 1946 volume's manifest lives at `manifests/2016298176/manifest.json`) |
| `green_book_entries_all_fixed.csv` | Scratch/working copy; `green_book_entries_all.csv` is the canonical one |
| `nyc_geo.json` | **Generated** — slim `sha1(canvas_fragment)[:12]` → `[lat, lon, neighborhood, borough, approx]` lookup for the 7,996 geocoded NYC entries. Rebuild with `python3 scripts/build_nyc_geo.py` whenever `nyc-neighborhoods/nyc_entries_geocoded.csv` changes; `--check` fails if it has drifted. |
| `nyc-neighborhoods/nyc-neighborhoods.slim.geojson` | **Generated** — the boundary polygons `nyc.html`'s map loads (261 top-level features, `name`+`borough` only, 5 dp; 239 KB gzipped vs the source's 409 KB). Rebuild with `python3 scripts/build_nyc_hoods.py`; `--check` fails if it has drifted. A *modified* CC BY-SA 4.0 redistribution — see `nyc-neighborhoods/README.md`. |

## Branch overview

| Branch | Status |
|--------|--------|
| `main` | Production. Has inference-patched CSV (11,972 category inferences; 0 U+FFFD chars). No category sidebar facet. |
| `new_facets` | Has category sidebar facet (`type: "facet"` in FIELD_META, top-20 checkboxes). Needs the updated CSV pulled from main before merging. |
| `react_clover` | React + `@samvera/clover-iiif@3.9.2` rewrite of the IIIF viewer. Image loading works; fragment zoom implemented but not yet browser-tested. |
| `sibling_viewer` | Stub predating `travel_guides_explorer.html`, which now ships on `main`; branch is obsolete. |
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

## Afro-American's Travel Guide volumes

Four NYPL volumes added to `travel_guides_all.csv`, bringing it to 26 travel-guide
volumes / 7 travel-guide publications (50 volumes / 8 publications corpus-wide).
Published by the Travel Bureau of the Afro-American newspapers, Baltimore. NYPL
collection UUID `52af6e40-7256-013f-1a2f-0242ac110002`.

| Year | Volume UUID | Rows |
|------|-------------|-----:|
| 1954 | `b5f95f60-7256-013f-3691-0242ac110002` | 1,287 |
| 1956 | `e36a5750-7256-013f-f2b2-0242ac110002` | 1,113 |
| 1957 | `fb4f57d0-7256-013f-8933-0242ac110003` | 1,127 |
| 1958 | `2a3699e0-7257-013f-019f-0242ac110003` | 1,137 |

4,664 rows appended in total. All four are NYPL PDREN / NoC-US public domain
(verified via the NYPL API). Explorer color `#713471` (deep plum) in
`all-volumes.html`/`nyc.html`, `#a83a68` (deep rose) in
`travel_guides_explorer.html`; short name "Afro-American".

- **Integration**: added via `scripts/append_afro_american.py`, mirroring
  `scripts/append_loc_1946.py` but for IIIF v3 manifests. It patches in real
  canvas dimensions from the pipeline's aligned sidecars, because the NYPL
  manifests for these volumes report a placeholder 2560×2560 for every canvas.

## Thumbnail CDN (all entries → Hugging Face)

Every entry's cropped snippet thumbnail (113,053 webps across both CSVs, incl. the
LOC 1946 volume and the four Afro-American's Travel Guide volumes) is pre-cropped and
served from the **`hadro/green-books-thumbnails`** HF dataset repo, so the explorers
make effectively zero live NYPL/LOC image requests.

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
    --images-dir /Users/joshhadro/github/directory-pipeline/output/afro-american-travel-guide-1954 \
    --images-dir /Users/joshhadro/github/directory-pipeline/output/afro-american-travel-guide-1956 \
    --images-dir /Users/joshhadro/github/directory-pipeline/output/afro-american-travel-guide-1957 \
    --images-dir /Users/joshhadro/github/directory-pipeline/output/afro-american-travel-guide-1958 \
    --format webp --jobs 7
  ```
  Local scans are joined by the CSV `image` column (an exact filename for both
  NYPL and LOC) — this is what pulls the LOC and Afro-American volumes in. `scripts/build_hero_thumbs.py`
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

## NYC coordinates (`nyc_geo.json`)

`nyc-neighborhoods/nyc_entries_geocoded.csv` is the NYC geocoding run's deliverable:
8,108 rows (re-run to include the 113 Afro-American's Travel Guide rows), 99.6%
resolved to real coordinates via NYC GeoSearch, with `neighborhood` and `borough`
labels. `nyc.html` streams that CSV as its entire dataset.

`all-volumes.html` only needs the coordinate, so it loads **`nyc_geo.json`** instead —
the same data at ~107 KB gzipped rather than 3.1 MB, keyed by the same
content-addressed id the thumbnail CDN uses (`sha1(canvas_fragment)[:12]`), so the
browser derives keys with the `sha1hex()` already inlined in each explorer. It is
fetched on idle after the CSVs land, never on the critical path.

Where a coordinate exists, the detail panel skips Nominatim entirely: no request, a
tighter map, and the neighborhood named. Rows the pipeline marked
`GEOMETRIC_CENTER`/`APPROXIMATE` or flagged for review are shown as block-level
approximations rather than pinpoints. Everywhere outside NYC still geocodes live.

**Licensing:** coordinates (NYC GeoSearch, public domain) and the point-in-polygon
`neighborhood`/`borough` labels are CC0-compatible. The CC BY-SA boundary geometry in
`nyc-neighborhoods/nyc-neighborhoods*.geojson` is deliberately **not** in `nyc_geo.json`
— only `nyc.html`'s map loads it, with attribution.

## NYC map (`nyc.html`, map view)

Two tiers, switched at zoom 14 (`GB_TIER_ZOOM`), both drawing from the same
`getFiltered()` set as the table:

- **Aggregate tier** (zoomed out) — the unit is the *neighborhood*, not a pixel
  radius. Every row already carries a `neighborhood` label, and those labels join
  exactly to the boundary file on `name` + normalized `borough` (name alone is
  not a key — six names repeat across boroughs). Two readings, toggled by
  `#map-mode` and serialized as `map=density` in the hash: **Bubbles** (a disc
  per neighborhood, area ∝ count, largest on top via `zIndexOffset`, radius
  scaled by zoom, names printed for the top 12 at z≥12) and **Density** (the
  polygons shaded on fixed manual breaks `[1,5,15,50,150,500]` using `HEAT_RAMP`,
  the same six-step ramp as the trends heatmap). Breaks are fixed, never derived
  from the filtered max — a scale that rescales under the reader is a scale that
  lies.
- **Point tier** (zoomed in) — one `circleMarker` per business inside
  `L.markerClusterGroup`, filled by publication, gold ring for 2+ guides, dashed
  stroke for a block-level geocode. markercluster stays because 7,645 of the
  7,965 geocoded rows share a coordinate with another row (one address carries
  78) and spiderfy is the only way to reach them — so `disableClusteringAtZoom`
  is deliberately unset.

Selecting exactly one neighborhood in the facet also forces the point tier.
Clicking a bubble or polygon flies to it and opens a popup offering
"Filter to <name>"; the click itself never applies the facet.

`MarkerCluster.Default.css` is deliberately **not** loaded — `gbClusterIcon()`
replaces the plugin's default `iconCreateFunction`, so its classes are dead.
`vendor/` stays a clean upstream copy; all Leaflet restyling is in the page's
own `<style>`.

`#map-wrap` carries `isolation: isolate`, and that is load-bearing: Leaflet
numbers its panes 400 and its controls 800/1000, and without a stacking context
there that ladder escapes into `#app`'s context (`#app` is `position: sticky`)
and out-ranks `#detail` (100 desktop / 300 mobile) — the map then paints over an
open detail panel. Its `detail-open` rule reserves room with a transparent
`border-right`, not `padding-right`: the map and all five `.map-chip` elements
are absolutely positioned, and those resolve their offsets against the *padding*
box, so padding reserved nothing.

The map auto-fits only on first render and when the neighborhood/borough facet
changes; every other filter leaves the viewport alone (it used to re-fit on
every keystroke). "⤴ Whole city" is the manual reset.

## Companion repo: directory-pipeline

Raw pipeline code at `/Users/joshhadro/github/directory-pipeline`. It produces the CSVs and manifests that feed this repo. After a pipeline run, copy `green_book_entries_all.csv` and `image_to_volume.json` here and commit.

## Pending work (as of 2026-05-15)

1. Browser-test the `react_clover` viewer zoom fix
2. Merge `new_facets` → `main` (category sidebar facet)
3. ~~Build sibling explorer for the travel guide volumes~~ — done: `travel_guides_explorer.html` is live on `main`, now covering 26 volumes / 7 publications
4. Add cross-links between Green Books explorer and sibling explorer
