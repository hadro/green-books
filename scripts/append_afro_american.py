#!/usr/bin/env python3
"""One-off script: integrate four newly-pipelined NYPL volumes of
"Afro-American's Travel Guide" (1954, 1956, 1957, 1958) into the site's
travel-guide data artifacts.

- Appends entries to travel_guides_all.csv (mapped to the master column set).
- Adds NYPL image ids to travel_guides_image_to_volume.json.
- Adds pages to travel_guides_canvas_map.json.
- Writes manifests/<uuid>/manifest.json for each of the 4 volumes (IIIF v3,
  ids rewritten, real canvas/annotation dims patched in from the per-page
  aligned sidecars -- every canvas in the raw NYPL manifest reports a
  placeholder 2560x2560).
- Recomputes travel_guides_explorer.html facet data from the updated master
  CSV and writes it to a scratchpad JSON file for review (does NOT edit
  travel_guides_explorer.html).

Idempotent: refuses to run if the master CSV already contains any of the 4
volume_ids.

Mirrors scripts/append_loc_1946.py's shape. Key difference from that script:
the LOC manifest is IIIF v2 (`sequences` -> `canvases`); these four NYPL
manifests are IIIF v3 (`items`), so this script does v3 traversal and also
rewrites per-canvas/page/annotation ids (the LOC script only rewrote the
top-level manifest @id) to match the convention already used by the repo's
existing travel-guide manifests (see manifests/0b8da6b0-.../manifest.json).
"""
import csv
import glob
import json
import os
import re
import sys

REPO_ROOT = "/Users/joshhadro/github/green-books"
PIPELINE_OUTPUT = "/Users/joshhadro/github/directory-pipeline/output"

MASTER_CSV = os.path.join(REPO_ROOT, "travel_guides_all.csv")
IMAGE_TO_VOLUME = os.path.join(REPO_ROOT, "travel_guides_image_to_volume.json")
CANVAS_MAP = os.path.join(REPO_ROOT, "travel_guides_canvas_map.json")
MANIFESTS_DIR = os.path.join(REPO_ROOT, "manifests")
EXPLORER_HTML = os.path.join(REPO_ROOT, "travel_guides_explorer.html")

SCRATCH_DIR = (
    "/private/tmp/claude-501/-Users-joshhadro-github-green-books/"
    "297ef446-4808-4888-a890-4fcdb02798e2/scratchpad"
)
FIELD_META_OUT = os.path.join(SCRATCH_DIR, "tg_field_meta_recompute.json")

PUBLICATION = "Afro-American's Travel Guide"

# (pipeline output dir name, volume UUID, volume year)
VOLUMES = [
    ("afro-american-travel-guide-1954", "b5f95f60-7256-013f-3691-0242ac110002", "1954"),
    ("afro-american-travel-guide-1956", "e36a5750-7256-013f-f2b2-0242ac110002", "1956"),
    ("afro-american-travel-guide-1957", "fb4f57d0-7256-013f-8933-0242ac110003", "1957"),
    ("afro-american-travel-guide-1958", "2a3699e0-7257-013f-019f-0242ac110003", "1958"),
]

sys.path.insert(0, REPO_ROOT)
from gb_categories import gb_category_group  # noqa: E402

# Afro CSV column -> master column, for columns whose name differs.
AFRO_TO_MASTER_RENAME = {
    "details": "notes",
    "state_country": "state",
}

# Master columns with no equivalent in the Afro CSVs -> filled with "".
MASTER_ONLY_COLUMNS = {
    "sub_region",
    "proprietor",
    "amenities_services",
    "rates",
    "personnel",
    "reference_number",
    "is_advertisement",
    "is_recommended",
}

# Master columns populated per-volume by this script, not read from the CSV.
VOLUME_META_COLUMNS = {"volume_id", "volume_title", "volume_year", "publication"}

IMAGE_ID_RE = re.compile(r"/iiif/\d+/(\d+)")


def read_master_header():
    with open(MASTER_CSV, newline="") as f:
        reader = csv.reader(f)
        return next(reader)


def check_not_already_present(master_header):
    vid_idx = master_header.index("volume_id")
    volume_ids = {uuid for _dirname, uuid, _year in VOLUMES}
    with open(MASTER_CSV, newline="") as f:
        reader = csv.reader(f)
        next(reader)  # header
        for row in reader:
            if row[vid_idx] in volume_ids:
                print(
                    f"ERROR: master CSV already contains volume_id {row[vid_idx]}. "
                    "Aborting without changes.",
                    file=sys.stderr,
                )
                sys.exit(1)


def load_manifest(dirname):
    path = os.path.join(PIPELINE_OUTPUT, dirname, "manifest.json")
    with open(path) as f:
        return json.load(f)


def volume_title_from_manifest(manifest):
    return manifest["label"]["en"][0]


def load_afro_rows(dirname):
    path = os.path.join(PIPELINE_OUTPUT, dirname, "entries_gemini-3.1-flash-lite_fixed.csv")
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        return list(reader)


def should_skip(row):
    """Same filter as directory-pipeline/analysis/combine_volumes.py."""
    if row.get("flag_unanchored") == "1":
        return True
    if row.get("flag_hallucinated") == "1":
        return True
    if "#xywh=" not in (row.get("canvas_fragment") or ""):
        return True
    return False


def map_row_to_master(row, master_header, meta):
    out = {}
    for col in master_header:
        if col in MASTER_ONLY_COLUMNS:
            out[col] = ""
            continue
        if col in VOLUME_META_COLUMNS:
            out[col] = meta[col]
            continue
        src_col = col
        for afro_name, master_name in AFRO_TO_MASTER_RENAME.items():
            if master_name == col:
                src_col = afro_name
                break
        out[col] = row.get(src_col, "")
    return out


def append_rows_to_master(master_header, mapped_rows):
    with open(MASTER_CSV, "a", newline="") as f:
        writer = csv.writer(f)
        for row in mapped_rows:
            writer.writerow([row[col] for col in master_header])


def load_sidecar_lookup(dirname):
    """Scan *_aligned.json in a volume's pipeline dir.

    Returns (by_canvas_uri, by_image_id), both mapping to (width, height).
    The aligned sidecars are the only trusted source of real canvas
    dimensions -- every canvas in these manifests reports a placeholder
    2560x2560.
    """
    by_canvas_uri = {}
    by_image_id = {}
    pattern = os.path.join(PIPELINE_OUTPUT, dirname, "*_aligned.json")
    for path in glob.glob(pattern):
        with open(path) as f:
            d = json.load(f)
        uri = d.get("canvas_uri")
        width = d.get("canvas_width")
        height = d.get("canvas_height")
        if not uri or width is None or height is None:
            continue
        by_canvas_uri[uri] = (width, height)
        m = IMAGE_ID_RE.search(uri)
        if m:
            by_image_id[m.group(1)] = (width, height)
    return by_canvas_uri, by_image_id


def update_image_to_volume(kept_rows, volume_id):
    with open(IMAGE_TO_VOLUME) as f:
        mapping = json.load(f)
    before = len(mapping)

    image_ids = set()
    for row in kept_rows:
        base = row["canvas_fragment"].split("#")[0]
        m = IMAGE_ID_RE.search(base)
        if not m:
            print(f"WARNING: no image id match for {base}", file=sys.stderr)
            continue
        image_ids.add(m.group(1))

    added = 0
    for image_id in sorted(image_ids):
        if image_id not in mapping:
            added += 1
        mapping[image_id] = volume_id

    # Match the existing file's formatting exactly: json.dump with default
    # separators (", " / ": "), no indent, no trailing newline -- verified
    # byte-for-byte against the committed travel_guides_image_to_volume.json.
    with open(IMAGE_TO_VOLUME, "w") as f:
        json.dump(mapping, f)

    return added, len(mapping) - before, image_ids


def update_canvas_map(kept_rows, volume_id, by_canvas_uri, canvas_index_by_base):
    with open(CANVAS_MAP) as f:
        cmap = json.load(f)
    before = len(cmap)

    bases = sorted(set(row["canvas_fragment"].split("#")[0] for row in kept_rows))
    unmatched = []
    added = 0
    for base in bases:
        dims = by_canvas_uri.get(base)
        if dims is None:
            print(f"WARNING: no aligned sidecar for canvas_fragment base {base}", file=sys.stderr)
            unmatched.append(base)
            continue
        width, height = dims
        m = IMAGE_ID_RE.search(base)
        if not m:
            print(f"WARNING: no image id match for {base}", file=sys.stderr)
            unmatched.append(base)
            continue
        image_id = m.group(1)
        # service_base convention verified against the existing 0b8da6b0-...
        # entries in this file: strip the /full/!W,H/0/default.jpg suffix.
        # e.g. https://iiif.nypl.org/iiif/3/58019257/full/!760,760/0/default.jpg
        # -> https://iiif.nypl.org/iiif/3/58019257
        service_prefix = base.split(f"/{image_id}/", 1)[0]
        service_base = f"{service_prefix}/{image_id}"
        position = canvas_index_by_base.get(base)
        if position is None:
            print(f"WARNING: no manifest canvas found for base {base}", file=sys.stderr)
            unmatched.append(base)
            continue
        # viewer_url shape + 0-based canvasIndex verified against 0b8da6b0-...:
        # canvas at manifest.items[0] (the first page) has canvasIndex=0.
        viewer_url = f"https://digitalcollections.nypl.org/items/{volume_id}?canvasIndex={position}"
        if base not in cmap:
            added += 1
        cmap[base] = [service_base, width, height, viewer_url]

    # Match existing file's formatting: default separators, no indent, no
    # trailing newline (verified byte-for-byte).
    with open(CANVAS_MAP, "w") as f:
        json.dump(cmap, f)

    return added, len(cmap) - before, bases, unmatched


def rewrite_and_patch_manifest(manifest, volume_id, by_image_id):
    """Return (patched_manifest, canvas_index_by_base, unmatched_canvases).

    patched_manifest has:
    - top-level id rewritten to the hadro.github.io manifest URL (matches
      every existing repo manifest, e.g. manifests/0b8da6b0-.../manifest.json)
    - each canvas's id/page id/annotation id/target rewritten to
      "<manifest_id>/canvas/<idx>[/page/<p>[/annotation/<a>]]", 0-based,
      mirroring the existing repo manifests exactly (image/service ids
      themselves are left pointing at iiif.nypl.org, unrewritten -- verified
      there are zero leftover api-collections.nypl.org references in the
      existing 0b8da6b0-... manifest, i.e. everything else is left alone)
    - each canvas's width/height, and each painting annotation body's (and
      its service's) width/height, patched in from the aligned sidecars --
      the raw manifest reports a placeholder 2560x2560 for every canvas

    canvas_index_by_base maps each painting annotation's body id (the
    canvas_fragment base used throughout the CSV/JSON artifacts) to its
    0-based canvas index, needed by update_canvas_map for canvasIndex.

    Canvases with no matching sidecar are left with their placeholder
    width/height untouched; each such canvas is returned in
    unmatched_canvases as (canvas_index, image_id_or_None) for a warning.
    """
    out = dict(manifest)
    manifest_id = f"https://hadro.github.io/green-books/manifests/{volume_id}/manifest.json"
    out["id"] = manifest_id

    canvas_index_by_base = {}
    unmatched_canvases = []

    items = out.get("items", [])
    for idx, canvas in enumerate(items):
        canvas_id = f"{manifest_id}/canvas/{idx}"
        canvas["id"] = canvas_id

        image_id = None
        for ap_idx, ap in enumerate(canvas.get("items", [])):
            ap["id"] = f"{canvas_id}/page/{ap_idx}"
            for ann_idx, ann in enumerate(ap.get("items", [])):
                ann["id"] = f"{canvas_id}/page/{ap_idx}/annotation/{ann_idx}"
                ann["target"] = canvas_id
                body = ann.get("body", {})
                body_id = body.get("id")
                if body_id:
                    canvas_index_by_base[body_id] = idx
                services = body.get("service") or []
                svc_id = services[0].get("id") if services else body_id
                m = IMAGE_ID_RE.search(svc_id or "")
                if m:
                    image_id = m.group(1)

        dims = by_image_id.get(image_id) if image_id else None
        if dims is None:
            unmatched_canvases.append((idx, image_id))
            continue
        width, height = dims
        canvas["width"] = width
        canvas["height"] = height
        for ap in canvas.get("items", []):
            for ann in ap.get("items", []):
                body = ann.get("body", {})
                body["width"] = width
                body["height"] = height
                for svc in body.get("service") or []:
                    svc["width"] = width
                    svc["height"] = height

    return out, canvas_index_by_base, unmatched_canvases


def write_manifest(manifest, volume_id):
    out_path = os.path.join(MANIFESTS_DIR, volume_id, "manifest.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    # Match existing repo manifests: json.dump with indent=2, no trailing
    # newline (verified byte-for-byte against manifests/0b8da6b0-.../manifest.json).
    with open(out_path, "w") as f:
        json.dump(manifest, f, indent=2)
    return out_path


def extract_current_field_meta():
    """Pull the current FIELD_META literal out of travel_guides_explorer.html
    without editing the file, so the recompute JSON can show before/after."""
    with open(EXPLORER_HTML) as f:
        for line in f:
            marker = "const FIELD_META"
            if marker in line:
                idx = line.index(marker)
                rest = line[idx + len(marker):]
                eq_idx = rest.index("=")
                json_str = rest[eq_idx + 1:].rstrip()
                if json_str.endswith(";"):
                    json_str = json_str[:-1]
                return json.loads(json_str)
    return None


def recompute_field_meta(master_header):
    with open(MASTER_CSV, newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    total_rows = len(rows)

    # volume_year distribution, chronological
    year_counts = {}
    for row in rows:
        y = row.get("volume_year", "")
        year_counts[y] = year_counts.get(y, 0) + 1
    year_pairs = sorted(year_counts.items(), key=lambda kv: kv[0])
    year_pairs = [[y, c] for y, c in year_pairs]

    # publication distribution, descending count
    pub_counts = {}
    for row in rows:
        p = row.get("publication", "")
        pub_counts[p] = pub_counts.get(p, 0) + 1
    pub_pairs = sorted(pub_counts.items(), key=lambda kv: -kv[1])
    pub_pairs = [[p, c] for p, c in pub_pairs]

    # category folded top 25
    cat_counts = {}
    for row in rows:
        label = gb_category_group(row.get("category", ""))
        cat_counts[label] = cat_counts.get(label, 0) + 1
    cat_top25 = sorted(cat_counts.items(), key=lambda kv: -kv[1])[:25]
    cat_top25 = [[label, c] for label, c in cat_top25]

    # fill rate + cardinality per column, for every column in the header
    fill_rate = {}
    cardinality = {}
    for col in master_header:
        values = [(row.get(col) or "") for row in rows]
        non_empty = sum(1 for v in values if v.strip() != "")
        fill_rate[col] = round(non_empty / total_rows, 4) if total_rows else 0.0
        cardinality[col] = len({v for v in values if v.strip() != ""})

    current_field_meta = extract_current_field_meta()
    current = {}
    if current_field_meta:
        for entry in current_field_meta:
            name = entry.get("name")
            current[name] = {
                "fill_rate": entry.get("fill_rate"),
                "cardinality": entry.get("cardinality"),
            }

    out = {
        "total_rows": total_rows,
        "volume_year": {
            "top_values": year_pairs,
            "cardinality": len(year_pairs),
        },
        "publication": {
            "top_values": pub_pairs,
            "cardinality": len(pub_pairs),
        },
        "category_folded_top25": cat_top25,
        "fill_rate": fill_rate,
        "cardinality": cardinality,
        "current_field_meta_from_explorer_html": current,
    }

    os.makedirs(SCRATCH_DIR, exist_ok=True)
    with open(FIELD_META_OUT, "w") as f:
        json.dump(out, f, indent=2)


def main():
    master_header = read_master_header()
    check_not_already_present(master_header)

    per_volume_summaries = []
    manifest_paths = []
    all_unmatched_cmap = []
    all_unmatched_manifest = []
    grand_itv_added = 0
    grand_cmap_added = 0

    for dirname, volume_id, year in VOLUMES:
        manifest = load_manifest(dirname)
        volume_title = volume_title_from_manifest(manifest)
        meta = {
            "volume_id": volume_id,
            "volume_title": volume_title,
            "volume_year": year,
            "publication": PUBLICATION,
        }

        afro_rows = load_afro_rows(dirname)
        kept_rows = []
        dropped = 0
        for row in afro_rows:
            if should_skip(row):
                dropped += 1
                continue
            kept_rows.append(row)

        mapped_rows = [map_row_to_master(r, master_header, meta) for r in kept_rows]
        append_rows_to_master(master_header, mapped_rows)

        by_canvas_uri, by_image_id = load_sidecar_lookup(dirname)

        patched_manifest, canvas_index_by_base, unmatched_manifest = rewrite_and_patch_manifest(
            manifest, volume_id, by_image_id
        )
        for canvas_idx, image_id in unmatched_manifest:
            print(
                f"WARNING [{dirname}]: canvas index {canvas_idx} "
                f"(image id {image_id}) has no matching aligned sidecar; "
                "left with placeholder dimensions.",
                file=sys.stderr,
            )
        all_unmatched_manifest.extend((dirname, c, i) for c, i in unmatched_manifest)

        out_path = write_manifest(patched_manifest, volume_id)
        manifest_paths.append(out_path)

        itv_added, itv_delta, itv_ids = update_image_to_volume(kept_rows, volume_id)
        cmap_added, cmap_delta, cmap_bases, unmatched_cmap = update_canvas_map(
            kept_rows, volume_id, by_canvas_uri, canvas_index_by_base
        )
        all_unmatched_cmap.extend((dirname, b) for b in unmatched_cmap)
        grand_itv_added += itv_added
        grand_cmap_added += cmap_added

        per_volume_summaries.append({
            "dirname": dirname,
            "volume_id": volume_id,
            "volume_title": volume_title,
            "year": year,
            "rows_read": len(afro_rows),
            "rows_dropped": dropped,
            "rows_kept": len(kept_rows),
            "distinct_images": len(itv_ids),
            "distinct_canvas_bases": len(cmap_bases),
            "itv_added": itv_added,
            "cmap_added": cmap_added,
        })

    recompute_field_meta(master_header)

    with open(MASTER_CSV, newline="") as f:
        new_total = sum(1 for _ in csv.reader(f)) - 1  # minus header

    print("=== append_afro_american.py summary ===")
    for s in per_volume_summaries:
        print(
            f"[{s['dirname']}] volume_id={s['volume_id']} year={s['year']} "
            f"title={s['volume_title']!r}"
        )
        print(
            f"  rows read={s['rows_read']} kept={s['rows_kept']} "
            f"dropped(unanchored/hallucinated/no-xywh)={s['rows_dropped']}"
        )
        print(
            f"  distinct canvas images={s['distinct_images']} "
            f"distinct canvas_fragment bases={s['distinct_canvas_bases']}"
        )
        print(
            f"  travel_guides_image_to_volume.json new entries={s['itv_added']}, "
            f"travel_guides_canvas_map.json new entries={s['cmap_added']}"
        )
    print(f"New travel_guides_all.csv total rows: {new_total}")
    print(f"travel_guides_image_to_volume.json: {grand_itv_added} total new entries added")
    print(f"travel_guides_canvas_map.json: {grand_cmap_added} total new entries added")
    if all_unmatched_cmap:
        print(f"WARNING: {len(all_unmatched_cmap)} canvas_fragment bases had NO sidecar/manifest match:")
        for dirname, base in all_unmatched_cmap:
            print(f"  [{dirname}] {base}")
    else:
        print("All canvas_fragment bases matched a sidecar and a manifest canvas.")
    if all_unmatched_manifest:
        print(f"WARNING: {len(all_unmatched_manifest)} manifest canvases had NO aligned sidecar (left at placeholder dims):")
        for dirname, canvas_idx, image_id in all_unmatched_manifest:
            print(f"  [{dirname}] canvas index {canvas_idx} (image id {image_id})")
    else:
        print("Every manifest canvas across all 4 volumes matched an aligned sidecar.")
    print("Manifests written:")
    for p in manifest_paths:
        print(f"  {p}")
    print(f"Field meta recompute written: {FIELD_META_OUT}")


if __name__ == "__main__":
    main()
