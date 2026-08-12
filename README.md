# The Negro Motorist Green Book & Black Travel Guides — IIIF Viewer & Directory Explorer

This repository powers a public website for browsing and viewing the digitized editions of *The Negro Motorist Green Book* (1936–1966) and six other African American travel guides published between 1930 and 1962 — directories listing hotels, restaurants, beauty salons, and other businesses that served Black travelers during the Jim Crow era. The scanned volumes are held by the New York Public Library's Schomburg Center for Research in Black Culture and served as IIIF resources, with the 1946 edition digitized by the Library of Congress.

## 👉 Start here: **https://hadro.github.io/green-books/all-volumes**

The all-volumes explorer is the main entry point to the project — search, filter, and chart all ~109,200 listings across all 46 volumes and seven publications in one place. If you are linking to this project, link there.

The other explorers are narrower views of the same corpus and remain available:

- [/explorer](https://hadro.github.io/green-books/explorer) — *The Negro Motorist Green Book* only (24 editions, ~67,000 listings)
- [/travel_guides_explorer](https://hadro.github.io/green-books/travel_guides_explorer) — the six non–Green Book travel guides
- [/nyc](https://hadro.github.io/green-books/nyc) — the New York City listings, mapped by neighborhood

---

## What's here

| File / folder | Description |
|---|---|
| `all-volumes.html` | **The primary explorer** — search and filter all ~109,200 listings across 46 volumes and seven publications (1930–1966), with cross-publication charts and trends |
| `explorer.html` | The same browser scoped to *The Negro Motorist Green Book* — ~67,000 listings across its 24 editions |
| `travel_guides_explorer.html` | Browser scoped to just the six non–Green Book travel guides |
| `nyc.html` | New York City listings on a neighborhood map — aggregate and point views over the geocoded NYC subset |
| `index.html` | IIIF viewer (Clover) with routing logic — opens a specific page when given a `?cf=` deep-link. **The only part of the site that contacts the NYPL or LOC image servers.** |
| `old-explorer.html` | Archived earlier version of the explorer — kept as a historical reference, not linked from the live site |
| `green_book_entries_all.csv` | Structured dataset of the Green Book entries, extracted via OCR and AI from the digitized scans |
| `travel_guides_all.csv` | Structured dataset of the other six publications' entries |
| `gb-matching.js` | Shared address-signature resolver used to match the same business across editions and publications |
| `gb-categories.js` | Category folding — normalizes the guides' printed section headings into a consistent set of business categories |
| `gb-geo.js` | Geocoding helpers for placing entries on the OpenStreetMap embed |
| `image_to_volume.json`, `travel_guides_image_to_volume.json` | Lookup tables mapping NYPL image IDs and LOC IIIF service IDs to volume IDs, used by the viewer to route deep-links |
| `canvas_map.json`, `travel_guides_canvas_map.json` | Lookup tables mapping IIIF canvas IDs to image service URLs — used to construct viewer deep-links and, only on a CDN miss, a fallback live image crop |
| `nyc_geo.json` | Pre-computed coordinates and neighborhood labels for the ~7,900 geocoded New York City entries, so those never need a live geocoding request |
| `manifests/` | IIIF Presentation 3 manifests for each digitized volume, patched to serve from this repository |
| `tests/` | End-to-end viewer tests (Playwright + local fake IIIF service) — see `tests/README.md` |
| `clover.umd-3.11.0.js` | Vendored, **unmodified** [Clover IIIF](https://github.com/samvera-labs/clover-iiif) viewer bundle — `@samvera/clover-iiif@3.11.0`, `dist/web-components/index.umd.js` from the [npm package](https://registry.npmjs.org/@samvera/clover-iiif/-/clover-iiif-3.11.0.tgz). Configured via the `options` attribute set in `index.html`; content-state deep-linking and HTTP→HTTPS URL rewriting for NYPL tile requests are handled entirely in `index.html`, no bundle patching needed. |

---

## How the site works

### Explorer (`all-volumes.html`)

A single-page browser that streams `green_book_entries_all.csv` and `travel_guides_all.csv` after first paint, merging both into one searchable corpus. Features include:

- Full-text search across all fields
- Faceted filtering by edition year, city, state, and business category (with live counts)
- Detail panel with a cropped snippet of the listing as it appears on the original scanned page (served from Hugging Face — see below) and a link to open that page in the IIIF viewer
- "Also listed in" cross-referencing — shows other editions where the same business appears
- Cross-edition timeline — for businesses appearing in multiple editions, a dedicated view shows each appearance as a run card with scan thumbnails, year chips, and address-diff detection
- Jump-to-year navigation for quickly moving between editions
- OpenStreetMap embed for entries with geocodeable addresses
- CSV export of any filtered view
- Deep-linking via `?cf=` (entry detail) and `?tl=` (timeline view) URL parameters

On top of that shared interface, `all-volumes.html` colors rows and filters by publication and adds a "Charts & trends" view — listings per year, first-time vs. returning businesses, a state-by-year heatmap, and the changing category mix — computed across the whole corpus.

`explorer.html` and `travel_guides_explorer.html` run the same code over a single publication's slice of the data; `nyc.html` reuses it over the geocoded New York City subset and adds a Leaflet neighborhood map.

### Viewer (`index.html`)

A Clover IIIF viewer that accepts a `?cf=` query parameter containing a canvas fragment URL (e.g. from the `canvas_fragment` column of the CSV). It:

1. Extracts the NYPL image ID (or LOC IIIF service ID) from the URL
2. Looks up the volume ID in `image_to_volume.json`
3. Fetches the corresponding manifest from `manifests/<id>/manifest.json`
4. Navigates Clover to the correct page and bounding box region

Visiting the root URL without a `?cf=` parameter shows a landing page linking to the all-volumes explorer.

---

## Where the data comes from (and what the site does *not* request)

The explorers are deliberately built so that **browsing the site places no load on the libraries' image servers.** Everything an explorer needs comes from two places:

1. **The CSVs in this repository**, served as static files from GitHub Pages and streamed into the browser after first paint. All text — business names, addresses, cities, categories, years — is read from these. There is no API and no database behind the site.
2. **Cropped snippet thumbnails from Hugging Face.** Every entry's thumbnail is pre-cropped and served from the [`hadro/green-books-thumbnails`](https://huggingface.co/datasets/hadro/green-books-thumbnails) dataset repo. Filenames are content-addressed (`sha1(canvas_fragment)[:12]`), so the browser derives each URL locally — there is no per-entry manifest to fetch.

**The NYPL and Library of Congress IIIF servers are contacted only when a reader explicitly opens a page in the IIIF viewer** (`index.html`, via an entry's "View page" / `?cf=` deep-link). That is a deliberate, per-click action: tiles are fetched then, for that one volume, and not before. Scrolling, searching, faceting, charting, and viewing entry detail panels in any explorer trigger zero requests to either institution.

Two narrow exceptions, both fallbacks rather than normal operation:

- If a thumbnail is missing from the Hugging Face CDN, the page falls back to a live IIIF crop for that single image (`liveIiifUrl()`).
- Entries outside New York City geocode their address through OpenStreetMap's Nominatim when their detail panel is opened, cached in the browser afterward. NYC entries skip this entirely — their coordinates are pre-computed in `nyc_geo.json`.

---

## Data

The structured entries dataset was produced by the [directory-pipeline](https://github.com/hadro/directory-pipeline) project, which uses Gemini for OCR and named-entity recognition on the NYPL scans. The pipeline extracts business names, addresses, cities, states, categories, and notes from each page, and links each entry back to its source canvas via IIIF URIs.

*The Negro Motorist Green Book* editions alone number 24 volumes with roughly 67,000 listings. Together with six other digitized African American travel guides — *Hackley & Harrison's Hotel and Apartment Guide* (1930), *The Travelers' Guide* (1931), *Smith's Tourist Guide* (1940), *Travelguide* (1947–1962), *Go: Guide to Pleasant Motoring* (1952–1959), and the *NHA Directory and Guide to Travelers* (1959) — the full corpus spans 46 volumes across seven publications (1930–1966) and roughly 109,200 individual listings.

The data reaches only as far as digitization has: other Black travel guides that have not been digitized (see NYPL's guide, ["More African American Travel Guides!"](https://libguides.nypl.org/greenbook/more)) are not represented, so counts describe the digitized corpus, not the full historical record.

The full structured dataset — all seven publications combined — is also published as a downloadable, CC0-licensed dataset on Hugging Face: [hadro/green-books-travel-guides](https://huggingface.co/datasets/hadro/green-books-travel-guides). The matching cropped snippet images for every entry are published alongside it as [hadro/green-books-thumbnails](https://huggingface.co/datasets/hadro/green-books-thumbnails), which is also what the live explorers load their thumbnails from.

---

## Running the viewer tests

End-to-end tests for the viewer's deep-link/zoom flow live in `tests/`
(Playwright + a local fake IIIF image service — no network access to NYPL
needed). See `tests/README.md` for details and environment overrides.

```sh
cd tests
npm install
npx playwright install --with-deps chromium
./run.sh
```

CI runs the same suite via `.github/workflows/viewer-tests.yml` on any change
to `index.html`, the vendored Clover bundle, or `tests/**`.

---

## Traffic

Public traffic dashboard: https://green-books.goatcounter.com (via [GoatCounter](https://www.goatcounter.com/), privacy-friendly and cookieless)

---

## Credits

- Digitized volumes: [New York Public Library Digital Collections](https://digitalcollections.nypl.org/)
- The Negro Motorist Green Book (1946): [Library of Congress](https://www.loc.gov/item/2016298176/)
- IIIF viewer: [Clover IIIF](https://github.com/samvera-labs/clover-iiif) by Mat Jordan and Adam Arling
- Data extraction pipeline: [directory-pipeline](https://github.com/hadro/directory-pipeline)
- Claude Code for coding support, and Claude Design for design elements
