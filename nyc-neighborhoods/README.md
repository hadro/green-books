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
| `nyc-neighborhoods.geojson` | Neighborhood boundary polygons — see license/attribution below |
| `nyc-neighborhoods.slim.geojson` | **Generated** — the trimmed boundaries `nyc.html`'s map loads (261 top-level features, 2 properties, 5 dp; 239 KB gzipped vs 409 KB). Rebuild with `python3 scripts/build_nyc_hoods.py`; `--check` fails if it has drifted. Same CC BY-SA 4.0 licence — see below. |
| `full_run.log` | Run log |

## Neighborhood boundaries — license & attribution

`nyc-neighborhoods.geojson` is redistributed from
[chriswhong/nyc-neighborhood-boundaries](https://github.com/chriswhong/nyc-neighborhood-boundaries)
(`dist/nyc-neighborhood-boundaries.geojson`), by Chris Whong, licensed
**[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)**. That dataset
is itself derived from the **Zillow Neighborhood Boundary Shapefile for New York
State** (last published Aug 2017), licensed CC BY-SA 3.0.

- `nyc-neighborhoods.geojson` is redistributed here **unmodified**, and remains
  the source of truth for the point-in-polygon run.
- `nyc-neighborhoods.slim.geojson` is a **modified** redistribution — an adapted
  work under CC BY-SA 4.0 §3(a)(1)(B), and so licensed CC BY-SA 4.0 in turn. It
  is what `nyc.html`'s map actually loads (239 KB gzipped rather than 409 KB, and
  the map now shades the polygons rather than just outlining them). Built by
  `scripts/build_nyc_hoods.py`, which is also the record of the modifications:
  - properties reduced to `name` and `borough`;
  - the 125 `kind: "sub-neighborhood"` features dropped, keeping the 261
    top-level ones (all 99 neighborhoods the entries resolve to are top-level,
    and the build fails if that ever stops being true);
  - coordinates rounded to 5 decimal places (~1.1 m).
- This project **builds upon** the boundaries: the `neighborhood` and `borough`
  columns in `nyc_entries_geocoded.csv` are assigned by point-in-polygon lookup
  against them.
- Neighborhood lines in NYC are unofficial, approximate, and disputed; treat the
  labels as one interpretation, not authoritative.

**ShareAlike / CC0 position:** both GeoJSON files remain CC BY-SA 4.0, attributed
above and in the map's attribution control, and are kept as standalone files —
they are **not merged into the published CC0 dataset**. The `neighborhood`/`borough` columns are the output of a
point-in-polygon *computation* (a factual label assigned to each coordinate), not
a reproduction or adaptation of the polygon geometry, and so are treated as
CC0-compatible facts. Rule of thumb: publish the neighborhood **labels**, never
the boundary **geometry**, in the CC0 dataset.
