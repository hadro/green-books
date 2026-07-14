# The Negro Motorist Green Book & Black Travel Guides — IIIF Viewer & Directory Explorer

This repository powers a public website for browsing and viewing the digitized editions of *The Negro Motorist Green Book* (1936–1966) and six other African American travel guides published between 1930 and 1962 — directories listing hotels, restaurants, beauty salons, and other businesses that served Black travelers during the Jim Crow era. The scanned volumes are held by the New York Public Library's Schomburg Center for Research in Black Culture and served as IIIF resources.

**Live site:** https://hadro.github.io/green-books/explorer (the Green Book) · https://hadro.github.io/green-books/all-volumes (search across all seven publications)

---

## What's here

| File / folder | Description |
|---|---|
| `index.html` | IIIF viewer (Clover) with routing logic — opens a specific page when given a `?cf=` deep-link |
| `explorer.html` | Interactive directory browser for *The Negro Motorist Green Book* — search and filter ~63,000 listings across all 23 editions |
| `all-volumes.html` | The same browser extended to all seven publications — ~105,700 listings across 45 volumes (1930–1966), with cross-publication charts and trends |
| `travel_guides_explorer.html` | Browser scoped to just the six non–Green Book travel guides |
| `old-explorer.html` | Archived earlier version of the explorer — kept as a historical reference, not linked from the live site |
| `green_book_entries_all.csv` | Structured dataset of the Green Book entries, extracted via OCR and AI from the digitized scans |
| `travel_guides_all.csv` | Structured dataset of the other six publications' entries |
| `gb-matching.js` | Shared address-signature resolver used to match the same business across editions and publications |
| `gb-categories.js` | Category folding — normalizes the guides' printed section headings into a consistent set of business categories |
| `gb-geo.js` | Geocoding helpers for placing entries on the OpenStreetMap embed |
| `image_to_volume.json`, `travel_guides_image_to_volume.json` | Lookup tables mapping NYPL image IDs to volume UUIDs, used by the viewer to route deep-links |
| `canvas_map.json`, `travel_guides_canvas_map.json` | Lookup tables mapping IIIF canvas IDs to image service URLs, used by the explorers for thumbnail generation |
| `manifests/` | IIIF Presentation 3 manifests for each digitized volume, patched to serve from this repository |
| `tests/` | End-to-end viewer tests (Playwright + local fake IIIF service) — see `tests/README.md` |
| `clover.umd-3.11.0.js` | Vendored, **unmodified** [Clover IIIF](https://github.com/samvera-labs/clover-iiif) viewer bundle — `@samvera/clover-iiif@3.11.0`, `dist/web-components/index.umd.js` from the [npm package](https://registry.npmjs.org/@samvera/clover-iiif/-/clover-iiif-3.11.0.tgz). Configured via the `options` attribute set in `index.html`; content-state deep-linking and HTTP→HTTPS URL rewriting for NYPL tile requests are handled entirely in `index.html`, no bundle patching needed. |

---

## How the site works

### Explorer (`explorer.html`)

A single-page browser that lazy-loads `green_book_entries_all.csv` after first paint. Features include:

- Full-text search across all fields
- Faceted filtering by edition year, city, state, and business category (with live counts)
- Detail panel with a thumbnail of the original scanned page and a link to the IIIF viewer
- "Also listed in" cross-referencing — shows other editions where the same business appears
- Cross-edition timeline — for businesses appearing in multiple editions, a dedicated view shows each appearance as a run card with scan thumbnails, year chips, and address-diff detection
- Jump-to-year navigation for quickly moving between editions
- OpenStreetMap embed for entries with geocodeable addresses
- CSV export of any filtered view
- Deep-linking via `?cf=` (entry detail) and `?tl=` (timeline view) URL parameters

`all-volumes.html` and `travel_guides_explorer.html` reuse the same interface over a wider dataset. `all-volumes.html` merges both CSVs to cover all seven publications, colors rows and filters by publication, and adds a "Charts & trends" view — listings per year, first-time vs. returning businesses, a state-by-year heatmap, and the changing category mix — computed across the whole corpus.

### Viewer (`index.html`)

A Clover IIIF viewer that accepts a `?cf=` query parameter containing a canvas fragment URL (e.g. from the `canvas_fragment` column of the CSV). It:

1. Extracts the NYPL image ID from the URL
2. Looks up the volume UUID in `image_to_volume.json`
3. Fetches the corresponding manifest from `manifests/<uuid>/manifest.json`
4. Navigates Clover to the correct page and bounding box region

Visiting the root URL without a `?cf=` parameter shows a landing page linking to the explorer.

---

## Data

The structured entries dataset was produced by the [directory-pipeline](https://github.com/hadro/directory-pipeline) project, which uses Gemini for OCR and named-entity recognition on the NYPL scans. The pipeline extracts business names, addresses, cities, states, categories, and notes from each page, and links each entry back to its source canvas via IIIF URIs.

*The Negro Motorist Green Book* editions alone number 23 volumes with roughly 63,000 listings. Together with six other digitized African American travel guides — *Hackley & Harrison's Hotel and Apartment Guide* (1930), *The Travelers' Guide* (1931), *Smith's Tourist Guide* (1940), *Travelguide* (1947–1962), *Go: Guide to Pleasant Motoring* (1952–1959), and the *NHA Directory and Guide to Travelers* (1959) — the full corpus spans 45 volumes across seven publications (1930–1966) and roughly 105,700 individual listings.

The data reaches only as far as digitization has: other Black travel guides that have not been digitized (see NYPL's guide, ["More African American Travel Guides!"](https://libguides.nypl.org/greenbook/more)) are not represented, so counts describe the digitized corpus, not the full historical record.

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
- IIIF viewer: [Clover IIIF](https://github.com/samvera-labs/clover-iiif) by Mat Jordan and Adam Arling
- Data extraction pipeline: [directory-pipeline](https://github.com/hadro/directory-pipeline)
- Claude Code for coding support, and Claude Design for design elements
