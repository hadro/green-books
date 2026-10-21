#!/usr/bin/env python3
"""Build alignment_ground_truth.json — every hand-verified OCR alignment, preserved.

Why this file exists
--------------------
`directory-pipeline`'s alignment review UI (`pipeline/review_alignment.py`) writes
corrected lines back into `*_aligned.json` with `"confidence": "manual"`. Those
lines are the ONLY human-verified data anywhere in this project. Everything else —
Surya boxes, Gemini OCR text, alignments, entries, thumbnails — is reproducible
from the page images. The manual corrections are not: they exist in exactly one
place, inside a gitignored `output/` tree, and `align_ocr.py --force` rewrites
those files wholesale without reading them first (align_ocr.py:1255 skips when the
file exists; on the --force path align_image() builds its result purely from Surya
+ Gemini text and calls out_path.write_text(), so every manual line is lost).

So this script lifts them out into a small, committed file before anything can
overwrite them. It is a rescue, not a pipeline stage.

What it is good for
-------------------
More than a backup. These records are a ground-truth set: for each one we know
which bounding box a human decided belonged to which line of text. That makes
every future claim about alignment quality *measurable* rather than argued —
re-align, then check how often the machine reproduces the human's box. Without
it, "the new aligner is better" can only be evidenced by coverage (how many lines
got a box at all), which cannot see whether a box is on the right line.

Note the set is deliberately skewed: pages get hand-corrected precisely when the
aligner failed on them, and roughly 70% of the Green Book records come from the
1966-67 edition alone. It is a hard-case benchmark, not a representative sample,
and a score against it should be read that way.

Provenance kept per record
--------------------------
`page_mode` distinguishes two quite different kinds of work, because the review UI
supports both (review_alignment.py:308-317):

  full     the page was cleared and rebuilt from scratch — every line on it is
           hand-placed (the UI's `clear_existing` path)
  partial  targeted fixes merged into an otherwise machine-produced page

`canvas_width`/`canvas_height` are kept alongside `bbox` so a `canvas_fragment`
stays re-derivable if canvas dimensions are ever corrected upstream.

Usage:
    python3 scripts/extract_manual_alignments.py [--output-root DIR] [--check]

--check verifies the committed alignment_ground_truth.json still matches what is
on disk and exits non-zero if it has drifted, without writing anything.
"""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

DEFAULT_OUTPUT_ROOT = Path("/Users/joshhadro/github/directory-pipeline/output")
TARGET = Path(__file__).resolve().parent.parent / "alignment_ground_truth.json"

ALIGNED_RE = re.compile(r"^(?P<stem>.+?)_(?P<slug>gemini[-\w.]+)_aligned\.json$")


def collect(output_root: Path) -> dict:
    """Walk the pipeline output tree and lift out every manual line."""
    records = []
    pages = 0
    for path in sorted(output_root.rglob("*_aligned.json")):
        m = ALIGNED_RE.match(path.name)
        if not m:
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue

        lines = data.get("lines", [])
        manual = [ln for ln in lines if ln.get("confidence") == "manual"]
        if not manual:
            continue

        rel = path.relative_to(output_root)
        # output/<collection>/<volume>/<page>  — collection may be one level deep
        parts = rel.parts
        collection = parts[0] if len(parts) > 1 else ""
        # _ocr_backups holds superseded copies of aligned trees (…_OLD, …_PREFIX).
        # Their manual lines are stale duplicates of work that lives, in its
        # current form, in the live tree — carrying them here would mean the
        # ground truth disagreed with itself.
        if collection == "_ocr_backups":
            continue
        pages += 1
        volume = parts[-2] if len(parts) > 2 else ""
        page_mode = "full" if len(manual) == len(lines) else "partial"

        for ln in manual:
            records.append({
                "collection": collection,
                "volume": volume,
                "image": data.get("image") or f"{m.group('stem')}.jpg",
                "aligned_model": m.group("slug"),
                "page_mode": page_mode,
                "canvas_width": data.get("canvas_width"),
                "canvas_height": data.get("canvas_height"),
                "bbox": ln.get("bbox"),
                "canvas_fragment": ln.get("canvas_fragment"),
                "text": ln.get("gemini_text", ""),
            })

    records.sort(key=lambda r: (r["collection"], r["volume"], r["image"],
                                (r["bbox"] or [0, 0, 0, 0])[1],
                                (r["bbox"] or [0, 0, 0, 0])[0]))
    by_collection = Counter(r["collection"] for r in records)
    by_mode = Counter(r["page_mode"] for r in records)
    return {
        "_comment": (
            "Hand-verified OCR alignments lifted out of directory-pipeline's "
            "gitignored output/ tree. The only human-verified data in this "
            "project and the only artifact not reproducible from the page "
            "images. Rebuild with scripts/extract_manual_alignments.py."
        ),
        "pages": pages,
        "lines": len(records),
        "lines_by_collection": dict(by_collection.most_common()),
        "lines_by_page_mode": dict(by_mode.most_common()),
        "records": records,
    }


def render(built: dict) -> str:
    """Serialise with one record per line.

    Pretty-printing the whole structure would put each bbox coordinate on its own
    line and triple the file size; a single compact blob would make every rebuild
    a one-line diff. One record per line keeps it small AND lets git show exactly
    which alignments changed.
    """
    head = {k: v for k, v in built.items() if k != "records"}
    out = ["{"]
    for key, value in head.items():
        out.append(f"  {json.dumps(key)}: {json.dumps(value, ensure_ascii=False)},")
    out.append('  "records": [')
    rows = [json.dumps(r, ensure_ascii=False, sort_keys=True) for r in built["records"]]
    for i, row in enumerate(rows):
        out.append(f"    {row}" + ("," if i < len(rows) - 1 else ""))
    out.append("  ]")
    out.append("}")
    return "\n".join(out) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT,
                    help="directory-pipeline's output/ tree (default: %(default)s)")
    ap.add_argument("--check", action="store_true",
                    help="verify the committed file matches disk; write nothing")
    args = ap.parse_args()

    if not args.output_root.is_dir():
        print(f"error: {args.output_root} is not a directory", file=sys.stderr)
        return 2

    built = collect(args.output_root)
    payload = render(built)

    if args.check:
        if not TARGET.exists():
            print(f"FAIL: {TARGET.name} does not exist", file=sys.stderr)
            return 1
        if TARGET.read_text(encoding="utf-8") != payload:
            current = json.loads(TARGET.read_text(encoding="utf-8"))
            print(f"FAIL: {TARGET.name} has drifted — "
                  f"committed {current.get('lines')} lines / {current.get('pages')} pages, "
                  f"disk has {built['lines']} lines / {built['pages']} pages",
                  file=sys.stderr)
            return 1
        print(f"OK: {TARGET.name} matches disk "
              f"({built['lines']} lines across {built['pages']} pages)")
        return 0

    TARGET.write_text(payload, encoding="utf-8")
    print(f"wrote {TARGET.name}: {built['lines']} manual lines "
          f"across {built['pages']} pages ({len(payload) / 1024:.0f} KB)")
    for k, v in built["lines_by_collection"].items():
        print(f"   {v:>6}  {k}")
    print(f"   page mode: {built['lines_by_page_mode']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
