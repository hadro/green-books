# MCP server for the Green Books corpus — plan

**Status:** proposal, not started. Written 2026-08-01.
**Scope:** expose the 113,827-listing corpus to LLM agents over the Model Context
Protocol, without breaking this repo's no-build-step, no-infrastructure property.

---

## Recommendation

Build it, as a **local stdio server** shipped in this repo: one Python package,
one SQLite file built from the CSVs, no hosting. Defer any remote/HTTP deployment
until there is evidence of non-developer demand.

The case rests on one thing: **the valuable part of this dataset is not the rows,
it's the logic layered on top of them**, and that logic currently exists only
inside `all-volumes.html`, `gb-matching.js`, and `gb-categories.js`. Anyone handed
the raw CSVs re-derives it badly.

### The counterargument, stated fairly

The data is already public, CC0-oriented, static, and one `read_csv` away on
Hugging Face. A server that only wraps "grep the CSV" earns nothing. And this
repo's defining property is that it has no build step and no backend — a server is
the first thing to break that. If the answer were only "make the CSVs queryable,"
the right answer would be a skill, not a server.

### What survives it

1. **Too big for context, but the questions are small.** 34 MB / 109k rows across
   the two CSVs. "Which Birmingham businesses appear in every edition 1947–1955?"
   is a one-paragraph answer that today needs the web UI or hand-written pandas.
2. **The joins are non-trivial and already solved here.** `gb-matching.js` is ~500
   lines of address-signature resolution; `gb-categories.js` folds 759 raw category
   strings to 462. Exposing *our* resolver is the strongest single reason to build.
3. **Every row is provenanced, so hallucination is checkable.** Each listing carries
   a `canvas_fragment` with `#xywh=` and a pre-cropped thumbnail at a
   content-addressed URL. A tool returning the crop *as an image* lets a vision
   model verify its own answer against the scan — which is what the dataset card
   already tells humans to do.
4. **~60k quality flags have no consumer.** `drift_geonames` 47,565 ·
   `drift_score` 4,946 · `flag_duplicate` 1,306 · `flag_state_invalid` 1,262 ·
   `flag_name_address` 335 · `flag_unanchored` 314. That is more than anyone will
   hand-review.

### Alternative already delivered

`.claude/skills/green-books-data/` + `scripts/build_query_db.py` ship now and cover
most of tiers 1–2 **for agents with shell access**. If the audience is only
developers in Claude Code, that may be enough — evaluate it before committing to the
server. MCP wins if the audience includes Claude Desktop, ChatGPT, or researchers
who will not open a terminal, which the existence of three public explorer UIs
suggests it does.

---

## Use cases, ranked by confidence

### Tier 1 — these justify the build

- **Data-quality triage (highest value, and it's for the maintainer).** Agent pulls
  flagged rows, fetches the page crop, compares transcription to image, emits a
  correction patch with confidence + evidence URL, to be reviewed and fed back into
  `directory-pipeline`. Nothing consumes the flag columns today.
- **Corpus Q&A with citations.** "What was available to a Black traveler in Selma in
  1961?" → listings, each with a deep link to the exact page region. The citation is
  the product; without it this is a chatbot speculating about history.
- **Cross-edition business biography.** Trace one business across every guide it
  appears in — the thing that genuinely cannot be reproduced from the CSVs alone.
  See the caveat in [Cross-edition matching](#cross-edition-matching-the-hard-part).

### Tier 2 — real, secondary

- **Aggregates and trends** — category mix 1947 vs 1955, states gaining/losing
  listings — answered as counts without pulling rows into context.
- **Geography** over the 7,969 NYC-geocoded rows (neighborhood, borough, radius).
- **External enrichment** — this server plus web search to match listings against
  present-day addresses or NRHP entries. Useful, hallucination-prone; treat output
  as leads, never as data.

### Tier 3 — skip

- Public "chat with the Green Book" as a product. That's a website feature; the MCP
  audience is people already inside an agent client.
- Any write path. The server is read-only. Corrections belong in the pipeline repo
  as reviewed patches, never as live edits to a published historical dataset.

---

## Architecture

```
green_book_entries_all.csv ─┐
travel_guides_all.csv ──────┼─→ scripts/build_mcp_db.py ─→ green_books.sqlite ─→ MCP server (stdio)
nyc_geo.json ───────────────┤        (superset of                                      │
hf-dataset/volume_rights.csv┘      build_query_db.py)                          .mcp.json in repo
gb-matching.js ─(node vm)───┘                                                   uvx for external use
```

- **Transport:** stdio. No hosting, no CORS, no rate limiting, no auth surface.
- **Language:** Python, `mcp` SDK (FastMCP). Reuses `gb_categories.py` directly.
- **Store:** SQLite, read-only at runtime. `scripts/build_query_db.py` already builds
  the listings + FTS5 + volumes tables in ~5 s (68 MB output, gitignored).
  `build_mcp_db.py` is that script plus the `business_group_id` column below.
- **Distribution:** `.mcp.json` committed so Claude Code sessions in this repo pick
  it up automatically; `uvx --from git+https://github.com/hadro/green-books ...` for
  everyone else. The database builds on first run if absent.

### Why not ship the SQLite file

68 MB, derived, and it changes whenever the CSVs do. Building it locally in 5 s from
data already in the checkout is strictly better than committing a binary that can go
stale silently. `--check` catches staleness against a size+mtime signature.

---

## Tool surface

Seven tools. Every listing-returning tool includes `canvas_fragment`, the viewer
deep link, and the thumbnail URL — provenance is not optional.

| Tool | Purpose |
|---|---|
| `search_listings` | FTS5 + filters (publication, year range, state, city, category, flags); paginated |
| `get_listing` | One row, full detail, plus its cross-edition group |
| `trace_business` | Every appearance of one business across all 50 volumes, chronological |
| `aggregate_listings` | `group_by` ∈ {year, state, city, category, publication, neighborhood}; counts only |
| `list_volumes` | 50 volumes: years, publication, institution, **rights statement**, row counts |
| `get_page_crop` | Returns the cropped scan as MCP image content — the verification tool |
| `find_flagged` | Flag/drift-filtered sampling for the QA loop |

**Resources**, not tools, for what a model should read once rather than query: the
dataset card, the schema table, the category taxonomy (`gb-categories.json`), and
per-volume rights.

### Non-negotiable behaviours

- Tool *descriptions* carry the "machine-transcribed by a VLM — verify against the
  scan" caveat. A README nobody loads is not where that belongs.
- `list_volumes` surfaces rights per volume. Most are NYPL `PDREN`; the 1946 edition
  is LOC "no known restrictions"; **Travelguide 1957 is `ICORPHAN`, an orphan work**.
  An agent redistributing rows must be able to see that, so never flatten to "CC0".
- Result caps on every tool; `aggregate_listings` exists so counting questions never
  drag 10k rows through context.

---

## Cross-edition matching, the hard part

`trace_business` is the highest-value tool and the only one with a real design risk.

**Do not port `gb-matching.js` to Python.** ~500 lines of address heuristics
duplicated in two languages will drift, and the browser copy is the one users see.
Instead run the existing JS **once at build time** under Node and materialize the
result as a `business_group_id` column. Runtime matching then collapses to a
`GROUP BY`, and the JS stays the single source of truth.

This works today with **zero modification** to `gb-matching.js` — it declares bare
globals, so `vm.runInContext` picks up `gbBuildMatchIndex` directly:

```js
const ctx = { performance: { now: () => Date.now() } };
vm.createContext(ctx);
vm.runInContext(fs.readFileSync("gb-matching.js", "utf8"), ctx);
const { rowToKey } = ctx.gbBuildMatchIndex(rows);   // row → stable group key
```

### The recall limit — measured, not hypothetical

`gbBuildMatchIndex` buckets by `gbNewNameStem(name) + city` **before** address
resolution runs, so address matching only ever happens *within* a name-stem bucket.
Name variants that stem differently never get compared, however identical their
addresses.

Run against the 18 real listings for the A. G. Gaston Motel in Birmingham — one
business, one address, 1955–1966 — the matcher returned **three** groups:

| Group key | Rows | Example address |
|---|---:|---|
| `a g gaston\|birmingham#0` | 14 | `1510 5th Avenue North` |
| `gaston a g\|birmingham#0` | 3 | `1510 5th Ave., N.` — inverted name form, different bucket |
| `a g gaston\|birmingham#1` | 1 | `1510 5th Ave., N.` — same bucket, address split |

The singleton was a bug in `gbParseAddress`, **since fixed** — see
"Trailing directionals" below. It is now 2 groups: 15 + 3.

The remaining split is the structural one, and it does not have a cheap fix: the
inverted name form `"Gaston, A. G. (Motel)"` stems to `gaston a g` rather than
`a g gaston`, lands in a different bucket, and its address is therefore never
compared against the other fifteen.

**Consequences for the design:**

1. A naive `trace_business` over group IDs would report 15 appearances where the
   truth is 18 — confidently, with citations. That is worse than no tool.
2. So `trace_business` returns **two tiers**: `resolved` (same `business_group_id`,
   matching the live site exactly) and `candidates` (name-token/FTS recall pass,
   mirroring the site's "See all likely match listings"), clearly labelled, with the
   model told never to merge the tiers silently.

### Trailing directionals — fixed

Diagnosing the singleton above turned up a real defect in `gbParseAddress`, now
fixed in `gb-matching.js` with regression tests in `tests/matching_test.js`.

`STREET_SUFFIXES` is anchored to end-of-string, so a trailing directional shielded
the street type from being stripped. The *same* address then produced different
signatures depending on spelling:

| Address | Before | After |
|---|---|---|
| `1510 5th Ave.` | `["5"]` | `["5"]` |
| `1510 5th Ave. N.` | `["ave", "5ave"]` | `["5"]` |
| `1510 5th Avenue North` | `["avenue", "5avenue"]` | `["5"]` |
| `1510 5th Ave. No.` | `["ave", "5aveno"]` | `["5"]` |

The bare-ordinal form was the correct one all along; the directional spellings were
the broken ones, leaking the street type as a token and losing the ordinal entirely.
Because `tokensMatch` refuses to fuzzy-match numeric ordinals (so 5th never meets
6th), `["5"]` could never reach `["ave", "5ave"]`.

The fix strips a *trailing run* of directionals before the suffix strip, with a
fallback for streets whose name **is** a direction — Brooklyn's `Ave. S`, Washington's
`Q St. N. W.` — which would otherwise be erased. Corpus-wide: 961 of 100,847
addresses change signature, none lose all street tokens, and group count drops from
31,917 to 31,845 — 72 groups correctly unified (same business, same address, e.g.
`548 Bedford Pl. N. E.` / `548 Bedford Place, N.E.`).

One group split, and it is an honest cost: `901 Rhode Island Ave. N. W.` and
`901 Rhode Is. Ave. N. W.` (YWCA, Washington) previously matched *only* through the
junk `ave` token both carried — a token that would equally have matched any other
avenue in the bucket. That merge was accidental, not principled, and the abbreviation
`Rhode Is.` is beyond what the resolver handles.

The extra parsing pass cost ~18% on `gbParseAddress`. Rather than leave that,
`gbParseAddress`, `gbNewNameStem` and `gbHouseRange` are now memoized — the corpus
reprints the same address, name and house range edition after edition (60% of
address triples and 75% of names are repeats), so the index build drops from
~1,300 ms to ~910 ms over all 109,163 rows, a net ~30% faster than before the fix.
The tables serve one build and `gbBuildMatchIndex` clears them on the way out, so
retained memory is unchanged at 13.3 MB; `gbClearMatchCaches()` is exported for
callers that drive `gbResolveGroups` directly.

Two known limits were left alone as out of scope: `No.`/`So.` are still not treated
as directionals in the *global* strip (adding them fixes a false merge of
`429 No. 37th St.` with `429 No. 27th Street`, but costs eight Tacoma/Las Vegas
lettered-street addresses their only token), and the street *type* is discarded for
numbered streets, so `5th Ave.` and `5th St.` share a signature.

---

## Build plan

| Phase | Work | Est. |
|---|---|---|
| 0 | ✅ `scripts/build_query_db.py` + `green-books-data` skill (shipped) | done |
| 1 | `scripts/build_mcp_db.py`: add the Node group-ID precompute + `business_group_id` | ~0.5 d |
| 2 | Server skeleton + `search_listings`, `get_listing`, `list_volumes` | ~0.5 d |
| 3 | `trace_business` (two-tier), `aggregate_listings`, `find_flagged` | ~0.5 d |
| 4 | `get_page_crop` (fetch CDN thumb, fall back to live IIIF crop), resources | ~0.25 d |
| 5 | `.mcp.json`, README section, pytest smoke tests, packaging | ~0.5 d |

Roughly **two focused days**. Phase 1 is the piece most likely to surprise — the
group-ID precompute across 109k rows has not been timed at full scale (the matcher
is O(n²) within a bucket, which is fine for small buckets and needs watching for
large ones such as blank-name rows in a big city).

---

## Deferred / open questions

- **Remote HTTP server** (Cloudflare Worker + D1, or similar). Would reach
  non-technical users, but adds hosting, cost, abuse surface, and an update pipeline
  to a repo that currently has none. Revisit only with evidence of demand.
- **Should the server read the HF dataset instead of local CSVs?** Would decouple it
  from a checkout, at the cost of a network dependency and version skew. Local wins
  while the server ships in this repo.
- **Sibling-explorer overlap.** Pending work item #3 (the 26-volume travel guide
  explorer) needs the same aggregates this server computes. Worth checking whether
  the DB build can also emit the explorers' hard-coded `FIELD_META.top_values`,
  which are currently recomputed by hand whenever the data changes.
- **Name-stem bucketing** is now the binding constraint on matching recall: an
  inverted name form (`Gaston, A. G.`) never has its address compared against the
  canonical form. Fixing it means resolving addresses across buckets, which is a
  bigger change than the trailing-directional fix and needs its own measurement.
- **`No.`/`So.` as global directionals** — fixes a false merge (37th St / 27th St)
  at the cost of eight lettered-street addresses. Deferred; see above.

---

## Risks

| Risk | Mitigation |
|---|---|
| Confident wrong answers about real historical businesses | Provenance on every row; `get_page_crop` for verification; two-tier `trace_business` |
| Matching logic forks between JS and Python | Never port it — precompute from the JS at build time |
| Derived DB goes stale against the CSVs | `--check` staleness signature; build on first run |
| Orphan-work volume redistributed as public domain | Rights surfaced per volume in `list_volumes` |
| Repo acquires infrastructure it can't maintain | stdio only; no hosting; remote deployment explicitly deferred |
