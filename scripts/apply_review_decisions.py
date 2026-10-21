#!/usr/bin/env python3
"""Apply a human review pass from alignment_review.html back into the CSVs.

The automated arbiter that produced the review queue turned out to be much weaker
than it looked (see below), so these decisions are ground truth and override it.

  restore_box   the box was correct and the arbiter wrongly removed it -> put it back
  remove_box    the box was wrong and the arbiter wrongly kept it      -> blank it
  ok_*          the arbiter was right                                  -> leave alone
  review_again  reviewer was unsure                                    -> leave alone

Why the arbiter failed
----------------------
It scored an entry against Surya's reading of the pixels inside its box and kept
the box only above a floor. That assumed agreement falls as correctness falls. It
does not. Against 1,348 hand-reviewed blanked rows:

    agreement      n      we were right   wrongly removed   error
    0.50-0.70    118          13                98           88%
    0.30-0.50     51          38                10           21%
    0.10-0.30     59          55                 2            4%
    <0.10      1,165         778               354           31%

The error rate is 88% at the top of the blanked range, 4% in the middle, 31% at
the bottom — not monotonic in any direction, so no threshold separates the two
populations. Agreement is near zero both when the box is wrong AND when Surya
simply could not read the line (dot leaders swallow the text, and 64% of
dot-leader lines lose everything after the leader). Those two cases are
indistinguishable from the score alone.

Keeping, by contrast, was safe: of 249 kept boxes only 18 were wrong (7%).

The honest conclusion is that this needed eyes, and a hand review of 1,802 rows
found 464 boxes the heuristic had wrongly discarded.

Usage:
    python3 scripts/apply_review_decisions.py ~/Downloads/alignment_review_decisions.csv --dry-run
    python3 scripts/apply_review_decisions.py ~/Downloads/alignment_review_decisions.csv
"""

import argparse
import collections
import csv
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
CSVS = ("green_book_entries_all.csv", "travel_guides_all.csv")
XYWH = re.compile(r"#xywh=\d+,\d+,\d+,\d+")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("decisions", type=Path, help="Export from alignment_review.html")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    csv.field_size_limit(10 ** 9)

    if not args.decisions.is_file():
        print(f"error: {args.decisions} not found", file=sys.stderr)
        return 2

    decisions = list(csv.DictReader(args.decisions.open(encoding="utf-8")))
    by_csv = collections.defaultdict(dict)
    for d in decisions:
        by_csv[d["csv"]][int(d["row"])] = d

    stats = collections.Counter()
    for name in CSVS:
        path = REPO / name
        with path.open(encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            fields = reader.fieldnames
            rows = list(reader)

        changed = 0
        for i, d in by_csv.get(name, {}).items():
            if i >= len(rows):
                stats["row_out_of_range"] += 1
                continue
            row = rows[i]
            action = d["action"]
            stats[action] += 1
            if action == "restore_box":
                # The reviewer confirmed the original box was on the entry's line.
                if row["canvas_fragment"] != d["previous_fragment"]:
                    row["canvas_fragment"] = d["previous_fragment"]
                    changed += 1
            elif action == "remove_box":
                # Kept box was wrong; drop to the bare canvas so nothing is asserted.
                bare = (row["canvas_fragment"] or "").split("#")[0]
                if row["canvas_fragment"] != bare:
                    row["canvas_fragment"] = bare
                    changed += 1

        print(f"  {name}: {changed} fragments changed by the review")
        if not args.dry_run and changed:
            tmp = path.with_suffix(".csv.tmp")
            with tmp.open("w", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=fields)
                w.writeheader()
                w.writerows(rows)
            tmp.replace(path)

    print()
    for k, v in sorted(stats.items(), key=lambda kv: -kv[1]):
        print(f"  {v:>6}  {k}")
    if args.dry_run:
        print("\n(dry run — no files written)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
