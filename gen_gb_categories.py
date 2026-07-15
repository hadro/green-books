#!/usr/bin/env python3
"""Generate gb-categories.js from gb-categories.json.

gb-categories.json is the SINGLE SOURCE OF TRUTH for the category fold map
(read directly by gb_categories.py for the dataset build). This script emits an
inline-map `gb-categories.js` from it, so the browser explorers load the map
synchronously via <script> — no runtime fetch(), so it can't 404 and works over
file://. Run after editing gb-categories.json:

    python3 gen_gb_categories.py

Then commit both gb-categories.json and the regenerated gb-categories.js.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
JSON_PATH = os.path.join(HERE, "gb-categories.json")
JS_PATH = os.path.join(HERE, "gb-categories.js")

HEADER = """\
// gb-categories.js — shared category-folding logic for the Green Book explorers.
// Loaded by explorer.html (Green Book only) and all-volumes.html (merged).
//
// ⚠ AUTO-GENERATED from gb-categories.json — DO NOT EDIT BY HAND.
//   Edit gb-categories.json (the single source of truth, also read by the Python
//   dataset build in gb_categories.py), then regenerate:  python3 gen_gb_categories.py
//
// Two-layer normalization (mirrored exactly in gb_categories.py):
//   1. Baseline case fold — trim + uppercase, so "Motel"/"MOTEL" collapse for free.
//   2. Explicit groups — GB_CATEGORY_GROUPS maps a canonical display label to the
//      UPPERCASE raw variants (typos, plurals, synonyms) that fold into it.
// The blank bucket ("" after trim) folds to "Blank or no specific category".
//
// The map is inlined below (not fetched) so it loads synchronously with the page
// and gbCategoryGroup() is available immediately — no async readiness needed.
"""

BODY = """
// variant (UPPERCASE) → canonical display label, built once from GB_CATEGORY_GROUPS.
// Canonical labels map to themselves so an already-canonical (or case-variant)
// value resolves without a separate variants entry.
const _GB_CATEGORY_INDEX = (() => {
  const idx = {};
  Object.entries(GB_CATEGORY_GROUPS).forEach(([canonical, variants]) => {
    idx[canonical.toUpperCase()] = canonical;
    variants.forEach(v => { idx[v] = canonical; });
  });
  return idx;
})();

// Fold a raw category value to its display label: baseline case fold, then the
// explicit groups map, falling back to the uppercased raw value when unmatched.
function gbCategoryGroup(raw) {
  const folded = (raw || "").trim().toUpperCase();
  if (!folded) return "Blank or no specific category";
  return _GB_CATEGORY_INDEX[folded] || folded;
}
"""


def main():
    with open(JSON_PATH) as f:
        groups = json.load(f)
    # json.dumps with 2-space indent is a valid JS object literal (quoted keys).
    literal = json.dumps(groups, indent=2, ensure_ascii=False)
    js = HEADER + "\nconst GB_CATEGORY_GROUPS = " + literal + ";\n" + BODY
    with open(JS_PATH, "w") as f:
        f.write(js)
    n_labels = len(groups)
    n_variants = sum(len(v) for v in groups.values())
    print(f"Wrote {JS_PATH} — {n_labels} canonical labels, {n_variants} variants")


if __name__ == "__main__":
    main()
