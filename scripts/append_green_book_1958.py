#!/usr/bin/env python3
"""One-off script: integrate the NYPL 1958 Green Book (item
b4affe50-7ca3-013f-af86-0242ac110002, "The Negro Travelers' Green Book: 1958")
into the site's data artifacts. It fills the 1957 -> 1959 gap.

Two phases, because drift scoring has to see the new rows next to every other
edition (its cross-volume check compares a business's state across editions):

  stage  Map the pipeline's fixed CSV onto the master header and write, into
         the volume's pipeline output dir:
           - entries_..._fixed_master.csv     the 1958 rows alone
           - drift_input_all_plus_1958.csv    current master + the 1958 rows
         Touches nothing in this repo. Prints the drift command to run next.

  apply  Read the drift script's output, copy drift_* onto the 1958 rows, then:
           - append them to green_book_entries_all.csv
           - add their image ids to image_to_volume.json
           - add their pages to canvas_map.json
           - write manifests/<uuid>/manifest.json (IIIF v3, ids rewritten,
             real canvas dims patched in)
           - recompute explorer.html facet data into a scratch JSON for review
             (does NOT edit explorer.html)
         Refuses to run if the master CSV already holds this volume_id.

Shaped after scripts/append_loc_1946.py (Green Book master target) and
scripts/append_afro_american.py (NYPL v3 manifest + placeholder dims). As with
those volumes, every canvas in the raw NYPL manifest reports a placeholder
2560x2560; the per-page *_aligned.json sidecars hold the real dims, which is the
space the CSV #xywh= boxes are in. Five pages' sidecars had themselves fallen
back to the placeholder and were repaired with tools/rescale_canvas_fragments.py
+ tools/patch_canvas_fragments.py before this script was written.

Pipeline-side history of the input CSV (all in the volume's output dir):
  - page 0078 never went through NER on the first run; re-run, then 10 listings
    NER still dropped were added by hand (hand_added=True in the CSV). Those
    rows are marked "Fixed or checked" = TRUE here.
  - fix_entries.py --infer-categories (category lives in the `section` column).
"""
import argparse
import csv
import glob
import json
import os
import re
import sys

REPO_ROOT = "/Users/joshhadro/github/green-books"
VOLUME_DIR = ("/Users/joshhadro/github/directory-pipeline/output/"
              "b4affe50-7ca3-013f-af86-0242ac110002")
SOURCE_CSV = os.path.join(VOLUME_DIR, "entries_gemini-3.1-flash-lite_fixed.csv")
SOURCE_MANIFEST = os.path.join(VOLUME_DIR, "manifest.json")
STAGED_CSV = os.path.join(VOLUME_DIR, "entries_gemini-3.1-flash-lite_fixed_master.csv")
DRIFT_INPUT = os.path.join(VOLUME_DIR, "drift_input_all_plus_1958.csv")
DRIFT_OUTPUT = os.path.join(VOLUME_DIR, "drift_output_all_plus_1958.csv")

MASTER_CSV = os.path.join(REPO_ROOT, "green_book_entries_all.csv")
IMAGE_TO_VOLUME = os.path.join(REPO_ROOT, "image_to_volume.json")
CANVAS_MAP = os.path.join(REPO_ROOT, "canvas_map.json")
MANIFESTS_DIR = os.path.join(REPO_ROOT, "manifests")
EXPLORER_HTML = os.path.join(REPO_ROOT, "explorer.html")

SCRATCH_DIR = ("/private/tmp/claude-501/-Users-joshhadro-github-green-books/"
               "e66aebbe-0a26-4d86-b0c5-809eab312b01/scratchpad")
FIELD_META_OUT = os.path.join(SCRATCH_DIR, "gb1958_field_meta_recompute.json")

VOLUME_ID = "b4affe50-7ca3-013f-af86-0242ac110002"
VOLUME_YEAR = "1958"

sys.path.insert(0, REPO_ROOT)
from gb_categories import gb_category_group  # noqa: E402

# 1958 CSV column -> master column, for columns whose name differs.
SOURCE_TO_MASTER_RENAME = {
    "business_name": "name",
    "section": "category",
    "is_advertiser": "is_advertisement",
}

# Master columns with no 1958 equivalent -> filled with "".
MASTER_ONLY_COLUMNS = {
    "sub_region",
    "phone",
    "proprietor",
    "amenities_services",
    "rates",
    "personnel",
    "reference_number",
    "is_recommended",
}

DRIFT_COLUMNS = ["drift_geonames", "drift_window", "drift_cross_volume",
                 "drift_alignment", "drift_score"]

IMAGE_ID_RE = re.compile(r"/iiif/\d+/(\d+)")


# ── shared ───────────────────────────────────────────────────────────────────

def read_master_header():
    with open(MASTER_CSV, newline="") as f:
        return next(csv.reader(f))


def check_not_already_present(master_header):
    vid_idx = master_header.index("volume_id")
    with open(MASTER_CSV, newline="") as f:
        reader = csv.reader(f)
        next(reader)
        for row in reader:
            if row[vid_idx] == VOLUME_ID:
                sys.exit(f"ERROR: master CSV already contains volume_id {VOLUME_ID}. "
                         "Aborting without changes.")


def load_manifest():
    with open(SOURCE_MANIFEST) as f:
        return json.load(f)


def should_skip(row):
    """Same filter as directory-pipeline/analysis/combine_volumes.py."""
    if row.get("flag_unanchored") == "1":
        return True
    if row.get("flag_hallucinated") == "1":
        return True
    if "#xywh=" not in (row.get("canvas_fragment") or ""):
        return True
    return False


def map_row_to_master(row, master_header, volume_title):
    meta = {"volume_id": VOLUME_ID, "volume_title": volume_title,
            "volume_year": VOLUME_YEAR}
    out = {}
    for col in master_header:
        if col in meta:
            out[col] = meta[col]
        elif col in MASTER_ONLY_COLUMNS or col in DRIFT_COLUMNS:
            out[col] = ""
        elif col == "Fixed or checked":
            # the 10 page-0078 listings NER dropped were entered by hand
            out[col] = "TRUE" if row.get("hand_added") == "True" else ""
        else:
            src = next((s for s, m in SOURCE_TO_MASTER_RENAME.items() if m == col), col)
            out[col] = row.get(src, "")
    # master convention is uppercase TRUE/FALSE; the pipeline CSV uses True/False
    if out["is_advertisement"] in ("True", "False"):
        out["is_advertisement"] = out["is_advertisement"].upper()
    # master states are uppercase headings; nine 1958 rows came back title-case
    out["state"] = out["state"].upper()
    return out


def read_rows(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def write_rows(path, header, rows):
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for row in rows:
            writer.writerow([row[c] for c in header])


# ── stage ────────────────────────────────────────────────────────────────────

def stage():
    master_header = read_master_header()
    check_not_already_present(master_header)
    volume_title = load_manifest()["label"]["en"][0]

    source_rows = read_rows(SOURCE_CSV)
    kept = [r for r in source_rows if not should_skip(r)]
    mapped = [map_row_to_master(r, master_header, volume_title) for r in kept]
    write_rows(STAGED_CSV, master_header, mapped)

    # Drift input: the current master verbatim, then the 1958 rows.
    with open(MASTER_CSV, newline="") as src, open(DRIFT_INPUT, "w", newline="") as dst:
        dst.write(src.read())
    with open(DRIFT_INPUT, "a", newline="") as f:
        writer = csv.writer(f)
        for row in mapped:
            writer.writerow([row[c] for c in master_header])

    print("=== append_green_book_1958.py stage ===")
    print(f"volume_title: {volume_title!r}")
    print(f"rows read={len(source_rows)} kept={len(kept)} "
          f"dropped(unanchored/hallucinated/no-xywh)={len(source_rows) - len(kept)}")
    print(f"hand-entered rows (Fixed or checked=TRUE): "
          f"{sum(1 for r in mapped if r['Fixed or checked'] == 'TRUE')}")
    print(f"staged:      {STAGED_CSV}")
    print(f"drift input: {DRIFT_INPUT}")
    print("\nNext, from /Users/joshhadro/github/directory-pipeline:")
    print("  .venv/bin/python collections/greenbook/detect_geographic_drift.py \\\n"
          f"    {DRIFT_INPUT} \\\n"
          f"    --aligned-dir {VOLUME_DIR} \\\n"
          f"    --output {DRIFT_OUTPUT}")
    print("then: python3 scripts/append_green_book_1958.py apply")


# ── apply ────────────────────────────────────────────────────────────────────

def merge_drift(master_header):
    """Return the staged 1958 rows with drift_* filled from the drift output."""
    staged = read_rows(STAGED_CSV)
    drifted = [r for r in read_rows(DRIFT_OUTPUT) if r["volume_id"] == VOLUME_ID]
    if len(drifted) != len(staged):
        sys.exit(f"ERROR: drift output has {len(drifted)} rows for {VOLUME_ID}, "
                 f"staged CSV has {len(staged)}. Re-run stage and drift.")
    for s, d in zip(staged, drifted):
        if (s["canvas_fragment"], s["name"]) != (d["canvas_fragment"], d["name"]):
            sys.exit(f"ERROR: drift output row order differs from staged CSV at "
                     f"{s['name']!r} / {d['name']!r}. Re-run stage and drift.")
        for col in DRIFT_COLUMNS:
            s[col] = d[col]
    missing = [c for c in master_header if c not in staged[0]]
    if missing:
        sys.exit(f"ERROR: staged CSV lacks master columns {missing}")
    return staged


def append_rows_to_master(master_header, rows):
    with open(MASTER_CSV, "a", newline="") as f:
        writer = csv.writer(f)
        for row in rows:
            writer.writerow([row[c] for c in master_header])


def dump_like(path, obj, original_text, **kwargs):
    """json.dump obj, keeping the original file's trailing-newline choice."""
    text = json.dumps(obj, **kwargs)
    if original_text.endswith("\n"):
        text += "\n"
    with open(path, "w") as f:
        f.write(text)


def load_sidecar_dims():
    """canvas_uri -> (w, h) and image id -> (w, h) from the aligned sidecars,
    the only trusted source of real canvas dims for this volume."""
    by_uri, by_image_id = {}, {}
    for path in glob.glob(os.path.join(VOLUME_DIR, "*_aligned.json")):
        with open(path) as f:
            d = json.load(f)
        uri, w, h = d.get("canvas_uri"), d.get("canvas_width"), d.get("canvas_height")
        if not uri or w is None or h is None:
            continue
        if (w, h) == (2560, 2560):
            sys.exit(f"ERROR: {os.path.basename(path)} still reports the 2560x2560 "
                     "placeholder; run tools/rescale_canvas_fragments.py first.")
        by_uri[uri] = (w, h)
        m = IMAGE_ID_RE.search(uri)
        if m:
            by_image_id[m.group(1)] = (w, h)
    return by_uri, by_image_id


def rewrite_and_patch_manifest(manifest, by_image_id):
    """Rewrite ids to the hadro.github.io convention the existing Green Book
    manifests use (e.g. manifests/8bf60a70-.../manifest.json: canvas ids are
    "<manifest_id>/canvas/<idx>", 0-based) and patch real dims onto every
    canvas, painting-annotation body and image service.

    Returns (manifest, canvas_index_by_base, unmatched_canvases).
    """
    out = dict(manifest)
    manifest_id = f"https://hadro.github.io/green-books/manifests/{VOLUME_ID}/manifest.json"
    out["id"] = manifest_id
    canvas_index_by_base, unmatched = {}, []

    for idx, canvas in enumerate(out.get("items", [])):
        canvas_id = f"{manifest_id}/canvas/{idx}"
        canvas["id"] = canvas_id
        image_id = None
        for ap_idx, ap in enumerate(canvas.get("items", [])):
            ap["id"] = f"{canvas_id}/page/{ap_idx}"
            for ann_idx, ann in enumerate(ap.get("items", [])):
                ann["id"] = f"{canvas_id}/page/{ap_idx}/annotation/{ann_idx}"
                ann["target"] = canvas_id
                body = ann.get("body", {})
                if body.get("id"):
                    canvas_index_by_base[body["id"]] = idx
                services = body.get("service") or []
                svc_id = services[0].get("id") if services else body.get("id")
                m = IMAGE_ID_RE.search(svc_id or "")
                if m:
                    image_id = m.group(1)

        dims = by_image_id.get(image_id) if image_id else None
        if dims is None:
            unmatched.append((idx, image_id))
            continue
        w, h = dims
        canvas["width"], canvas["height"] = w, h
        for ap in canvas.get("items", []):
            for ann in ap.get("items", []):
                body = ann.get("body", {})
                body["width"], body["height"] = w, h
                for svc in body.get("service") or []:
                    svc["width"], svc["height"] = w, h
    return out, canvas_index_by_base, unmatched


def write_manifest(manifest):
    out_path = os.path.join(MANIFESTS_DIR, VOLUME_ID, "manifest.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    # existing Green Book manifests: indent=2 with a trailing newline
    with open(out_path, "w") as f:
        json.dump(manifest, f, indent=2)
        f.write("\n")
    return out_path


def image_ids_of(rows):
    image_ids = set()
    for row in rows:
        m = IMAGE_ID_RE.search(row["canvas_fragment"].split("#")[0])
        if not m:
            sys.exit(f"ERROR: no NYPL image id in {row['canvas_fragment']}")
        image_ids.add(m.group(1))
    return image_ids


def check_image_ids_free(image_ids):
    with open(IMAGE_TO_VOLUME) as f:
        mapping = json.load(f)
    clashes = sorted(i for i in image_ids if mapping.get(i) not in (None, VOLUME_ID))
    if clashes:
        sys.exit(f"ERROR: image ids already mapped to another volume: {clashes[:5]}")


def update_image_to_volume(image_ids):
    with open(IMAGE_TO_VOLUME) as f:
        original = f.read()
    mapping = json.loads(original)
    added = sum(1 for i in image_ids if i not in mapping)
    for i in sorted(image_ids):
        mapping[i] = VOLUME_ID
    dump_like(IMAGE_TO_VOLUME, mapping, original, separators=(",", ":"))
    return added


def update_canvas_map(rows, by_uri, canvas_index_by_base):
    with open(CANVAS_MAP) as f:
        original = f.read()
    cmap = json.loads(original)
    bases = sorted({row["canvas_fragment"].split("#")[0] for row in rows})
    unmatched, added = [], 0
    for base in bases:
        dims = by_uri.get(base)
        position = canvas_index_by_base.get(base)
        m = IMAGE_ID_RE.search(base)
        if dims is None or position is None or not m:
            unmatched.append(base)
            continue
        image_id = m.group(1)
        # service base: strip the /full/!760,760/0/default.jpg suffix
        service_base = base.split(f"/{image_id}/", 1)[0] + f"/{image_id}"
        viewer_url = (f"https://digitalcollections.nypl.org/items/{VOLUME_ID}"
                      f"?canvasIndex={position}")
        if base not in cmap:
            added += 1
        cmap[base] = [service_base, dims[0], dims[1], viewer_url]
    dump_like(CANVAS_MAP, cmap, original, separators=(",", ":"))
    return added, bases, unmatched


def extract_current_field_meta():
    with open(EXPLORER_HTML) as f:
        for line in f:
            if "const FIELD_META" in line:
                rest = line[line.index("const FIELD_META") + len("const FIELD_META"):]
                json_str = rest[rest.index("=") + 1:].strip()
                return json.loads(json_str.rstrip(";"))
    return None


def recompute_field_meta(master_header):
    rows = read_rows(MASTER_CSV)
    total = len(rows)

    year_counts = {}
    for row in rows:
        year_counts[row["volume_year"]] = year_counts.get(row["volume_year"], 0) + 1
    year_pairs = [[y, c] for y, c in sorted(year_counts.items())]

    cat_counts = {}
    for row in rows:
        label = gb_category_group(row.get("category", ""))
        cat_counts[label] = cat_counts.get(label, 0) + 1
    cat_top25 = [[k, c] for k, c in sorted(cat_counts.items(), key=lambda kv: -kv[1])[:25]]

    fill_rate, cardinality = {}, {}
    for col in master_header:
        values = [(row.get(col) or "").strip() for row in rows]
        non_empty = [v for v in values if v]
        fill_rate[col] = round(len(non_empty) / total, 4) if total else 0.0
        cardinality[col] = len(set(non_empty))

    current = {e["name"]: {k: e.get(k) for k in ("fill_rate", "cardinality", "top_values")}
               for e in (extract_current_field_meta() or [])}

    out = {
        "total_rows": total,
        "volume_year": {"top_values": year_pairs, "cardinality": len(year_pairs)},
        "category_folded_top25": cat_top25,
        "category_folded_cardinality": len(cat_counts),
        "fill_rate": fill_rate,
        "cardinality": cardinality,
        "current_field_meta_from_explorer_html": current,
    }
    os.makedirs(SCRATCH_DIR, exist_ok=True)
    with open(FIELD_META_OUT, "w") as f:
        json.dump(out, f, indent=2)


def apply():
    master_header = read_master_header()
    check_not_already_present(master_header)
    rows = merge_drift(master_header)

    by_uri, by_image_id = load_sidecar_dims()
    manifest, canvas_index_by_base, unmatched_canvases = rewrite_and_patch_manifest(
        load_manifest(), by_image_id)
    # Validate everything before the first write.
    bases = {row["canvas_fragment"].split("#")[0] for row in rows}
    no_canvas = sorted(b for b in bases
                       if b not in canvas_index_by_base or b not in by_uri)
    if no_canvas:
        sys.exit(f"ERROR: {len(no_canvas)} canvas_fragment bases match no manifest "
                 f"canvas or sidecar, e.g. {no_canvas[0]}")
    image_ids = image_ids_of(rows)
    check_image_ids_free(image_ids)

    append_rows_to_master(master_header, rows)
    manifest_path = write_manifest(manifest)
    itv_added = update_image_to_volume(image_ids)
    cmap_added, cmap_bases, unmatched_cmap = update_canvas_map(
        rows, by_uri, canvas_index_by_base)
    recompute_field_meta(master_header)

    with open(MASTER_CSV, newline="") as f:
        new_total = sum(1 for _ in csv.reader(f)) - 1

    print("=== append_green_book_1958.py apply ===")
    print(f"rows appended: {len(rows)}  (Fixed or checked=TRUE: "
          f"{sum(1 for r in rows if r['Fixed or checked'] == 'TRUE')})")
    print(f"new green_book_entries_all.csv total: {new_total}")
    scores = {}
    for r in rows:
        scores[r["drift_score"]] = scores.get(r["drift_score"], 0) + 1
    print(f"drift_score distribution: {dict(sorted(scores.items()))}")
    print(f"image_to_volume.json: {itv_added} new keys ({len(image_ids)} pages)")
    print(f"canvas_map.json: {cmap_added} new keys ({len(cmap_bases)} pages)")
    if unmatched_cmap:
        print(f"WARNING: {len(unmatched_cmap)} canvas_map bases unmatched:")
        for b in unmatched_cmap:
            print(f"  {b}")
    if unmatched_canvases:
        print(f"note: {len(unmatched_canvases)} manifest canvases have no sidecar "
              "and keep placeholder dims (no entries on them):")
        for idx, image_id in unmatched_canvases:
            print(f"  canvas {idx} (image {image_id})")
    print(f"manifest written: {manifest_path}")
    print(f"field meta recompute: {FIELD_META_OUT}")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("phase", choices=["stage", "apply"])
    args = p.parse_args()
    stage() if args.phase == "stage" else apply()


if __name__ == "__main__":
    main()
