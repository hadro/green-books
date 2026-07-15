// gb-categories.js — shared category-folding logic for the Green Book
// explorers. Loaded by explorer.html (Green Book only) and all-volumes.html
// (Green Book + travel guides merged).
//
// SINGLE SOURCE OF TRUTH: the category map lives in `gb-categories.json`, which
// is fetched at load time here and read directly by the Python build
// (gb_categories.py). Do not re-inline the map into this file — edit the JSON.
//
// Two-layer normalization (mirrored exactly in gb_categories.py):
//   1. Baseline case fold — every raw value is trimmed and uppercased before
//      lookup, so casing/whitespace variants ("Motel" / "MOTEL") collapse for
//      free without needing an entry in the map.
//   2. Explicit groups — gb-categories.json maps a canonical display label to
//      the UPPERCASE raw variants (typos, plurals, synonyms) that fold into it.
//      Variants are stored UPPERCASE, matched against the baseline-folded value.
// The blank bucket ("" after trimming) always folds to "Blank or no specific
// category" — handled in gbCategoryGroup(), since there is no raw string.
//
// The JSON's "Blank or no specific category" group additionally absorbs generic
// combined-lodging section headers ("Hotels - Motels - Tourist Homes", "Where
// to Stay", ...), bare geographic section headers, sports-league/event headers,
// publishing-apparatus/editorial headers that leaked in from non-listing pages,
// placeholder values ("Not Specified", "N/A", ...), and proper-noun one-offs.
// Genuine compound business-type categories ("Hotels & Guest Houses", "Cafes &
// Taverns") are deliberately kept distinct — this is a mechanical/typo/header
// cleanup, not a taxonomy rollup.
//
// ── Async loading ────────────────────────────────────────────────────────────
// Because the map is fetched, `window.gbCategoriesReady` is a Promise that
// resolves once the index is built. Callers that fold during boot (facet
// building, first render) MUST `await window.gbCategoriesReady` before their
// first gbCategoryGroup() call. If gbCategoryGroup() is somehow called before
// the index loads, it degrades gracefully to the baseline case fold (no
// grouping) rather than throwing.

// variant (UPPERCASE) → canonical display label. Null until the JSON loads.
let _GB_CATEGORY_INDEX = null;
// The raw map, exposed for any caller that inspected it before (parity with the
// old inline `GB_CATEGORY_GROUPS` global). Populated on load.
let GB_CATEGORY_GROUPS = null;

window.gbCategoriesReady = fetch('gb-categories.json')
  .then(r => { if (!r.ok) throw new Error('HTTP ' + r.status + ' for gb-categories.json'); return r.json(); })
  .then(map => {
    GB_CATEGORY_GROUPS = map;
    const idx = {};
    Object.entries(map).forEach(([canonical, variants]) => {
      idx[canonical.toUpperCase()] = canonical;
      variants.forEach(v => { idx[v] = canonical; });
    });
    _GB_CATEGORY_INDEX = idx;
    return map;
  });

// Fold a raw category value to its display label: baseline case fold, then the
// explicit groups map, falling back to the uppercased raw value when there's no
// group match (or the map hasn't loaded yet).
function gbCategoryGroup(raw) {
  const folded = (raw || "").trim().toUpperCase();
  if (!folded) return "Blank or no specific category";
  if (!_GB_CATEGORY_INDEX) return folded;  // map not loaded yet — degrade to case fold
  return _GB_CATEGORY_INDEX[folded] || folded;
}
