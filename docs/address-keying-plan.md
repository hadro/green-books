# Address-keying plan for `gbNameIndex`

Planning doc for the next iteration of cross-listing detection in
`all-volumes.html`. Background, design, algorithm, and test cases for an
implementer (you or Claude in VS Code) to follow.

## Background

The unified viewer's coverage grid and "See all likely match listings" search
both rely on `gbNameIndex`, a `Map<string, row[]>` built during data load that
groups rows likely to represent the same business. The current key is:

```js
function gbIndexKey(name, city) {
  return gbNormName(gbStripNameTail(name)) + "|" + (city || "").toLowerCase().trim();
}
```

`gbStripNameTail` (just shipped) removes a conservative list of trailing
business-type words (`hotel`, `motel`, `restaurant`, `tourist home`, …) so
suffix variants of the same business collapse to one key. It fixes the
**Miami Carver / Miami Carver Hotel** case (14 listings now group correctly).

## The problem

Short generic names — especially neighborhood names — share keys across
genuinely different businesses. **"West End" in St. Louis** is the canonical
example:

```
52 entries all key as "west end|st. louis"
  Categories: HOTELS (22), TAVERNS (10), NIGHT CLUBS (9),
              WINE & LIQUOR STORES (5), RESTAURANTS (1), …
  Addresses:  3900 W. Belle St.            (22, the hotel)
              939 N. Vanderventer Ave.     (10, the tavern)
              911 N. Vanderventer          (9,  the night club)
              937 N. Vanderventer Ave.     (5,  the liquor store)
              W. Belle & Vandevanter Sts.  (4,  intersection form of the hotel)
              Vandevanter & W. Bell        (4,  same, OCR drift)
              W. Belle and Vandeventer     (2,  same, "and" form)
              3900 W. Beele Street         (6,  same, OCR + formatting variant)
              …
```

These are **four distinct businesses** on or near the same block, all named
after the neighborhood, currently collapsed into one mega-group.

## Address grammar in this data

Five distinct shapes show up in the `address` column:

| Shape                         | Example                          | Frequency |
|---|---|---|
| Numbered + street             | `3900 W. Belle St.`              | most common |
| Numbered with OCR/format drift| `3900 W. Beele Street`           | common |
| Intersection                  | `W. Belle & Vandevanter Sts.`    | regular |
| Street only                   | `Vanderventer Ave.`              | uncommon |
| Empty                         | (blank)                          | ~8.4% of rows |

OCR drift (`Belle/Beele/Bell`, `Vanderventer/Vandeventer/Venderventer`) crosses
all shapes.

## Proposed approach: address signatures + compatibility match

### Step 1 — Parse each address into a signature

```
parseAddress(addr) → { number: <int|null>, streets: <Set<string>> }
```

- `number` = first run of digits in the string, or `null`
- `streets` = normalized tokens for street names. For intersections, both
  streets appear in the set. For street-only or numbered, just the one.

Normalization strips directionals (`N.`, `S.`, `W.`, `E.`, `North`, `South`,
…), suffixes (`St.`, `Street`, `Ave.`, `Avenue`, `Pl.`, `Blvd.`, `Rd.`, …),
and punctuation, then lowercases. Splits on `&`, `and`, `/`, `,` for
intersections.

Examples:
- `3900 W. Belle St.`           → `{ number: 3900, streets: {"belle"} }`
- `3900 W. Beele Street`        → `{ number: 3900, streets: {"beele"} }`
- `W. Belle & Vandevanter Sts.` → `{ number: null, streets: {"belle", "vandevanter"} }`
- `Vandevanter & W. Bell`       → `{ number: null, streets: {"vandevanter", "bell"} }`
- `Vanderventer Ave.`           → `{ number: null, streets: {"vanderventer"} }`
- `""` (empty)                  → `{ number: null, streets: {} }`

### Step 2 — Compatibility match

Two rows from the same `(strippedName, city)` group are considered **the same
business** iff:

1. Their `streets` sets **share at least one token under fuzzy match** (e.g.
   Levenshtein distance ≤ 1, OR both tokens share a 4-char prefix — picking
   one is a tuning decision; start with prefix). AND
2. Their `number`s are either **equal** or **at least one is `null`**.

This handles:

| Pair                                      | Streets shared (fuzzy)  | Numbers     | Match? |
|---|---|---|---|
| `3900 Belle` ↔ `3900 Beele`               | `belle`~`beele` (prefix)| `3900`==`3900` | ✓ |
| `3900 Belle` ↔ `Belle & Vandevanter`      | `belle`                 | `3900` + null  | ✓ |
| `3900 Belle` ↔ `Vandevanter & Bell`       | `belle`~`bell`          | `3900` + null  | ✓ |
| `3900 Belle` ↔ `3901 Belle`               | `belle`                 | `3900` ≠ `3901`| ✗ |
| `3900 Belle` ↔ `939 Vanderventer`         | none                    | n/a            | ✗ |
| `939 Vanderventer` ↔ `911 Vanderventer`   | `vanderventer`          | `939` ≠ `911`  | ✗ |

### Step 3 — Build groups transitively

Compatibility is a **pairwise** relation. Group via union-find or BFS over
pairs within each (strippedName, city) bucket. Rows that don't match anyone
form singleton groups.

Per-group identifier (the new index key) can be the deterministic minimum row
index in the group, or a hash of the representative signature. Doesn't matter
for correctness; pick whichever is easier to debug.

## What this resolves on West End / St. Louis

| Group | Members | Identified as |
|---|---|---|
| A | 22 numbered "3900 Belle" + 11 intersection variants | Hotel |
| B | 10 listings at 939 Vanderventer                     | Tavern |
| C | 9 listings at 911 Vanderventer                      | Night club |
| D | 5 listings at 937 Vanderventer                      | Liquor store |
| E | 1 listing at 929 Vanderventer                       | Restaurant (singleton) |
| F | 1 listing at 3901 Belle Place                       | Singleton (one off from hotel — debatable) |
| … | a few more singletons                               | |

≈ 6 groups instead of 1. The "Hotel" group correctly absorbs the OCR-drifted
"Beele" and the intersection-form addresses.

## What this still doesn't solve

- **Empty addresses** — no signal at all. Such rows fall back to the
  `(strippedName, city)` bucket without further disambiguation. They'll merge
  arbitrarily with whichever neighbor they happen to share fuzzy-match with,
  or stay as a singleton. Treat as a known limitation; flag visually (see UX
  below).
- **Just-street addresses** — `Vanderventer Ave.` with no number could be any
  of the four Vanderventer businesses. Same issue as empty. Treat the same
  way.
- **Genuine relocations** — same business at a new address splits into
  multiple groups. Probably rare in this dataset and probably acceptable.
- **Numbers off by a few** — `3900 Belle` vs `3901 Belle` could plausibly be
  the same business (renumbering, OCR). Rule above says no-match. Optional
  fuzzy-number rule (`|a - b| ≤ 5`) is a tuning question; **default to
  strict**.

## UX: surface uncertainty in the grid

Pure resolution can't guarantee correctness on this data. When a resolved
group spans **multiple distinct categories**, that's a strong "this might be
over-merged" signal. Add a small badge to the grid row label:

```
● The Negro Motorist Green Book  ⚠ mixed categories
   [grid cells]
```

Tooltip / aria-label expands: "This group spans HOTELS, TAVERNS, and NIGHT
CLUBS — the heuristic may have merged distinct businesses."

This honest disclosure is better than silently mis-grouping. The user can
click through individual cells to see actual categories.

## Implementation outline

1. **New helpers, near `gbNormName`:**

   ```js
   const STREET_SUFFIXES = /\s*\b(st|street|ave|avenue|blvd|boulevard|rd|road|pl|place|ct|court|dr|drive|ln|lane|hwy|highway|pkwy|parkway|terr?|terrace|sq|square|way|circle|cir)\.?\s*$/i;
   const STREET_DIRECTIONALS = /\b(north|south|east|west|n|s|e|w|ne|nw|se|sw)\b\.?/gi;
   const STREET_SPLIT = /\s*(?:&| and |\/|,)\s*/i;

   function gbParseAddress(addr) {
     const raw = (addr || "").trim();
     if (!raw) return { number: null, streets: new Set() };
     // Pull a leading number off the whole thing.
     const numMatch = raw.match(/^\s*(\d+)/);
     const number = numMatch ? parseInt(numMatch[1], 10) : null;
     // Split intersection forms into separate street strings.
     const parts = raw.replace(/^\s*\d+\s*/, "").split(STREET_SPLIT);
     const streets = new Set();
     for (const p of parts) {
       const token = p
         .replace(STREET_SUFFIXES, "")
         .replace(STREET_DIRECTIONALS, "")
         .replace(/[^a-zA-Z\s]/g, "")
         .trim()
         .toLowerCase()
         .split(/\s+/).pop();   // take the last word as the street name
       if (token && token.length >= 3) streets.add(token);
     }
     return { number, streets };
   }

   function gbStreetsCompatible(a, b) {
     // Fuzzy share-a-token rule: same first 4 chars counts as a match,
     // tolerating short OCR drifts like belle/beele/bell.
     for (const ta of a) {
       for (const tb of b) {
         if (ta === tb) return true;
         if (ta.slice(0, 4) === tb.slice(0, 4)) return true;
       }
     }
     return false;
   }

   function gbAddressCompatible(sigA, sigB) {
     // Numbers: equal, or at least one missing.
     if (sigA.number !== null && sigB.number !== null && sigA.number !== sigB.number) return false;
     // Streets: at least one shared (with the fuzzy rule above).
     if (sigA.streets.size === 0 || sigB.streets.size === 0) {
       // One side has no street info — fall back to permissive match within
       // the name+city bucket.
       return true;
     }
     return gbStreetsCompatible(sigA.streets, sigB.streets);
   }
   ```

2. **Replace the index builder** in `(async function () { … })()` at the end
   of the streaming loader:

   ```js
   // After ALL_ENTRIES is fully populated:
   gbNameIndex.clear();
   const buckets = new Map();   // (strippedName, city) → row[]
   ALL_ENTRIES.forEach(row => {
     const nf = ['name','establishment_name','firm_name','business_name']
       .find(k => k in row);
     if (!nf) return;
     const stem = gbNormName(gbStripNameTail(row[nf]));
     const city = (row.city || "").toLowerCase().trim();
     if (stem.length < 3) return;
     const bk = stem + "|" + city;
     if (!buckets.has(bk)) buckets.set(bk, []);
     buckets.get(bk).push(row);
   });

   // Resolve each bucket into business-level groups.
   buckets.forEach((rows, bk) => {
     const sigs = rows.map(r => gbParseAddress(r.address));
     // Union-Find over the rows in this bucket.
     const parent = rows.map((_, i) => i);
     const find = i => parent[i] === i ? i : (parent[i] = find(parent[i]));
     for (let i = 0; i < rows.length; i++) {
       for (let j = i + 1; j < rows.length; j++) {
         if (gbAddressCompatible(sigs[i], sigs[j])) {
           parent[find(i)] = find(j);
         }
       }
     }
     // Emit each component as its own gbNameIndex entry.
     const groups = new Map();
     rows.forEach((r, i) => {
       const root = find(i);
       const key = bk + "#" + root;
       if (!groups.has(key)) groups.set(key, []);
       groups.get(key).push(r);
     });
     groups.forEach((groupRows, key) => gbNameIndex.set(key, groupRows));
   });
   ```

3. **Replace lookups** — wherever code currently does
   `gbNameIndex.get(gbIndexKey(name, city))`, it needs to know *which group*
   a row belongs to. Easiest: at index build time, also build a
   `Map<row, key>` so a row → its group key is O(1).

   ```js
   const gbRowToKey = new Map();   // row → gbNameIndex key
   groups.forEach((groupRows, key) => {
     gbNameIndex.set(key, groupRows);
     groupRows.forEach(r => gbRowToKey.set(r, key));
   });

   // Lookup helper:
   function gbCrossListings(row) {
     return gbNameIndex.get(gbRowToKey.get(row)) || [];
   }
   ```

   Then replace each `gbNameIndex.get(gbIndexKey(...))` call site with
   `gbCrossListings(row)`.

4. **Mixed-category UX badge** in the grid renderer (`showDetail` patch in
   `all-volumes.html`). For each publication row, check whether the group's
   listings in that publication span >1 category; if so, append a `⚠` span
   with a tooltip / `aria-label`.

## Validation: before/after comparison page

Build a one-off `address-keying-test.html` (don't ship; for review only) that
loads both CSVs and lists side-by-side groupings for a curated set of
business names:

- `West End` / St. Louis
- `Miami Carver Hotel` / Miami
- `Hotel Theresa` / New York
- A few common-name picks (e.g. `Royal Hotel`, `Central Cafe`, `Park Hotel`)
- A few rare-name picks (should be unaffected — sanity check)

Show: old grouping (single bucket), new grouping (multiple sub-groups), with
counts and a few sample addresses per group. Inspect, tune the fuzzy-match
threshold and the `streets` empty-set fallback rule, then ship.

## Tuning knobs worth exposing during development

- **Street-token fuzzy match.** Prefix-of-4 is dumb-simple. Levenshtein ≤ 1
  is more nuanced but more code. Pick prefix-of-4 to start; revisit if
  validation surfaces obvious misses.
- **Empty-streets fallback.** Current proposal: empty + non-empty matches as
  permissive (`true`). Alternative: empty matches only other empty.
  Permissive errs toward merging; strict errs toward splitting. Default
  permissive for now; revisit.
- **Number-mismatch tolerance.** Default strict (must equal or one null).
  Optional fuzzy (`|a - b| ≤ 5`) is a one-line change.

## Open questions to settle as you build

- Do you want the badge for "mixed categories within a single (group,
  publication, year)" too (one cell having multiple categories), or just at
  the group level?
- Should "See all likely match listings" now search by the **resolved group**
  rather than the suffix-stripped name? It'd be more precise but tighter
  (currently it casts the wider name+city net). Could do both as
  "Show this business" vs "Show all matches by name."
- Is there value in surfacing the `address` column in the grid's hover state
  / tooltip? Already in the detail panel below, but for cells of *other*
  listings, showing the address would help the user spot over-merges.

## Out of scope (defer)

- Phone number matching (column is sparse and unreliable).
- Proprietor-name matching (same).
- Geocoding-based clustering (overkill).
- Manual merge/split UI.
