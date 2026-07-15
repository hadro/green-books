"""gb_categories.py — Python port of gb-categories.js's category folding.

Reads the shared `gb-categories.json` (the single source of truth, extracted
from gb-categories.js) so the dataset build and the browser explorer fold
categories identically. Mirrors gbCategoryGroup():

  1. Baseline case fold — trim + uppercase, so "Motel"/"MOTEL" collapse for free.
  2. Explicit groups — GB_CATEGORY_GROUPS maps a canonical display label to the
     UPPERCASE raw variants (typos, plurals, synonyms) that fold into it.
  Blank ("" after trim) folds to "Blank or no specific category".

Also provides gb_state_normalize(), a light state fold (trim + uppercase +
trailing-punctuation strip) matching how the explorers case-fold state inline.
This is a mechanical case fold only — NOT a gazetteer/abbreviation resolver.
"""
import json
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_JSON = os.path.join(_HERE, "gb-categories.json")

with open(_JSON) as _f:
    GB_CATEGORY_GROUPS = json.load(_f)

# variant (UPPERCASE) -> canonical display label. Canonical labels also map to
# themselves so an already-canonical value resolves without a variants entry.
_GB_CATEGORY_INDEX = {}
for _canonical, _variants in GB_CATEGORY_GROUPS.items():
    _GB_CATEGORY_INDEX[_canonical.upper()] = _canonical
    for _v in _variants:
        _GB_CATEGORY_INDEX[_v] = _canonical

BLANK_CATEGORY_LABEL = "Blank or no specific category"


def gb_category_group(raw):
    """Fold a raw category to its canonical display label (mirrors gbCategoryGroup)."""
    folded = (raw or "").strip().upper()
    if not folded:
        return BLANK_CATEGORY_LABEL
    return _GB_CATEGORY_INDEX.get(folded, folded)


def gb_state_normalize(raw):
    """Light state fold: trim, uppercase, strip surrounding punctuation/dots.

    Collapses case variants ("New York" -> "NEW YORK") and trailing periods.
    Does not expand abbreviations or map to a canonical gazetteer.
    """
    s = (raw or "").strip().upper()
    return s.strip(" .,;:")


if __name__ == "__main__":
    # Smoke test against a few known variants.
    for probe in ["Motel", "DRUGGIST", "hotels - motels - tourist homes",
                  "", "LOURIST", "Some Rare Thing"]:
        print(f"{probe!r:45s} -> {gb_category_group(probe)!r}")
    for probe in ["New York", "NEW YORK", "Fla.", "canada"]:
        print(f"{probe!r:15s} -> {gb_state_normalize(probe)!r}")
