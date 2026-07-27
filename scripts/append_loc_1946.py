#!/usr/bin/env python3
"""One-off script: integrate the LOC 1946 Green Book (item 2016298176) into
the site's data artifacts.

- Appends LOC entries to green_book_entries_all.csv (mapped to the master
  column set).
- Adds LOC canvas service tokens to image_to_volume.json.
- Adds LOC pages to canvas_map.json.
- Writes manifests/2016298176/manifest.json (LOC manifest, @id rewritten).
- Recomputes explorer facet data from the updated master CSV and writes it
  to a scratchpad JSON file for review (does NOT edit explorer.html).

Idempotent: refuses to run if the master CSV already contains volume_id
2016298176.
"""
import csv
import json
import os
import re
import sys

REPO_ROOT = "/Users/joshhadro/github/green-books"
LOC_DIR = "/Users/joshhadro/github/directory-pipeline/output/the_negro_motorist_green_book_2016298176/2016298176"
LOC_CSV = os.path.join(LOC_DIR, "entries_gemini-3.1-flash-lite_fixed_drift_flagged.csv")
LOC_MANIFEST = os.path.join(LOC_DIR, "manifest.json")

MASTER_CSV = os.path.join(REPO_ROOT, "green_book_entries_all.csv")
IMAGE_TO_VOLUME = os.path.join(REPO_ROOT, "image_to_volume.json")
CANVAS_MAP = os.path.join(REPO_ROOT, "canvas_map.json")
OUT_MANIFEST = os.path.join(REPO_ROOT, "manifests", "2016298176", "manifest.json")
EXPLORER_HTML = os.path.join(REPO_ROOT, "explorer.html")

SCRATCH_DIR = "/private/tmp/claude-501/-Users-joshhadro-github-green-books/d1fba99c-f022-4fe2-8e4c-f88801906b3b/scratchpad"
FIELD_META_OUT = os.path.join(SCRATCH_DIR, "field_meta_recompute.json")

VOLUME_ID = "2016298176"

sys.path.insert(0, REPO_ROOT)
from gb_categories import gb_category_group  # noqa: E402

# LOC column -> master column. Columns not listed here that share a name are
# copied by name. "description" maps to "notes". flag_hallucinated is dropped.
LOC_TO_MASTER_RENAME = {
    "description": "notes",
}
DROP_LOC_COLUMNS = {"flag_hallucinated"}

# Master columns with no LOC equivalent -> filled with empty string.
MASTER_ONLY_COLUMNS = {
    "sub_region",
    "amenities_services",
    "rates",
    "personnel",
    "reference_number",
    "is_recommended",
    "Fixed or checked",
}


def read_master_header():
    with open(MASTER_CSV, newline="") as f:
        reader = csv.reader(f)
        return next(reader)


def check_not_already_present(master_header):
    vid_idx = master_header.index("volume_id")
    with open(MASTER_CSV, newline="") as f:
        reader = csv.reader(f)
        next(reader)  # header
        for row in reader:
            if row[vid_idx] == VOLUME_ID:
                print(
                    f"ERROR: master CSV already contains volume_id {VOLUME_ID}. "
                    "Aborting without changes.",
                    file=sys.stderr,
                )
                sys.exit(1)


def load_loc_rows():
    with open(LOC_CSV, newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    return rows


def should_skip(row):
    if row.get("flag_unanchored") == "1":
        return True
    if row.get("flag_hallucinated") == "1":
        return True
    if "#xywh=" not in (row.get("canvas_fragment") or ""):
        return True
    return False


def map_loc_row_to_master(row, master_header):
    out = {}
    for col in master_header:
        if col in MASTER_ONLY_COLUMNS:
            out[col] = ""
            continue
        # find the LOC source column name for this master column
        loc_col = col
        # reverse-lookup rename: master "notes" <- LOC "description"
        for loc_name, master_name in LOC_TO_MASTER_RENAME.items():
            if master_name == col:
                loc_col = loc_name
                break
        out[col] = row.get(loc_col, "")
    # master convention is uppercase TRUE/FALSE; the LOC CSV uses True/False
    if out.get("is_advertisement") in ("True", "False"):
        out["is_advertisement"] = out["is_advertisement"].upper()
    return out


def append_rows_to_master(master_header, mapped_rows):
    with open(MASTER_CSV, "a", newline="") as f:
        writer = csv.writer(f)
        for row in mapped_rows:
            writer.writerow([row[col] for col in master_header])


def update_image_to_volume(kept_rows):
    with open(IMAGE_TO_VOLUME) as f:
        mapping = json.load(f)
    before = len(mapping)

    pattern = re.compile(r"/image-services/iiif/(service:[^/#]+)")
    bases = sorted(set(row["canvas_fragment"].split("#")[0] for row in kept_rows))
    added = 0
    for base in bases:
        m = pattern.search(base)
        if not m:
            print(f"WARNING: no service token match for {base}", file=sys.stderr)
            continue
        token = m.group(1)
        if token not in mapping:
            added += 1
        mapping[token] = VOLUME_ID

    with open(IMAGE_TO_VOLUME, "w") as f:
        json.dump(mapping, f, separators=(",", ":"))

    return added, len(mapping) - before, bases


def loc_resource_url(service_base, position):
    """Build the loc.gov reader URL for a tile.loc.gov service id.

    A LOC resource path is <collection>.<item>, and BOTH halves are carried in
    the service id:

        service:gdc:gdcscd:00:21:22:75:09:8:00212275098:00064
                    ^^^^^^ collection        ^^^^^^^^^^^ item

    i.e. collection is the third colon-segment and the item id is the
    second-to-last (the last is the page). The same shape holds for LOC's
    other collections -- service:rbc:lcrbmrp:t8073:001 is lcrbmrp.t8073.

    The item id ALONE does not resolve: this script used to emit
    /resource/00212275098/?sp=N, dropping the gdcscd. prefix, and every
    "open original source page" link for the 1946 edition led nowhere.
    """
    tail = service_base.rsplit("/", 1)[-1]
    parts = tail.split(":")
    if parts[0] != "service" or len(parts) < 5:
        raise ValueError("unrecognised LOC service id: %s" % service_base)
    collection, item = parts[2], parts[-2]
    return "https://www.loc.gov/resource/%s.%s/?sp=%d" % (collection, item, position)


def update_canvas_map(kept_rows, manifest):
    with open(CANVAS_MAP) as f:
        cmap = json.load(f)
    before = len(cmap)

    canvases = manifest["sequences"][0]["canvases"]
    canvas_by_id = {}
    for idx, c in enumerate(canvases):
        canvas_by_id[c["@id"]] = (c["width"], c["height"], idx + 1)

    bases = sorted(set(row["canvas_fragment"].split("#")[0] for row in kept_rows))
    unmatched = []
    added = 0
    for base in bases:
        info = canvas_by_id.get(base)
        if info is None:
            unmatched.append(base)
            continue
        width, height, position = info
        viewer_url = loc_resource_url(base, position)
        if base not in cmap:
            added += 1
        cmap[base] = [base, width, height, viewer_url]

    with open(CANVAS_MAP, "w") as f:
        json.dump(cmap, f, separators=(",", ":"))

    return added, len(cmap) - before, bases, unmatched


def write_manifest(manifest):
    os.makedirs(os.path.dirname(OUT_MANIFEST), exist_ok=True)
    out = dict(manifest)  # shallow copy; only top-level @id is rewritten
    out["@id"] = "https://hadro.github.io/green-books/manifests/2016298176/manifest.json"
    with open(OUT_MANIFEST, "w") as f:
        json.dump(out, f, indent=2)


def extract_current_field_meta():
    """Pull the current FIELD_META literal out of explorer.html without
    editing the file, so the recompute JSON can show before/after."""
    with open(EXPLORER_HTML) as f:
        for line in f:
            if "const FIELD_META" in line:
                marker = "const FIELD_META  = "
                idx = line.index(marker)
                json_str = line[idx + len(marker):].rstrip()
                if json_str.endswith(";"):
                    json_str = json_str[:-1]
                return json.loads(json_str)
    return None


def recompute_field_meta(master_header):
    with open(MASTER_CSV, newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    total_rows = len(rows)

    # volume_year distribution
    year_counts = {}
    for row in rows:
        y = row.get("volume_year", "")
        year_counts[y] = year_counts.get(y, 0) + 1
    year_pairs = sorted(year_counts.items(), key=lambda kv: kv[0])
    year_pairs = [[y, c] for y, c in year_pairs]

    # category folded top 25
    cat_counts = {}
    for row in rows:
        label = gb_category_group(row.get("category", ""))
        cat_counts[label] = cat_counts.get(label, 0) + 1
    cat_top25 = sorted(cat_counts.items(), key=lambda kv: -kv[1])[:25]
    cat_top25 = [[label, c] for label, c in cat_top25]

    # fill rate per column
    fill_rate = {}
    for col in master_header:
        non_empty = sum(1 for row in rows if (row.get(col) or "").strip() != "")
        fill_rate[col] = round(non_empty / total_rows, 4) if total_rows else 0.0

    current_field_meta = extract_current_field_meta()
    current = {}
    if current_field_meta:
        for entry in current_field_meta:
            name = entry.get("name")
            current[name] = {
                "fill_rate": entry.get("fill_rate"),
                "cardinality": entry.get("cardinality"),
                "top_values": entry.get("top_values"),
            }

    out = {
        "total_rows": total_rows,
        "volume_year": {
            "top_values": year_pairs,
            "cardinality": len(year_pairs),
        },
        "category_folded_top25": cat_top25,
        "fill_rate": fill_rate,
        "current_field_meta_from_explorer_html": {
            "volume_year": current.get("volume_year"),
            "category": current.get("category"),
            "all_fields_current_fill_rate": {
                name: v.get("fill_rate") for name, v in current.items()
            },
        },
    }

    os.makedirs(SCRATCH_DIR, exist_ok=True)
    with open(FIELD_META_OUT, "w") as f:
        json.dump(out, f, indent=2)


def main():
    master_header = read_master_header()
    check_not_already_present(master_header)

    loc_rows = load_loc_rows()
    kept_rows = []
    skipped = 0
    for row in loc_rows:
        if should_skip(row):
            skipped += 1
            continue
        kept_rows.append(row)

    mapped_rows = [map_loc_row_to_master(r, master_header) for r in kept_rows]
    append_rows_to_master(master_header, mapped_rows)

    with open(LOC_MANIFEST) as f:
        manifest = json.load(f)

    itv_added, itv_delta, itv_bases = update_image_to_volume(kept_rows)
    cmap_added, cmap_delta, cmap_bases, unmatched = update_canvas_map(kept_rows, manifest)
    write_manifest(manifest)

    recompute_field_meta(master_header)

    with open(MASTER_CSV, newline="") as f:
        new_total = sum(1 for _ in csv.reader(f)) - 1  # minus header

    print("=== append_loc_1946.py summary ===")
    print(f"LOC rows read: {len(loc_rows)}")
    print(f"Rows skipped (unanchored/hallucinated/no-xywh): {skipped}")
    print(f"Rows appended to master CSV: {len(mapped_rows)}")
    print(f"New master CSV total rows: {new_total}")
    print(f"Distinct LOC pages (canvas_fragment bases) among kept rows: {len(itv_bases)}")
    print(f"image_to_volume.json: {itv_added} new entries added (delta {itv_delta})")
    print(f"canvas_map.json: {cmap_added} new entries added (delta {cmap_delta})")
    if unmatched:
        print(f"WARNING: {len(unmatched)} canvas_fragment bases had NO matching manifest canvas:")
        for u in unmatched:
            print(f"  {u}")
    else:
        print("All canvas_fragment bases matched a manifest canvas.")
    print(f"Manifest written: {OUT_MANIFEST}")
    print(f"Field meta recompute written: {FIELD_META_OUT}")


if __name__ == "__main__":
    main()
