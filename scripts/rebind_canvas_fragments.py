#!/usr/bin/env python3
"""Re-bind every published entry to its aligned line using the corrected matcher.

Why this exists
---------------
The `canvas_fragment` in the published CSVs was written by the old entry→line
matcher in `directory-pipeline`, which fell through to any string field over three
characters. In a Green Book an entry's `category` *is* the printed section heading,
so ~1,200 entries point at a heading or a neighbouring listing rather than at
themselves. `utils/entry_binding.py` replaces that matcher; this script applies it
to the data already published.

It runs entirely offline: no Gemini calls, no IIIF fetches, no image reads.

Which alignment it binds against
--------------------------------
The **pre-re-align** tree, restored from
`output/_ocr_backups/green_books_aligned_2026-09-04/`. That is deliberate. The
2026-09-04 re-alignment was measured and left unapplied — it moves 98.7% of entry
boxes not at all while costing ~12,800 thumbnail rebuilds (see
`docs/alignment-audit-2026-09-04.md`). Binding against the backup keeps this change
to the one thing that actually repairs the reported bug.

The live pipeline tree is never read or written.

What it does with an entry it cannot place
------------------------------------------
Asks an arbiter that had no part in producing the box. The existing fragment is
scored against **Surya's own reading of the pixels inside that bbox**; it is kept
if it clears `--keep-floor`, and blanked to the bare canvas URI otherwise. Either
way the row goes to the review report.

An earlier version of this script kept every unplaceable row's box on the
reasoning that some are correct. Measured, that reasoning was wrong: boxes on
refused rows average 0.36 against 0.84 for rows the matcher does place, and 44%
of them are badly wrong. Keeping them preserves roughly one correct box per
two-and-a-half actively misleading ones — and the two are not equivalent. A
missing box is a non-answer; a wrong box is a false statement, pointing the
reader at TAVERNS when the entry is a hotel, which is the bug this whole exercise
exists to fix.

Surya is the right arbiter for the same reason it settled the re-alignment
question: the matcher's score and the old binder's substring match are both
judgments about the aligned text, while Surya read those pixels once, before
either existed. It is independent, but it is *not clean*, and the floor is set
where it is because of how it fails:

  >=0.70      boxes are right. Reviewed by hand: 5/5 correct. These rows were
              refused only because a short identity ("YMCA", "NCCJ") cannot clear
              the matcher's minimum-overlap guard — the guard is right to decline
              to verify them, and the boxes happen to be fine.
  0.50-0.70   boxes are UNRELIABLE, and an earlier 0.60 floor kept them. Green Book
              entries are formulaic ("Mrs. X — Guest Home"), so shared boilerplate
              carries the score while the distinguishing surname is a small share
              of it: "Mrs. Sallie Price-Guest Home" scores 0.68 against
              "Mrs. Charlotte Strong—Guest Home". Different person, kept box.
  below 0.50  mixed, and Surya's own fault as much as the box's. It transcribes
              dot leaders as '★MAGNOLIA HOTEL .....................' and loses
              everything after them — 64% of dot-leader lines in a 400-page sample.
              Dot leaders are the dominant listing format, so correct boxes are
              systematically under-scored here. They are blanked anyway: the review
              queue catches them, and a wrong box makes a false claim to a reader
              while a missing box merely fails to help.

That asymmetry is the whole basis of the floor. It is deliberately conservative.

Usage:
    python3 scripts/rebind_canvas_fragments.py --dry-run     # report, write nothing
    python3 scripts/rebind_canvas_fragments.py               # rewrite the CSVs
    python3 scripts/rebind_canvas_fragments.py --review-out review.csv
"""

import argparse
import collections
import csv
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PIPELINE = Path("/Users/joshhadro/github/directory-pipeline")
sys.path.insert(0, str(PIPELINE))
csv.field_size_limit(10 ** 9)

from utils.entry_binding import (  # noqa: E402
    bind_entries, identity_text, identity_tokens, score, tokens,
)

CSVS = ("green_book_entries_all.csv", "travel_guides_all.csv")
ALIGNED_RE = re.compile(r"_(gemini[-\w.]+)_aligned\.json$")
XYWH = re.compile(r"#xywh=\d+,\d+,\d+,\d+")


def surya_index(root: Path) -> dict:
    idx = {}
    for p in root.rglob("*_surya.json"):
        if "_ocr_backups" in str(p):
            continue
        idx.setdefault(p.name[: -len("_surya.json")] + ".jpg", p)
    return idx


def surya_text_at(smap: dict | None, bbox) -> str | None:
    """Surya's own reading inside this bbox, matched on line centre."""
    if not smap or not bbox or len(bbox) != 4:
        return None
    key = (round((bbox[0] + bbox[2]) / 2), round((bbox[1] + bbox[3]) / 2))
    if key in smap:
        return smap[key]
    best, dist = None, 1e9
    for c in smap:
        d = abs(c[0] - key[0]) + abs(c[1] - key[1])
        if d < dist:
            best, dist = c, d
    return smap[best] if dist <= 6 else None


def index_aligned(root: Path) -> dict:
    idx = collections.defaultdict(list)
    for p in root.rglob("*_aligned.json"):
        if "_ocr_backups" in str(p):
            continue
        idx[ALIGNED_RE.sub("", p.name) + ".jpg"].append(p)
    return idx


def coverage(doc: dict) -> float:
    """lines * (lines / (lines + unmatched)) — matches _detect_aligned_slug."""
    n = len(doc.get("lines", []))
    return n * (n / (n + len(doc.get("unmatched_gemini", [])))) if n else 0.0


def source_aligned(paths, shipped: set, cache) -> dict | None:
    """The alignment this page's published fragments actually came from.

    Selected by overlap with those fragments, NOT by quality. That distinction is
    the whole point: a page often carries alignments from several models, and
    ranking them by coverage picks a *different* one for 717 pages. Doing that
    here would bundle a model switch into what is supposed to be a matcher fix —
    it changed 15,508 extra rows on the first attempt, none of them because the
    matcher disagreed. Isolating the variable keeps this pass to the bug it is
    meant to repair.

    Coverage ranking is the fallback only when no alignment recognises any of the
    page's fragments, which is the small orphaned population.
    """
    def load(p):
        key = str(p)
        if key not in cache:
            try:
                cache[key] = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                cache[key] = None
        return cache[key]

    best, best_hits = None, 0
    for p in paths:
        doc = load(p)
        if doc is None:
            continue
        hits = sum(1 for l in doc.get("lines", [])
                   if l.get("canvas_fragment") in shipped)
        if hits > best_hits:
            best, best_hits = doc, hits
    if best is not None:
        return best
    fallback, key = None, -1.0
    for p in paths:
        doc = load(p)
        if doc is None:
            continue
        c = coverage(doc)
        if c > key:
            fallback, key = doc, c
    return fallback


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--aligned-root", type=Path, default=Path("/tmp/_oldtree"),
                    help="Restored pre-re-align tree (default: %(default)s)")
    ap.add_argument("--dry-run", action="store_true", help="Report only; write nothing")
    ap.add_argument("--review-out", type=Path,
                    help="Write unplaced entries here for review")
    ap.add_argument("--keep-floor", type=float, default=0.70,
                    help="Surya agreement an unplaceable row's existing box must "
                         "clear to be kept rather than blanked (default: %(default)s)")
    args = ap.parse_args()

    if not args.aligned_root.is_dir():
        print(f"error: {args.aligned_root} is not a directory.\n"
              f"Restore it with:\n"
              f"  mkdir -p {args.aligned_root} && tar -xzf \\\n"
              f"    {PIPELINE}/output/_ocr_backups/green_books_aligned_2026-09-04/aligned.tar.gz \\\n"
              f"    -C {args.aligned_root}", file=sys.stderr)
        return 2

    print(f"indexing {args.aligned_root} …", file=sys.stderr)
    aligned = index_aligned(args.aligned_root)
    surya = surya_index(PIPELINE / "output")
    print(f"{len(aligned)} aligned pages · {len(surya)} surya files", file=sys.stderr)
    surya_cache: dict = {}

    def surya_map(image: str):
        """bbox centre -> Surya's own reading, for the arbiter."""
        if image not in surya_cache:
            path, m = surya.get(image), None
            if path is not None:
                try:
                    doc = json.loads(path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    doc = None
                if doc:
                    m = {}
                    for l in doc.get("lines", []):
                        b = l.get("bbox")
                        if b and len(b) == 4:
                            m[(round((b[0] + b[2]) / 2), round((b[1] + b[3]) / 2))] = l.get("text", "")
            surya_cache[image] = m
        return surya_cache[image]

    doc_cache: dict = {}
    stats = collections.Counter()
    review: list[dict] = []

    for name in CSVS:
        path = REPO / name
        with path.open(encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            fields = reader.fieldnames
            rows = list(reader)

        by_page = collections.OrderedDict()
        for i, r in enumerate(rows):
            by_page.setdefault(r.get("image", ""), []).append(i)

        changed = 0
        for image, idxs in by_page.items():
            shipped = {rows[i].get("canvas_fragment", "") for i in idxs}
            doc = source_aligned(aligned.get(image, []), shipped, doc_cache)
            if doc is None:
                stats["no_aligned_json"] += len(idxs)
                continue
            lines = doc.get("lines", [])
            by_frag = {l.get("canvas_fragment"): l for l in lines}
            smap = surya_map(image)
            canvas_uri = doc.get("canvas_uri", "")
            entries = [rows[i] for i in idxs]
            bindings = bind_entries(entries, lines,
                                    canvas_width=doc.get("canvas_width") or 0)
            for i, b in zip(idxs, bindings):
                row = rows[i]
                old = row.get("canvas_fragment", "")
                stats["rows"] += 1
                if b.line_index is None:
                    # Unplaceable. Ask Surya whether the box already there is worth
                    # keeping; it had no part in producing that box.
                    stats["unplaced"] += 1
                    verdict, agree = "no_box", None
                    if XYWH.search(old):
                        line = by_frag.get(old)
                        text = surya_text_at(smap, line.get("bbox")) if line else None
                        if text is None:
                            verdict = "kept_unverifiable"   # nothing to judge it with
                        else:
                            agree = score(identity_tokens(row), tokens(text))
                            verdict = "kept" if agree >= args.keep_floor else "blanked"
                            if verdict == "blanked":
                                row["canvas_fragment"] = canvas_uri or old
                    stats[f"unplaced_{verdict}"] += 1
                    review.append({
                        "csv": name, "row": i, "image": image,
                        "name": row.get("name", ""), "address": row.get("address", ""),
                        "category": row.get("category", ""),
                        "entry_text": identity_text(row),
                        "verdict": verdict,
                        "surya_agreement": "" if agree is None else f"{agree:.2f}",
                        "fragment": row.get("canvas_fragment", ""),
                        "previous_fragment": old,
                    })
                    continue
                new = lines[b.line_index].get("canvas_fragment") or old
                if new == old:
                    stats["unchanged"] += 1
                else:
                    stats["changed"] += 1
                    changed += 1
                    if not XYWH.search(old) and XYWH.search(new):
                        stats["gained_box"] += 1
                    row["canvas_fragment"] = new

        print(f"  {name}: {changed} fragments changed")
        if not args.dry_run and changed:
            tmp = path.with_suffix(".csv.tmp")
            with tmp.open("w", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=fields)
                w.writeheader()
                w.writerows(rows)
            tmp.replace(path)

    print("\n" + json.dumps(dict(stats), indent=1))
    if args.review_out and review:
        with args.review_out.open("w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=list(review[0].keys()))
            w.writeheader()
            w.writerows(review)
        print(f"wrote {args.review_out} ({len(review)} unplaced entries)")
    if args.dry_run:
        print("\n(dry run — no files written)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
