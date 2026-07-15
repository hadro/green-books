# Internet Archive as a secondary IIIF image source — research notes

Date: 2026-07-15. Read-only research, no uploads performed. Question: could
`iiif.archive.org` serve as a secondary/fallback image source for the ~46
Green Book / sibling travel guide volumes currently served from
`iiif.nypl.org`?

## 1. Green Book editions found on archive.org

Searched via `advancedsearch.php` (title queries for "green book" / "negro
motorist" / "negro travelers", cross-checked with `mediatype:texts`) and
pulled `/metadata/<id>` for the plausible book scans.

| Identifier | Claimed year | Scan source / provenance | Quality |
|---|---|---|---|
| `history_green_book` | 1949 | Uploaded by `brewster@archive.org` (2015), sourced from U. Michigan AutoLife project / Boston Public Library | **1 page only** — cover/title page scan, not a full volume |
| `TheNegroMotoristGreenBook194026` | 1940 | Uploaded by a private user (2019), CC BY-NC-ND 4.0 | 50 JPEG pages, JP2 zip present — looks like a real full scan, but license is **non-commercial/no-derivatives**, not CC0 |
| `NegroMotoristGreenBook1938D.D.TeoliJr.A.C.` | 1938 | Explicitly sourced "from NYPL / Green Bag collection", curated by D.D. Teoli Jr., CC BY-NC-ND 4.0 | Re-upload of an NYPL-derived PDF, not an independent scan |
| `download-the-negro-motorist-green-book-1938-facsimile-edition` | 1938 | Uploaded 2024 by an unrelated personal account, thin metadata, "facsimile edition" | Looks like a legitimate OCR scan but unclear provenance; likely another re-upload/repackaging |

No hits for any other Green Book years (1937, 1941–1948, 1950s, 1960s
editions). Everything else the search API returned was noise: documentaries,
news clips, exhibit interviews, the picture book "Ruth and the Green Book,"
Wikipedia snapshots, etc.

**Bottom line on coverage:** of the ~25 Green Book editions in the NYPL/site
corpus, at most **2–3 years (1938, 1938 again, 1940, partial 1949)** have any
presence on IA, and none are IA's own institutional scans — they're all
individual re-uploads of NYPL- or other-library-sourced material, with
inconsistent (and non-CC0) licensing. This is a large gap versus the ~46
volumes the site needs.

## 2. Sibling travel guides on IA

Searched for Hackley & Harrison's Hotel and Apartment Guide, Travelguide,
The Travelers' Guide, *Go: Guide to Pleasant Motoring*, Smith's Tourist
Guide, and N.H.A. Directory and Guide to Travelers.

- **One partial hit:** `nby_813416` — "Go: Guide to Pleasant Motoring" (1959)
  — plausibly the right title, worth a follow-up metadata check to confirm
  it's the same publication.
- Everything else returned only false positives (law firm dockets,
  yearbooks, unrelated "traveler's guide" titles, "Hackley School" alumni
  materials). No sign of Hackley & Harrison's guide, *Travelguide*, *The
  Travelers' Guide*, Smith's Tourist Guide, or the N.H.A. Directory anywhere
  on IA.

**Bottom line:** the sibling guides are effectively **absent from IA.**

## 3. How `iiif.archive.org` works today

- Manifest: `https://iiif.archive.org/iiif/<identifier>/manifest.json`
  (IIIF Presentation API **v3**, confirmed live — `history_green_book`
  returned a valid v3 manifest with `@context:
  http://iiif.io/api/presentation/3/context.json`).
- Collections: `https://iiif.archive.org/iiif/<identifier>/collection.json`
- Legacy v2 manifest: `https://iiif.archive.org/iiif/2/<identifier>/manifest.json`
- Image API: `https://iiif.archive.org/iiif/<identifier>/info.json`, and a
  distinct full-image convenience route
  `https://iiif.archive.org/image/iiif/<identifier>+<filename>/full/max/0/default.jpg`
- IA's own docs (iiif.archive.org/iiif/documentation) say the service was
  "officially upgraded and adopted" in **September 2023**, is called
  "stable" but is still described as under active development. No documented
  rate limit was found in IA's own docs; a third-party IIIF ecosystem page
  cited **2,000 requests/hour unauthenticated** for the older v1 alpha —
  treat as indicative, not authoritative for the current v3 service.
- **Reliability observed in this research session:** the small, one-page
  `history_green_book` manifest returned successfully, but the same request
  against `TheNegroMotoristGreenBook194026` (a real 50-page scan) **timed
  out twice** (60s). That's a small sample, but it's consistent with IA's
  IIIF layer being noticeably slower/less predictable than NYPL's for larger
  items — the opposite of what you'd want in a "reduce load / improve
  reliability" fallback.
- Page/leaf addressing is not `$<page>` (that was this task's working
  assumption going in) — IA addresses images by `identifier+filename` or by
  manifest-driven canvas IDs, not a simple numeric fragment. Any integration
  would need to walk the manifest to resolve canvas → image-service IDs
  rather than constructing URLs from a page number directly.

## 4. Rights / provenance considerations

- The Green Books themselves are public domain; NYPL's own scans are
  released CC0 under NYPL Digital Collections policy — this is what the
  green-books site currently relies on.
- Every Green Book item found on IA is either an **individual re-upload**
  (not an IA/institutional scan) or explicitly licensed **CC BY-NC-ND
  4.0** — non-commercial, no-derivatives. That license is incompatible with
  treating IA copies as an equivalent free/open substitute for the NYPL CC0
  originals; at minimum it would require attribution and would forbid any
  derivative processing (e.g., the site's own thumbnail generation) if taken
  literally.
- Even setting licensing aside, **canvas/page numbering will not line up.**
  The site's data model keys every entry to an NYPL image ID plus an
  `xywh=` box expressed in NYPL's canvas coordinate space (see
  `image_to_volume.json` / per-volume `manifests/{uuid}/manifest.json` in
  this repo). An IA scan of the "same" volume is a different digitization
  with its own page count, trimming, and canvas ordering — none of the
  existing bounding boxes would transfer. Using IA as a source would require
  **manual re-alignment per volume** (matching printed page → IA leaf →
  re-deriving xywh boxes), not a drop-in URL swap.

## 5. Bottom line / recommendation

| Use case | Viable? | Why | Rough effort |
|---|---|---|---|
| (a) Hero-thumbnail source | N/A | Already solved locally (no need for IA) | — |
| (b) Full tile-viewer mirror (replace/fallback for iiif.nypl.org tiles) | **No** | IA only has ~2–3 of ~46 volumes, non-CC0 licensing on the ones it does have, no NYPL canvas/xywh alignment, and observed timeouts on real multi-page items | High (per-volume re-alignment) for a small fraction of coverage — not worth it |
| (c) Bulk-thumbnail source for table/hover features | **Not now** | Same coverage gap (only 1938/1940/1949-partial exist) and licensing caveats; NYPL already provides thumbnails without apparent load issues | Low effort *if* NYPL ever becomes unreliable, but low value today given coverage |

**Recommendation:** Do not pursue IA as a secondary IIIF source at this
time. Coverage is far too sparse (a handful of re-uploaded editions out of
~46 volumes, no sibling guides at all), licensing on the extant items is
non-CC0, canvas numbering doesn't map to the site's existing NYPL-keyed
bounding-box data, and IA's IIIF service showed timeouts on a real
multi-page item during this research. If NYPL load ever becomes a real
problem, a better mitigation is likely a caching/CDN layer in front of
`iiif.nypl.org` rather than a partial, license-encumbered IA mirror. Revisit
only if IA (or a partner institution) does a proper CC0 mass-digitization of
the full Green Book run.
