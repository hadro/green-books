#!/usr/bin/env python3
"""Build nyc_geo.json — a slim canvas_fragment → coordinate lookup for the explorers.

`nyc-neighborhoods/nyc_entries_geocoded.csv` is the deliverable of the NYC
geocoding run: 7,995 rows, 99.6% resolved, carrying every original entry column
plus `neighborhood`, `borough`, `latitude`, `longitude` and QA fields. `nyc.html`
streams that CSV as its whole dataset, which is right for a page that is only
about NYC.

`all-volumes.html` needs almost none of it. It already has the entry rows; the
only thing it lacks is the coordinate. Fetching the 3.1 MB CSV there to read four
columns would add real weight to a page that already takes ~20s to load, so this
script emits just the lookup: ~470 KB raw, ~96 KB over the wire gzipped.

Keys are sha1(canvas_fragment)[:12] — the same content-addressed id the
thumbnail CDN uses, so the browser computes them with the `sha1hex()` already
inlined in each explorer rather than shipping the long IIIF URLs as JSON keys
(which alone would cost more than the whole file does this way).

Values are [lat, lon, neighborhood, borough, approx] where `approx` is 1 when the
geocode is not precise enough to point at a building — GEOMETRIC_CENTER or
APPROXIMATE quality, or a row the pipeline flagged for review. The explorers use
it to soften the map's claim rather than to hide the entry.

Licensing: coordinates come from NYC GeoSearch (NYC Planning Labs, public
domain) and the neighborhood/borough labels are the factual output of a
point-in-polygon computation, both CC0-compatible per
nyc-neighborhoods/README.md. The CC BY-SA boundary geometry in
nyc-neighborhoods.geojson is deliberately NOT part of this file.

Usage:
    python3 scripts/build_nyc_geo.py [--check]

--check verifies the committed nyc_geo.json matches the CSV and exits non-zero
if it has drifted, without writing anything.
"""

import argparse
import csv
import gzip
import hashlib
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "nyc-neighborhoods" / "nyc_entries_geocoded.csv"
OUT = ROOT / "nyc_geo.json"

# Qualities that do not identify a building. ROOFTOP and RANGE_INTERPOLATED are
# precise enough to drop a marker on; these are not.
FUZZY_QUALITY = {"GEOMETRIC_CENTER", "APPROXIMATE", ""}


def build():
    csv.field_size_limit(10 ** 7)
    out = {}
    total = skipped = dupes = approx = 0
    with SRC.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            total += 1
            cf = (row.get("canvas_fragment") or "").strip()
            lat = (row.get("latitude") or "").strip()
            lon = (row.get("longitude") or "").strip()
            if not cf or not lat or not lon:
                skipped += 1
                continue
            key = hashlib.sha1(cf.encode("utf-8")).hexdigest()[:12]
            if key in out:
                # 7,995 rows carry 7,913 distinct canvas_fragments: a handful of
                # entries were extracted twice from one clipped region. They
                # geocode to the same place, so first-wins is fine.
                dupes += 1
                continue
            fuzzy = (
                (row.get("geocode_quality") or "").strip().upper() in FUZZY_QUALITY
                or (row.get("review_flag") or "").strip().lower() == "true"
            )
            if fuzzy:
                approx += 1
            out[key] = [
                round(float(lat), 5),
                round(float(lon), 5),
                (row.get("neighborhood") or "").strip(),
                (row.get("borough") or "").strip(),
                1 if fuzzy else 0,
            ]
    blob = json.dumps(out, separators=(",", ":"), sort_keys=True)
    stats = dict(
        total=total, written=len(out), skipped=skipped, dupes=dupes, approx=approx,
        raw_kb=round(len(blob) / 1024),
        gzip_kb=round(len(gzip.compress(blob.encode("utf-8"))) / 1024),
    )
    return blob, stats


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="verify the committed file is current; write nothing")
    args = ap.parse_args()

    if not SRC.exists():
        sys.exit(f"missing source CSV: {SRC}")

    blob, stats = build()
    print(
        "{total} rows -> {written} entries "
        "({skipped} without coordinates, {dupes} duplicate fragments, "
        "{approx} approximate); {raw_kb} KB raw, ~{gzip_kb} KB gzipped".format(**stats)
    )

    if args.check:
        if not OUT.exists():
            sys.exit(f"{OUT.name} is missing — run without --check to build it")
        if OUT.read_text(encoding="utf-8") != blob:
            sys.exit(f"{OUT.name} is out of date — re-run scripts/build_nyc_geo.py")
        print(f"{OUT.name} is up to date")
        return

    OUT.write_text(blob, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
