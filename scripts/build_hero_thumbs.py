#!/usr/bin/env python3
"""Build the pre-crunched hero thumbnail set for all-volumes.html.

Selects a stratified random subset of entries (spread evenly across volumes,
deduped by business name + city) and crops each entry's thumbnail from the
LOCAL full-page scans produced by directory-pipeline — zero requests to NYPL.
The crop geometry is a pixel-exact port of thumbUrl(row, 'left') in
all-volumes.html, so a pre-crunched thumb is identical (modulo the local
masters' resolution) to what the live IIIF path would have requested.

Output: <out-dir>/<sha1(canvas_fragment)[:12]>.jpg + <out-dir>/manifest.json,
consumed by gbUpdateHero(). Filenames are content-addressed so re-runs that
re-select an entry produce no diff for it.

Usage (from the green-books repo root):

  /Users/joshhadro/github/directory-pipeline/.venv/bin/python \
      scripts/build_hero_thumbs.py \
      --images-dir /Users/joshhadro/github/directory-pipeline/output/green_books_and_related \
      --count 300 --seed 42 [--dry-run]

Refresh the set later by re-running with a different --seed and committing.
Requires Pillow (the directory-pipeline venv has it).

Curation: to remove a bad thumb (misaligned xywh box in the source data),

  python3 scripts/build_hero_thumbs.py --prune <id> [<id> ...]

which deletes it from hero-thumbs/ + manifest.json AND records it in
scripts/hero_thumbs_exclude.txt so future rebuilds (any --seed) never
re-select that entry. No --images-dir needed for pruning.
"""

import argparse
import csv
import hashlib
import json
import os
import random
import re
import shutil
import sys
from datetime import datetime, timezone

GB_CSV = "green_book_entries_all.csv"
TG_CSV = "travel_guides_all.csv"
GB_MAP = "canvas_map.json"
TG_MAP = "travel_guides_canvas_map.json"
EXCLUDE_FILE = os.path.join("scripts", "hero_thumbs_exclude.txt")

PAGE_IMG_RE = re.compile(r"^\d{4}_(\d+)\.jpg$")
IMAGE_ID_RE = re.compile(r"/iiif/3/(\d+)")


def canvas_id(cf):
    return cf.split("#")[0]


def thumb_id(cf):
    return hashlib.sha1(cf.encode()).hexdigest()[:12]


def load_excluded(repo_root):
    """Thumb ids (or full canvas_fragments) listed one per line in
    scripts/hero_thumbs_exclude.txt; # starts a comment."""
    path = os.path.join(repo_root, EXCLUDE_FILE)
    excluded = set()
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                token = line.split("#")[0].strip()
                if token:
                    excluded.add(token)
    return excluded


def prune(repo_root, out_dir, ids):
    """Remove thumbs from hero-thumbs/ + manifest.json and record them in the
    exclude file so no future rebuild re-selects those entries."""
    manifest_path = os.path.join(out_dir, "manifest.json")
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    by_id = {t["id"]: t for t in manifest["thumbs"]}
    unknown = [i for i in ids if i not in by_id]
    if unknown:
        sys.exit(f"not in manifest: {', '.join(unknown)}")
    exclude_path = os.path.join(repo_root, EXCLUDE_FILE)
    already = load_excluded(repo_root)
    with open(exclude_path, "a", encoding="utf-8") as f:
        for i in ids:
            t = by_id[i]
            jpg = os.path.join(out_dir, t["file"])
            if os.path.exists(jpg):
                os.remove(jpg)
            if i not in already:
                f.write(f"{i}  # {t['name']} | {t['city']} {t['state']} {t['volume_year']}\n")
            print(f"pruned {i}: {t['name']} | {t['city']} {t['state']} {t['volume_year']}")
    manifest["thumbs"] = [t for t in manifest["thumbs"] if t["id"] not in ids]
    manifest["count"] = len(manifest["thumbs"])
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)
    print(f"manifest now has {manifest['count']} thumbs; ids recorded in {EXCLUDE_FILE}")


def parse_xywh(cf):
    part = cf.split("#xywh=")[1]
    vals = [float(v) for v in part.split(",")]
    if len(vals) != 4:
        raise ValueError("bad xywh")
    return vals


def crop_box(xywh, cw, ch):
    """Port of thumbUrl(row, 'left') in all-volumes.html — left-anchored crop
    box in canvas pixel space. Returns (rx, ry, rw, rh)."""
    x, y, w, h = xywh
    pad_v = max(h, 60)
    min_w = 600
    rx = max(0, x - 8)
    rw = min(cw, rx + max(min_w, w + 240)) - rx
    ry = max(0, y - pad_v)
    rh = (y + h + pad_v) - ry
    return rx, ry, rw, rh


def pct_url(svc_base, box, cw, ch, tw=400):
    """The exact live URL thumbUrl() would request — used for parity checks
    and as the --iiif fallback download URL."""
    rx, ry, rw, rh = box
    xp, yp = f"{rx / cw * 100:.4f}", f"{ry / ch * 100:.4f}"
    wp, hp = f"{rw / cw * 100:.4f}", f"{rh / ch * 100:.4f}"
    return f"{svc_base}/pct:{xp},{yp},{wp},{hp}/{tw},/0/default.jpg"


def load_candidates(repo_root, canvas_map):
    """Rows passing the same filter gbUpdateHero() applies, except the canvas
    MUST resolve with usable dimensions (the live code's default-true branch
    for unmapped canvases only ever yields imageless cards)."""
    candidates = []
    for csv_name, publication in ((GB_CSV, "green_book"), (TG_CSV, "travel_guide")):
        path = os.path.join(repo_root, csv_name)
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                cf = (row.get("canvas_fragment") or "").strip()
                if not (row.get("address") or "").strip() or "#xywh=" not in cf:
                    continue
                svc = canvas_map.get(canvas_id(cf))
                if not svc or not svc[1] or not svc[2]:
                    continue
                try:
                    xywh = parse_xywh(cf)
                except (ValueError, IndexError):
                    continue
                if xywh[2] / svc[1] > 0.45:
                    continue
                if not (row.get("name") or "").strip():
                    continue
                candidates.append({"row": row, "cf": cf, "svc": svc,
                                   "xywh": xywh, "publication": publication})
    return candidates


def select(candidates, count, seed, excluded=()):
    """Stratified draw: round-robin one entry per volume until count is met,
    deduped pool-wide by name|city so relisted businesses can't crowd out
    variety. Volumes with few eligible rows simply exhaust; the round-robin
    redistributes their share automatically. Entries in the exclude file
    (curated-out bad crops) are never selected."""
    rng = random.Random(seed)
    by_volume = {}
    for c in candidates:
        if thumb_id(c["cf"]) in excluded or c["cf"] in excluded:
            continue
        by_volume.setdefault(c["row"]["volume_id"], []).append(c)
    for pool in by_volume.values():
        rng.shuffle(pool)
    volumes = sorted(by_volume)
    rng.shuffle(volumes)
    seen, picked = set(), []
    while len(picked) < count:
        progressed = False
        for vid in volumes:
            if len(picked) >= count:
                break
            pool = by_volume[vid]
            while pool:
                c = pool.pop()
                key = c["row"]["name"] + "|" + (c["row"].get("city") or "")
                if key in seen:
                    continue
                seen.add(key)
                picked.append(c)
                progressed = True
                break
        if not progressed:
            break
    return picked


def index_page_images(images_dir):
    """Map NYPL image ID -> local page-image path (NNNN_<imageID>.jpg)."""
    idx = {}
    for dirpath, dirnames, filenames in os.walk(images_dir):
        dirnames[:] = [d for d in dirnames if not d.endswith("_cache") and d != ".claude"]
        for fn in filenames:
            m = PAGE_IMG_RE.match(fn)
            if m:
                idx.setdefault(m.group(1), os.path.join(dirpath, fn))
    return idx


def build_thumb(c, image_path, out_path, max_bytes):
    """Crop the entry's box from the local page scan (scaled from canvas
    coordinates to the local master's resolution) and save a 400px-wide JPEG
    stepped down in quality until it fits max_bytes."""
    from PIL import Image
    cw, ch = c["svc"][1], c["svc"][2]
    rx, ry, rw, rh = crop_box(c["xywh"], cw, ch)
    with Image.open(image_path) as im:
        sx, sy = im.width / cw, im.height / ch
        box = (round(rx * sx), round(ry * sy),
               round((rx + rw) * sx), round((ry + rh) * sy))
        crop = im.crop(box).convert("RGB")
        tw = 400
        if crop.width > tw:
            crop = crop.resize((tw, max(1, round(crop.height * tw / crop.width))),
                               Image.LANCZOS)
        for quality in (85, 75, 65, 55, 45):
            crop.save(out_path, "JPEG", quality=quality, optimize=True)
            if os.path.getsize(out_path) <= max_bytes:
                break


def download_thumb(c, out_path, rate):
    """--iiif fallback for entries whose local page scan is missing: fetch the
    exact live crop URL from NYPL, politely (sequential, rate-limited)."""
    import time
    import urllib.request
    cw, ch = c["svc"][1], c["svc"][2]
    url = pct_url(c["svc"][0], crop_box(c["xywh"], cw, ch), cw, ch)
    req = urllib.request.Request(url, headers={
        "User-Agent": "green-books-hero-thumb-builder/1 (+https://github.com/hadro/green-books)"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = resp.read()
            with open(out_path, "wb") as f:
                f.write(data)
            time.sleep(rate)
            return True
        except Exception as e:  # noqa: BLE001 — retry 5xx/network, give up on the rest
            code = getattr(e, "code", None)
            if code is not None and 400 <= code < 500:
                print(f"  skip ({code}): {url}", file=sys.stderr)
                return False
            time.sleep(2 ** (attempt + 1))
    print(f"  gave up after retries: {url}", file=sys.stderr)
    return False


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--images-dir",
                    help="directory-pipeline output tree containing NNNN_<imageID>.jpg page scans")
    ap.add_argument("--prune", nargs="+", metavar="ID",
                    help="remove these thumb ids from the built set and add them to the exclude file")
    ap.add_argument("--count", type=int, default=300)
    ap.add_argument("--out-dir", default="hero-thumbs")
    ap.add_argument("--max-bytes", type=int, default=40960)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--rate", type=float, default=1.0,
                    help="seconds between requests in --iiif fallback mode")
    ap.add_argument("--iiif", action="store_true",
                    help="download crops from NYPL IIIF for entries with no local page scan")
    ap.add_argument("--dry-run", action="store_true",
                    help="select and report only; write nothing")
    args = ap.parse_args()

    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_dir_resolved = args.out_dir if os.path.isabs(args.out_dir) else os.path.join(repo_root, args.out_dir)
    if args.prune:
        prune(repo_root, out_dir_resolved, args.prune)
        return
    if not args.images_dir:
        ap.error("--images-dir is required (except with --prune)")

    with open(os.path.join(repo_root, GB_MAP), encoding="utf-8") as f:
        canvas_map = json.load(f)
    with open(os.path.join(repo_root, TG_MAP), encoding="utf-8") as f:
        canvas_map.update(json.load(f))

    candidates = load_candidates(repo_root, canvas_map)
    picked = select(candidates, args.count, args.seed, load_excluded(repo_root))
    images = index_page_images(args.images_dir)

    with_local = missing = 0
    per_volume, per_category = {}, {}
    for c in picked:
        image_id = IMAGE_ID_RE.search(c["cf"]).group(1)
        c["image_id"] = image_id
        c["local"] = images.get(image_id)
        with_local += bool(c["local"])
        missing += not c["local"]
        r = c["row"]
        vol = f'{r.get("volume_year") or "?"} {r["volume_id"][:8]}'
        per_volume[vol] = per_volume.get(vol, 0) + 1
        cat = (r.get("category") or "(none)").strip()[:40]
        per_category[cat] = per_category.get(cat, 0) + 1

    print(f"candidates: {len(candidates)}  selected: {len(picked)}  "
          f"local page scan: {with_local}  missing: {missing}")
    print(f"volumes covered: {len(per_volume)}")
    for vol in sorted(per_volume):
        print(f"  {vol}: {per_volume[vol]}")
    print("top categories:")
    for cat, n in sorted(per_category.items(), key=lambda kv: -kv[1])[:15]:
        print(f"  {n:4d}  {cat}")
    print("sample live-URL parity (compare against thumbUrl() in all-volumes.html):")
    for c in picked[:5]:
        cw, ch = c["svc"][1], c["svc"][2]
        print(f"  {c['cf']}\n    -> {pct_url(c['svc'][0], crop_box(c['xywh'], cw, ch), cw, ch)}")

    if args.dry_run:
        return

    out_dir = out_dir_resolved
    staging = out_dir + ".staging"
    shutil.rmtree(staging, ignore_errors=True)
    os.makedirs(staging)
    thumbs, skipped = [], 0
    for i, c in enumerate(picked, 1):
        tid = thumb_id(c["cf"])
        out_path = os.path.join(staging, tid + ".jpg")
        ok = False
        if c["local"]:
            build_thumb(c, c["local"], out_path, args.max_bytes)
            ok = True
        elif args.iiif:
            ok = download_thumb(c, out_path, args.rate)
        if not ok:
            skipped += 1
            continue
        r = c["row"]
        year = r.get("volume_year") or ""
        thumbs.append({
            "id": tid,
            "file": tid + ".jpg",
            "canvas_fragment": c["cf"],
            "name": r["name"],
            "city": r.get("city") or "",
            "state": r.get("state") or "",
            "volume_year": int(year) if str(year).isdigit() else year,
            "category": r.get("category") or "",
            "publication": c["publication"],
        })
        if i % 50 == 0:
            print(f"  {i}/{len(picked)}...")

    manifest = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "generator_version": 1,
        "seed": args.seed,
        "count": len(thumbs),
        "thumbs": thumbs,
    }
    with open(os.path.join(staging, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)

    shutil.rmtree(out_dir, ignore_errors=True)
    shutil.move(staging, out_dir)
    total = sum(os.path.getsize(os.path.join(out_dir, t["file"])) for t in thumbs)
    print(f"wrote {len(thumbs)} thumbs ({total / 1e6:.1f} MB) + manifest.json to {out_dir}"
          + (f"; skipped {skipped}" if skipped else ""))


if __name__ == "__main__":
    main()
