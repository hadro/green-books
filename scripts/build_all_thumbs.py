#!/usr/bin/env python3
"""Build a pre-cropped thumbnail for EVERY entry in the merged corpus.

Unlike build_hero_thumbs.py (which selects a curated ~300-thumb sample for the
featured cards), this crops all ~109k entries across both CSVs and lays them out
content-addressed and sharded for hosting on a CDN (Hugging Face). It reuses the
pixel-exact crop geometry from build_hero_thumbs.py so a thumb here is identical
to what the live IIIF path in the explorers would have requested.

Output: <out-dir>/<tid[:2]>/<tid>.<ext>  where tid = sha1(canvas_fragment)[:12].
Sharded by the first two hex chars (256 shards) so no directory holds 100k files.
Content-addressed → deterministic and resumable: an existing thumb is skipped, so
re-runs only fill gaps.

Local page scans are matched by the CSV `image` column (an exact filename for
both NYPL, `0002_5207704.jpg`, and LOC, `0007_service:gdc:...:00007.jpg`), which
is what lets the LOC 1946 volume come along for free — no per-source regex.

Usage (from the green-books repo root):

  /Users/joshhadro/github/directory-pipeline/.venv/bin/python \
      scripts/build_all_thumbs.py \
      --images-dir /Users/joshhadro/github/directory-pipeline/output/green_books_and_related \
      --images-dir /Users/joshhadro/github/directory-pipeline/output/the_negro_motorist_green_book_2016298176/2016298176 \
      --format webp --jobs 7

Pilot a couple volumes first with --only-volume <id> [--only-volume <id> ...].
Requires Pillow (the directory-pipeline venv has it).
"""

import argparse
import csv
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from multiprocessing import Pool

# Reuse the crop primitives — same geometry as the hero builder / thumbUrl().
from build_hero_thumbs import (
    GB_CSV, TG_CSV, GB_MAP, TG_MAP,
    canvas_id, thumb_id, parse_xywh, crop_box,
)

csv.field_size_limit(1 << 22)
TW = 400  # output thumb width, matches build_hero_thumbs / thumbUrl()


def load_canvas_map(repo_root):
    with open(os.path.join(repo_root, GB_MAP), encoding="utf-8") as f:
        cmap = json.load(f)
    with open(os.path.join(repo_root, TG_MAP), encoding="utf-8") as f:
        cmap.update(json.load(f))
    return cmap


def load_candidates(repo_root, canvas_map, only_volumes=None):
    """Every row that can actually be cropped: has an `#xywh=` fragment whose
    canvas resolves in the map with usable dimensions, valid xywh, and a non-empty
    `image` filename to join against the local scans."""
    cands = []
    for csv_name, publication in ((GB_CSV, "green_book"), (TG_CSV, "travel_guide")):
        with open(os.path.join(repo_root, csv_name), newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if only_volumes and row.get("volume_id") not in only_volumes:
                    continue
                cf = (row.get("canvas_fragment") or "").strip()
                if "#xywh=" not in cf:
                    continue
                svc = canvas_map.get(canvas_id(cf))
                if not svc or not svc[1] or not svc[2]:
                    continue
                try:
                    xywh = parse_xywh(cf)
                except (ValueError, IndexError):
                    continue
                if not (row.get("image") or "").strip():
                    continue
                cands.append({"cf": cf, "svc": svc, "xywh": xywh,
                              "image": os.path.basename(row["image"].strip()),
                              "volume_id": row.get("volume_id") or "?",
                              "publication": publication})
    return cands


def index_by_basename(images_dirs):
    """Map page-scan basename -> full path across all --images-dir roots. Keys on
    the exact filename, so the CSV `image` value joins directly and the
    `_viz.jpg`/OCR-overlay siblings are never matched."""
    idx = {}
    for root in images_dirs:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if not d.endswith("_cache") and d != ".claude"]
            for fn in filenames:
                if fn.endswith(".jpg"):
                    idx.setdefault(fn, os.path.join(dirpath, fn))
    return idx


def _crop_page(job):
    """Decode one page scan once, then crop every entry that lives on it. The
    corpus averages ~18 entries per page (the LOC volume ~41), so opening the
    2048px master once instead of per-entry is the main throughput win.
    `items` = list of (svc, xywh, out_path). Returns (built, [error strings])."""
    image_path, items, fmt, quality, max_bytes = job
    from PIL import Image
    try:
        im = Image.open(image_path)
        im.load()
    except Exception as e:  # noqa: BLE001
        return (0, [f"{e!r} [open {os.path.basename(image_path)}]"])
    iw, ih = im.width, im.height
    built, errs = 0, []
    for svc, xywh, out_path in items:
        try:
            cw, ch = svc[1], svc[2]
            rx, ry, rw, rh = crop_box(xywh, cw, ch)
            sx, sy = iw / cw, ih / ch
            box = (round(rx * sx), round(ry * sy),
                   round((rx + rw) * sx), round((ry + rh) * sy))
            crop = im.crop(box).convert("RGB")
            if crop.width > TW:
                crop = crop.resize((TW, max(1, round(crop.height * TW / crop.width))),
                                   Image.LANCZOS)
            if fmt == "webp":
                crop.save(out_path, "WEBP", quality=quality, method=6)
            else:
                for q in (85, 75, 65, 55, 45):
                    crop.save(out_path, "JPEG", quality=q, optimize=True)
                    if os.path.getsize(out_path) <= max_bytes:
                        break
            built += 1
        except Exception as e:  # noqa: BLE001 — one bad box shouldn't sink the page
            errs.append(f"{e!r} [{out_path}]")
    im.close()
    return (built, errs)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--images-dir", action="append", default=[], metavar="DIR",
                    help="page-scan tree; repeatable (NYPL/travel-guide root + the LOC folder)")
    ap.add_argument("--out-dir", default="thumbs")
    ap.add_argument("--format", choices=["webp", "jpeg"], default="webp")
    ap.add_argument("--quality", type=int, default=75)
    ap.add_argument("--max-bytes", type=int, default=40960, help="JPEG size cap (ignored for webp)")
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--only-volume", action="append", default=[], metavar="VID",
                    help="restrict to these volume_ids (pilot); repeatable")
    ap.add_argument("--dry-run", action="store_true", help="report coverage only; write nothing")
    args = ap.parse_args()

    if not args.images_dir:
        ap.error("at least one --images-dir is required")
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_dir = args.out_dir if os.path.isabs(args.out_dir) else os.path.join(repo_root, args.out_dir)
    ext = "webp" if args.format == "webp" else "jpg"
    only = set(args.only_volume) or None

    canvas_map = load_canvas_map(repo_root)
    cands = load_candidates(repo_root, canvas_map, only)
    index = index_by_basename(args.images_dir)

    # Resolve each candidate to a local scan + output path; dedupe by output path
    # (content-addressed, so relisted businesses collapse to one file).
    tasks, seen_out = {}, set()
    per_vol_total, per_vol_missing = {}, {}
    missing_scan = skipped_existing = 0
    for c in cands:
        vid = c["volume_id"]
        per_vol_total[vid] = per_vol_total.get(vid, 0) + 1
        path = index.get(c["image"])
        if not path:
            missing_scan += 1
            per_vol_missing[vid] = per_vol_missing.get(vid, 0) + 1
            continue
        tid = thumb_id(c["cf"])
        out_path = os.path.join(out_dir, tid[:2], f"{tid}.{ext}")
        if out_path in seen_out:
            continue
        seen_out.add(out_path)
        if os.path.exists(out_path):
            skipped_existing += 1
            continue
        tasks[out_path] = (path, c["svc"], c["xywh"], out_path)

    print(f"candidates: {len(cands)}  unique thumbs: {len(seen_out)}  "
          f"to build: {len(tasks)}  already on disk: {skipped_existing}  "
          f"missing local scan: {missing_scan}")
    print(f"volumes: {len(per_vol_total)}")
    for vid in sorted(per_vol_total, key=lambda v: -per_vol_missing.get(v, 0))[:12]:
        miss = per_vol_missing.get(vid, 0)
        flag = f"  <-- {miss} missing scans" if miss else ""
        print(f"  {vid[:24]:24s}  {per_vol_total[vid]:6d} entries{flag}")

    if args.dry_run or not tasks:
        return

    for i in range(256):
        os.makedirs(os.path.join(out_dir, f"{i:02x}"), exist_ok=True)

    # Group the crops by source page so each master is decoded exactly once.
    by_page = defaultdict(list)
    for path, svc, xywh, out_path in tasks.values():
        by_page[path].append((svc, xywh, out_path))
    jobs = [(path, items, args.format, args.quality, args.max_bytes)
            for path, items in by_page.items()]
    print(f"dispatching {len(tasks)} crops across {len(jobs)} page scans, {args.jobs} workers")

    built = errors = 0
    err_samples = []
    done_crops = 0
    with Pool(args.jobs) as pool:
        for i, (n_ok, errs) in enumerate(
                pool.imap_unordered(_crop_page, jobs, chunksize=1), 1):
            built += n_ok
            errors += len(errs)
            for e in errs:
                if len(err_samples) < 10:
                    err_samples.append(e)
            done_crops += n_ok + len(errs)
            if i % 200 == 0:
                print(f"  page {i}/{len(jobs)}  crops built={built} errors={errors}")

    total_bytes = 0
    for dirpath, _, filenames in os.walk(out_dir):
        for fn in filenames:
            if fn.endswith(f".{ext}"):
                total_bytes += os.path.getsize(os.path.join(dirpath, fn))
    print(f"\nbuilt {built} new thumbs ({errors} errors); "
          f"pool now {total_bytes / 1e6:.1f} MB on disk in {out_dir}")
    for s in err_samples:
        print(f"  ERR {s}", file=sys.stderr)

    stats = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "format": args.format, "quality": args.quality,
        "candidates": len(cands), "unique_thumbs": len(seen_out),
        "built_this_run": built, "errors": errors,
        "missing_local_scan": missing_scan,
        "per_volume_missing": per_vol_missing,
    }
    with open(os.path.join(out_dir, "_build_stats.json"), "w", encoding="utf-8") as f:
        json.dump(stats, f, ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
