# NYC neighborhood geocoding

Geocoded location + neighborhood assignment for the ~8,000 NYC-area entries
across all 7 publication titles (Green Book + 6 sibling guides), for a
neighborhood-keyed whole-NYC explorer view.

## ToS-clean provenance

**Every published coordinate comes from NYC GeoSearch** (NYC Planning Labs,
public domain — freely redistributable in the CC0 dataset). Google Geocoding is
used only as a *validator* and, for addresses GeoSearch can't parse
(intersections, corners, landmarks), as a *transient block-locator* whose point
is immediately reverse-geocoded back through GeoSearch. **No Google-derived
coordinate is stored or published.**

Pipeline: `directory-pipeline/scripts/geocode_nyc_neighborhoods.py`

1. Clean address + append borough context.
2. GeoSearch forward (open candidate) + Google forward (truth + QA tier).
3. Agree within 150 m → publish the GeoSearch coord. Else Google's point →
   GeoSearch reverse → publish that open coord. Else → manual queue.
4. Point-in-polygon vs the neighborhood boundaries → `neighborhood` + `borough`.

## Results (full run, 2026-07-20)

- **7,965 / 7,995 (99.6%)** resolved to an open coordinate + neighborhood.
- 76% GeoSearch-agree · 24% reverse-launder (median recovery 30 m) · 0.4% unresolved.
- **4.6% (371) flagged for review** via `review_reasons`: 199 borough-inferred
  (untagged "New York City" rows Google placed in an outer borough), 110
  APPROXIMATE tier, 40 area-descriptions, 30 unresolved, 15 ambiguous-anchor, 7
  far reverse-launder.
- Top neighborhoods: Harlem 2,915 · Midtown West 858 · Hamilton Heights 743 ·
  Bedford-Stuyvesant 659 · Midtown East 373 · Morrisania 306 · Washington Hts 304.
  "Greater Harlem" (Harlem + Hamilton Hts + East Harlem + Manhattanville +
  Morningside Hts) = 3,896. By borough: Manhattan 6,235 · Brooklyn 1,052 ·
  Bronx 570 · Queens 71 · Staten Island 37.
- Cost: 2,661 Google calls (address dedup); under the 10k/month free cap → $0.

## Files

| File | What it is |
|------|-----------|
| `nyc_entries_geocoded.csv` | **The deliverable** — 7,995 NYC entries: core columns + `neighborhood`/`borough`/`latitude`/`longitude`/`geocode_source`/`geocode_quality`/`review_flag`/`review_reasons`. Built by `directory-pipeline/scripts/merge_nyc_geocode_csv.py` (reads the cache, no API calls). |
| `nyc_full_results.json` | Full ~8k output: per-entry coord, neighborhood, source, QA tier, review flags |
| `nyc_geocode_cache.json` | API result cache keyed by query — makes re-runs free; keep this |
| `nyc_sample_results.json` | The 250-row validation sample |
| `nyc-neighborhoods.geojson` | Neighborhood boundary polygons (chriswhong/nyc-neighborhood-boundaries, Pediacities-derived) |
| `full_run.log` | Run log |
