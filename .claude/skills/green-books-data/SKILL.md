---
name: green-books-data
description: Query the Green Book / Black travel guide corpus — 113,827 historical business listings across 50 volumes (1930–1966) in green_book_entries_all.csv and travel_guides_all.csv. Use when asked to search, count, cross-reference, chart, or audit listings; trace a business across editions; find listings by city, state, year, category, or NYC neighborhood; check transcription quality against the scanned page; or build a derived dataset from the corpus. Triggers on "Green Book", "travel guide listings", "the corpus", "the CSVs", specific business/place/edition lookups, and data-quality questions about the entries.
---

# Querying the Green Books corpus

113,827 listings from 50 digitized volumes of *The Negro Motorist Green Book* and seven
companion African American travel guides, 1930–1966, across 8 publications. Every row
links back to the exact region of the page scan it was read from.

**Never answer a corpus question by eyeballing the CSVs or by loading them into context.**
They are 34 MB / 114k rows. Build the SQLite database once and query it.

## Setup (once per checkout)

```bash
python3 scripts/build_query_db.py        # ~5 s → green_books.sqlite (68 MB, gitignored)
python3 scripts/build_query_db.py --check   # exit 1 if missing or stale vs the CSVs
```

Rebuild whenever either CSV or `nyc_geo.json` changes. Only Python stdlib is required —
`sqlite3` with FTS5. There is no DuckDB or pandas dependency, and don't add one.

## Querying

Query through Python — the `sqlite3` **command-line tool is often not installed**,
while the Python module always is. Use a heredoc and `sqlite3.Row`:

```bash
python3 - <<'EOF'
import sqlite3
con = sqlite3.connect("green_books.sqlite"); con.row_factory = sqlite3.Row
for r in con.execute("SELECT publication, COUNT(*) n FROM listings GROUP BY 1 ORDER BY n DESC"):
    print(dict(r))
EOF
```

Write intermediate result files to the scratchpad, not the repo.

### Tables

| Table | What |
|---|---|
| `listings` | 113,827 rows, both corpora in one schema |
| `listings_fts` | FTS5 over `name`, `address`, `notes`, `proprietor` (external content, join on `rowid = listings.id`) |
| `volumes` | 50 rows — per-volume rights provenance from `hf-dataset/volume_rights.csv` |
| `meta` | row counts + a staleness signature |

### Columns worth knowing

- `publication` — series label; all 24 Green Book editions collapse to `The Green Book`.
  `volume_title` keeps the specific edition. `source_corpus` is `green_book` or `travel_guides`.
- `category` (as printed) vs `category_normalized` (folded — **use this for grouping**).
- `state` (as printed) vs `state_normalized` (case-fold only, see gotchas).
- `canvas_fragment` — IIIF URL + `#xywh=` region. The provenance anchor.
- `thumb_id` — `sha1(canvas_fragment)[:12]`, the CDN/geo join key.
- `flags` — comma-joined list of the quality flags set on the row; `''` when clean.
- `lat`/`lon`/`neighborhood`/`borough`/`geo_approx` — populated for the 8,082 NYC rows only.

## Recipes

**Full-text search.** Scope the match to a column, or the term will also hit
addresses and notes:

```sql
SELECT l.name, l.city, l.volume_year, l.publication
FROM listings_fts f JOIN listings l ON l.id = f.rowid
WHERE listings_fts MATCH 'name:gaston'
ORDER BY l.volume_year;
```

**A place in a year.** Cities are as-printed and inconsistent (`Birmingham`,
`Birmingham, Ala.`) — match with `LIKE`, and filter state with `state_normalized`:

```sql
SELECT name, category_normalized, address, volume_title FROM listings
WHERE city LIKE 'selma%' AND state_normalized LIKE 'ALABAMA%' AND volume_year = 1953;
```

An empty result usually means the city or year string is off, **not** that the town
was absent from the guides. Check what actually exists before reporting a negative —
`SELECT volume_year, COUNT(*) FROM listings WHERE city LIKE 'selma%' GROUP BY 1` — and
say "no listing in this corpus" rather than "there were none."

**Category mix over time** (use the normalized column):

```sql
SELECT volume_year, category_normalized, COUNT(*) n FROM listings
WHERE publication = 'The Green Book' AND volume_year BETWEEN 1947 AND 1955
GROUP BY 1, 2 ORDER BY 1, n DESC;
```

**NYC neighborhoods:**

```sql
SELECT neighborhood, borough, COUNT(*) n FROM listings
WHERE neighborhood IS NOT NULL GROUP BY 1, 2 ORDER BY n DESC;
```

**Quality triage** — pull flagged rows to check against the scan:

```sql
SELECT name, address, city, state, flags, canvas_fragment FROM listings
WHERE flags LIKE '%flag_name_address%' ORDER BY RANDOM() LIMIT 20;
```

## Verifying a row against the page scan

The data was transcribed by a vision-language model, not keyed by hand — on dense
multi-column directory pages it confuses columns, mis-reads text, and mis-labels
categories. **When accuracy matters, look at the crop.** From any row:

- Cropped thumbnail (pre-built, ~4 KB):
  `https://huggingface.co/datasets/hadro/green-books-thumbnails/resolve/main/<thumb_id[:2]>/<thumb_id>.webp`
- Full viewer, zoomed to the listing:
  `https://hadro.github.io/green-books/index.html?cf=<url-encoded canvas_fragment>`

Fetch the thumbnail and read it. Cite the viewer link in any answer that makes a
factual claim about a specific listing.

## Gotchas

**Don't re-derive logic that already exists here.** Two normalizations are load-bearing
and an ad-hoc reimplementation will silently disagree with the published site:

- *Category folding* — `gb_categories.py` / `gb-categories.js`, folding 760 raw values
  to 463. Already applied as `category_normalized`.
- *Cross-edition business matching* — `gb-matching.js`. Grouping the same business across
  editions is **not** name+city; it is address-signature resolution (house-number ranges,
  fuzzy street tokens, dominance anchoring for intersections). It is not in the database.
  To trace a business across editions, either read `gbBuildMatchIndex` and run it under
  Node, or present candidates as *likely* matches and say so. Never invent a match rule.

**`state_normalized` is a case fold, not a gazetteer.** It uppercases and trims; it does
not expand `Fla.` → `FLORIDA`. 208 distinct values remain. Match with `LIKE`/`IN`, and
never assume 50 clean states.

**`thumb_id` is not a primary key.** 619 rows share a `canvas_fragment` with another row
(two listings read from one page region). Join on `listings.id` when you need one row.

**`drift_geonames` is noise at scale.** It is set on 50,456 rows — a soft signal, not a
defect list. Real triage targets are `flag_name_address` (440), `flag_unanchored` (314),
`flag_duplicate` (2,480), `flag_state_invalid` (2,303), and high `drift_score`.

**Rights are per-volume.** Most volumes are NYPL `PDREN` (public domain); the 1946 Green
Book is LOC "no known restrictions"; *Travelguide 1957* is `ICORPHAN`, an orphan work.
Check `volumes` before redistributing rows, and don't flatten to "it's all CC0".

**Blank categories are the largest group** (26,322 rows, `Blank or no specific category`).
Exclude them explicitly in any "most common category" answer, or say they're included.

## Reporting numbers

State the filter you used alongside any count — corpus-wide, single publication, and
single edition totals differ by an order of magnitude, and "the Green Book" (67,052)
is not "the corpus" (113,827). When a number could be read either way, give both.
