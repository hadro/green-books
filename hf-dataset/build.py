#!/usr/bin/env python3
"""Build the unified Hugging Face dataset from the two source CSVs.

Merges green_book_entries_all.csv + travel_guides_all.csv into a single
public-domain-oriented listings dataset with a shared 18-column schema.
Also emits per-volume rights provenance and dataset statistics for the card.
"""
import csv, json, os, sys
from collections import Counter, OrderedDict

ROOT = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(ROOT)  # source CSVs + gb_categories.py live in the repo root
OUT_DIR = ROOT
sys.path.insert(0, REPO)
from gb_categories import gb_category_group, gb_state_normalize  # shared with the JS explorer

# Unified schema, fixed column order. The *_normalized columns are derived by
# the shared folding logic in gb_categories.py (ported from gb-categories.js);
# the raw category/state values are preserved intact alongside them.
SCHEMA = [
    "publication", "source_corpus",
    "volume_id", "volume_title", "volume_year",
    "name", "proprietor",
    "category", "category_normalized",
    "address", "city",
    "state", "state_normalized",
    "phone", "rates", "notes",
    "is_advertisement", "is_recommended",
    "canvas_fragment", "image",
]

GB_PUBLICATION = "The Green Book"  # canonical series label for all 23 GB volumes

# Per-volume NYPL rights (from get_rights_info). All PDREN except the one orphan work.
ORPHAN_UUID = "4693c100-bde9-0136-1db2-00dd1dfcff8d"  # Travelguide 1957 -> ICORPHAN

SOURCES = [
    ("green_book_entries_all.csv", "green_book"),
    ("travel_guides_all.csv", "travel_guides"),
]

rows_out = []
fill = {c: 0 for c in SCHEMA}
pub_counts = Counter()
year_counts = Counter()
state_counts = Counter()
cat_counts = Counter()
state_norm_counts = Counter()
cat_norm_counts = Counter()
vol_meta = OrderedDict()  # volume_id -> (publication, volume_title, source, rowcount)

for path, src in SOURCES:
    with open(os.path.join(REPO, path), newline="") as f:
        for r in csv.DictReader(f):
            pub = GB_PUBLICATION if src == "green_book" else (r.get("publication") or "").strip()
            out = {
                "publication": pub,
                "source_corpus": src,
                "volume_id": r.get("volume_id", ""),
                "volume_title": r.get("volume_title", ""),
                "volume_year": r.get("volume_year", ""),
                "name": r.get("name", ""),
                "proprietor": r.get("proprietor", ""),
                "category": r.get("category", ""),
                "category_normalized": gb_category_group(r.get("category", "")),
                "address": r.get("address", ""),
                "city": r.get("city", ""),
                "state": r.get("state", ""),
                "state_normalized": gb_state_normalize(r.get("state", "")),
                "phone": r.get("phone", ""),
                "rates": r.get("rates", ""),
                "notes": r.get("notes", ""),
                "is_advertisement": r.get("is_advertisement", ""),
                "is_recommended": r.get("is_recommended", ""),
                "canvas_fragment": r.get("canvas_fragment", ""),
                "image": r.get("image", ""),
            }
            rows_out.append(out)
            for c in SCHEMA:
                if (out[c] or "").strip():
                    fill[c] += 1
            pub_counts[pub] += 1
            if out["volume_year"].strip():
                year_counts[out["volume_year"].strip()] += 1
            state_counts[out["state"].strip()] += 1
            state_norm_counts[out["state_normalized"]] += 1
            cat_norm_counts[out["category_normalized"]] += 1
            if out["category"].strip():
                cat_counts[out["category"].strip()] += 1
            vid = out["volume_id"]
            if vid not in vol_meta:
                vol_meta[vid] = {"publication": pub, "volume_title": out["volume_title"],
                                 "source": src, "rows": 0}
            vol_meta[vid]["rows"] += 1

# Write merged CSV
out_csv = os.path.join(OUT_DIR, "travel_guides_green_book_all.csv")
with open(out_csv, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=SCHEMA)
    w.writeheader()
    w.writerows(rows_out)

# Write per-volume rights provenance
rights_rows = []
for vid, m in vol_meta.items():
    is_orphan = (vid == ORPHAN_UUID)
    rights_rows.append({
        "volume_id": vid,
        "publication": m["publication"],
        "volume_title": m["volume_title"],
        "source_corpus": m["source"],
        "rows": m["rows"],
        "nypl_copyright_status": "ICORPHAN" if is_orphan else "PDREN",
        "rights_statement_uri": ("http://rightsstatements.org/vocab/InC-RUU/1.0/"
                                 if is_orphan else
                                 "http://rightsstatements.org/vocab/NoC-US/1.0/"),
        "public_domain": "false" if is_orphan else "true",
    })
with open(os.path.join(OUT_DIR, "volume_rights.csv"), "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rights_rows[0].keys()))
    w.writeheader()
    w.writerows(rights_rows)

n = len(rows_out)
stats = {
    "total_rows": n,
    "total_volumes": len(vol_meta),
    "publications": pub_counts.most_common(),
    "year_range": [min(year_counts), max(year_counts)] if year_counts else None,
    "distinct_states": len(state_counts),
    "distinct_states_normalized": len(state_norm_counts),
    "distinct_categories": len(cat_counts),
    "distinct_categories_normalized": len(cat_norm_counts),
    "fill_pct": {c: round(100 * fill[c] / n, 1) for c in SCHEMA},
    "top_categories": cat_counts.most_common(20),
    "top_states": state_counts.most_common(60),
    "orphan_rows": vol_meta[ORPHAN_UUID]["rows"],
}
# Internal build stats — kept in the repo root, not the publishable dataset dir.
with open(os.path.join(REPO, "_hf_build_stats.json"), "w") as f:
    json.dump(stats, f, indent=2)

# Console summary
print(f"Wrote {out_csv}")
print(f"Rows: {n}  Volumes: {len(vol_meta)}  Year range: {stats['year_range']}")
print(f"Distinct states: {len(state_counts)} -> {len(state_norm_counts)} normalized")
print(f"Distinct categories: {len(cat_counts)} -> {len(cat_norm_counts)} normalized (folded)")
print("\nPublications:")
for k, v in pub_counts.most_common():
    print(f"  {v:6d}  {k}")
print("\nFill %:")
for c in SCHEMA:
    print(f"  {c:18s} {stats['fill_pct'][c]:5.1f}%")
print(f"\nOrphan volume (Travelguide 1957) rows: {stats['orphan_rows']}")
print(f"\nCSV size: {os.path.getsize(out_csv)/1e6:.1f} MB")
