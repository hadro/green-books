#!/usr/bin/env python3
"""Build nyc-neighborhoods/nyc-neighborhoods.slim.geojson — the map's boundary layer.

`nyc-neighborhoods/nyc-neighborhoods.geojson` is the upstream boundary file:
386 features, 1.49 MB raw / ~419 KB gzipped, carrying a human-written `summary`
paragraph per neighborhood plus wikipedia/subreddit/related-content links. When
those boundaries were a decorative hairline underlay that weight didn't matter
much. `nyc.html`'s map now aggregates by neighborhood and shades the polygons by
listing count, so the file is on the critical path for the map view and every
byte of prose in it is dead weight.

This drops everything the page doesn't read:

  * properties → `name`, `borough` only,
  * features → the 261 `kind == "neighborhood"` polygons. All 99 neighborhoods
    the entries resolve to are top-level, so the 125 sub-neighborhoods are dead
    weight — and worse, filling one would double-composite the choropleth inside
    its parent. The script asserts this rather than assuming it.
  * coordinates → 5 decimal places, ~1.1 m, far under the boundaries' own
    uncertainty (nyc-neighborhoods/README.md calls them "unofficial, approximate
    and disputed"). Not 4 dp: that is ~11 m, which is a visible stair-step on a
    boundary line at the z16–17 the pin tier reaches routinely.

Result: ~244 KB gzipped, a 40% cut. The full file stays in the repo as the
source of truth for the geocoding pipeline.

Licensing: the boundary geometry is CC BY-SA 4.0 from
chriswhong/nyc-neighborhood-boundaries — see nyc-neighborhoods/README.md. This
file is a derivative and carries the same licence; `nyc.html` credits it in the
map's attribution control. Note the constraint from CLAUDE.md holds unchanged:
this geometry stays out of nyc_geo.json, and only nyc.html loads it.

Usage:
    python3 scripts/build_nyc_hoods.py [--check]

--check verifies the committed slim file matches the source and exits non-zero
if it has drifted, without writing anything.
"""

import argparse
import csv
import gzip
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "nyc-neighborhoods" / "nyc-neighborhoods.geojson"
ENTRIES = ROOT / "nyc-neighborhoods" / "nyc_entries_geocoded.csv"
OUT = ROOT / "nyc-neighborhoods" / "nyc-neighborhoods.slim.geojson"

KEEP_PROPS = ("name", "borough")
PRECISION = 5


def norm_borough(s):
    """`Staten Island` (CSV) and `staten-island` (GeoJSON) onto one key.

    Six GeoJSON names repeat across boroughs (Chinatown, Sunnyside, Bay Terrace,
    Koreatown, Murray Hill, Warnerville), so name alone is not a key. Do not
    reach for `properties.slug` instead: ten of them disagree with name+borough
    (`Mariner's Harbor` → `mariners-harbor`, `Little India` → `curry-hill-manhattan`).
    """
    return (s or "").strip().lower().replace(" ", "-")


def used_neighborhoods():
    """(name, borough) pairs the geocoded entries actually resolved to."""
    csv.field_size_limit(10 ** 7)
    used = set()
    with ENTRIES.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            name = (row.get("neighborhood") or "").strip()
            if name:
                used.add((name, norm_borough(row.get("borough"))))
    return used


def round_coords(coords):
    """Recursively round a GeoJSON coordinate tree to PRECISION decimals."""
    if coords and isinstance(coords[0], (int, float)):
        return [round(coords[0], PRECISION), round(coords[1], PRECISION)]
    return [round_coords(c) for c in coords]


def build():
    geo = json.loads(SRC.read_text(encoding="utf-8"))
    used = used_neighborhoods()

    features = []
    for feat in geo["features"]:
        props = feat["properties"]
        if props.get("kind") != "neighborhood":
            continue
        features.append({
            "type": "Feature",
            "properties": {k: props[k] for k in KEEP_PROPS if k in props},
            "geometry": {
                "type": feat["geometry"]["type"],
                "coordinates": round_coords(feat["geometry"]["coordinates"]),
            },
        })

    # A neighborhood the entries use but no kept polygon covers would silently
    # lose its choropleth shading — a hole in the map that looks like real
    # absence. Fail loudly instead. This is also what certifies the
    # sub-neighborhood drop above is lossless.
    have = {(f["properties"]["name"], norm_borough(f["properties"].get("borough")))
            for f in features}
    missing = sorted(used - have)
    if missing:
        sys.exit("no top-level polygon for neighborhood(s) used by the entries CSV: "
                 + ", ".join(f"{n} ({b})" for n, b in missing))

    blob = json.dumps({"type": "FeatureCollection", "features": features},
                      separators=(",", ":"))
    stats = dict(
        src_features=len(geo["features"]), features=len(features),
        hoods=len(used),
        src_kb=round(SRC.stat().st_size / 1024),
        src_gzip_kb=round(len(gzip.compress(SRC.read_bytes())) / 1024),
        raw_kb=round(len(blob) / 1024),
        gzip_kb=round(len(gzip.compress(blob.encode("utf-8"))) / 1024),
    )
    return blob, stats


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="verify the committed file is current; write nothing")
    args = ap.parse_args()

    for path in (SRC, ENTRIES):
        if not path.exists():
            sys.exit(f"missing source file: {path}")

    blob, stats = build()
    print(
        "{src_features} features -> {features} top-level ({hoods} carry listings); "
        "{src_kb} KB raw / ~{src_gzip_kb} KB gzipped -> "
        "{raw_kb} KB raw / ~{gzip_kb} KB gzipped".format(**stats)
    )

    if args.check:
        if not OUT.exists():
            sys.exit(f"{OUT.name} is missing — run without --check to build it")
        if OUT.read_text(encoding="utf-8") != blob:
            sys.exit(f"{OUT.name} is out of date — re-run scripts/build_nyc_hoods.py")
        print(f"{OUT.name} is up to date")
        return

    OUT.write_text(blob, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
