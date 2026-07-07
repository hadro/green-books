# The Negro Motorist Green Book — IIIF Viewer & Directory Explorer

This repository powers a public website for browsing and viewing the digitized editions of *The Negro Motorist Green Book* (1936–1966), a travel guide listing hotels, restaurants, beauty salons, and other businesses that served Black travelers during the Jim Crow era. The volumes were digitized by New York Public Library and are available as IIIF resources.

**Live site:** https://hadro.github.io/green-books/explorer

---

## What's here

| File / folder | Description |
|---|---|
| `index.html` | IIIF viewer (Clover) with routing logic — opens a specific page when given a `?cf=` deep-link |
| `explorer.html` | Interactive directory browser — search and filter ~63,000 business listings across all 23 editions |
| `green_book_entries_all.csv` | Combined structured dataset of all entries, extracted via OCR and AI from the digitized scans |
| `image_to_volume.json` | Lookup table mapping NYPL image IDs to volume UUIDs, used by the viewer to route deep-links |
| `canvas_map.json` | Lookup table mapping IIIF canvas IDs to image service URLs, used by the explorer for thumbnail generation |
| `manifests/` | IIIF Presentation 3 manifests for each of the 23 volumes, patched to serve from this repository |
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

The 23 volumes span 1936–1966 and contain approximately 63,000 individual listings.

---

## Traffic

Public traffic dashboard: https://green-books.goatcounter.com (via [GoatCounter](https://www.goatcounter.com/), privacy-friendly and cookieless)

---

## Credits

- Digitized volumes: [New York Public Library Digital Collections](https://digitalcollections.nypl.org/)
- IIIF viewer: [Clover IIIF](https://github.com/samvera-labs/clover-iiif) by Mat Jordan and Adam Arling
- Data extraction pipeline: [directory-pipeline](https://github.com/hadro/directory-pipeline)
- Claude Code for coding support, and Claude Design for design elements
