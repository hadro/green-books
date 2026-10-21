# Alignment audit and entry-binder repair — handoff

**2026-09-04, revised 2026-09-05.** Work spans two repos. Nothing is committed in either,
no thumbnails have been regenerated, and no alignment policy has been applied — the
published site still serves the pre-repair data.

**The 2026-09-05 revision reversed the recommendation.** Josh asked whether any of the
alignment work correlates to what the explorer actually shows. It largely does not: aligned
lines are not entry boxes, and most lines never become one. The recommendation is now
*ship the binder, keep the code fixes, leave the alignment data unapplied* — see
[The open decision](#the-open-decision). Two numbers in the first version of this doc were
withdrawn; both corrections are marked inline rather than deleted.

Two sessions worked this in parallel: this repo (audit, entry binding, measurement) and
`directory-pipeline` (OCR alignment). Their side is documented at
`directory-pipeline/docs/evidence/2026-09-04-column-selection-criterion/` and
`directory-pipeline/docs/plans/degenerate-page-reocr.md` — read those for the aligner
internals; this doc does not duplicate them.

A narrative version for non-implementers is published as an Artifact,
"The Misplaced Boxes".

---

## The problem, in one page

Some entries in the explorers highlight the wrong region of the right page. Josh reported
two examples; the audit found ~2,000 across 113,827 entries.

**It was mostly not an OCR alignment problem.** Three separate causes:

| # | Cause | Where | Status |
|---|---|---|---|
| 1 | Entry→line matcher fell through to `category`, which in a Green Book *is* the printed section heading | `pipeline/extract_entries.py` | **Fixed** (rewritten as `utils/entry_binding.py`) |
| 2 | `patch_canvas_fragments.py` kept a second copy of the same matcher, and skipped `multimodal` pages — two-thirds of the corpus | `tools/patch_canvas_fragments.py` | **Fixed** |
| 3 | Aligner chose the per-column result even when far worse than whole-page | `pipeline/align_ocr.py` | **Fixed** (peer session) |

Field attribution for cause 1, replayed over every flagged row:

```
489  category          ← the section heading, matched verbatim
 53  name              ← "Ave", "Hall" — 3 chars, substring-matched anything
 45  phone
 36  location_city   33  state_country   15  state_region   14  state_or_province
 27  details   13  manager_owner   12  mileage   10  notes   10  price
```

The second cluster is the design lesson: the old guard was a **denylist of four field
names** (`section`, `subsection`, `state`, `city`), but every collection's NER prompt
invents its own names. A denylist cannot govern an open vocabulary. The replacement uses
an **allowlist keyed on field shape** — anything ending `_name` is identity, so a new
collection's `ship_name` works and its `mileage` never will.

---

## The open decision

**Superseded 2026-09-05 — read this section, not the earlier table.** An earlier
version of this doc recommended applying the re-alignment selectively (+301
correctly-placed entries for ~4,110 thumbnails). **That table has been withdrawn.**
It was built on a circular metric; corrected, the gain is +52, not +301.

### Recommendation: do not apply the alignment data

Measured on pages the re-align actually rewrote (2,566 pages, 73,401 entries),
scoring each box by what **Surya** independently read at that bbox:

```
fragment changed        12,831  (17.48%)
placement old -> new    0.8373 -> 0.8393   (+0.0019)
bound in both (70,306)  improved 468 | degraded 416 | unchanged 69,422
badly placed (<0.30)    2,013 -> 1,977  (-36)
```

**~12,800 thumbnail regenerations to buy a net +52 placements across 70,306 boxes.**
98.7% of entry boxes do not move even where the re-align ran. Not worth applying.

The alignment genuinely is better at the *line* level. Those gains land on lines
that never become an entry box — most aligned lines never display.

### The metric error, because it is easy to repeat

Both the withdrawn table and the binder result score an entry against the text of
the line its box points at. That is **correct for one and circular for the other**:

| Measurement | Variable | Line text | Verdict |
|---|---|---|---|
| Binder (961 repairs / 0.12%) | the matcher | identical for both matchers — tree held fixed | **Valid** |
| Policy table (+301) | the aligned tree | *is the thing under test* | **Circular** |

When comparing two alignments, the score must come from something the alignment
cannot move. Surya's per-line text is that: Surya read those pixels once, and its
text at a bbox is invariant across both trees. **The binder result stands; do not
discard it along with the table.**

### What to do instead

- **Ship the binder.** 961 repairs at 0.12% regression, measured against the old
  tree, so it does not depend on any alignment decision. It fixes the bug that was
  actually reported.
- **Keep all three pipeline code fixes** (manual preservation, slug ranking,
  inversion-aware column selection). They improve what the pipeline does next time
  regardless of which tree is kept.
- **Leave the alignment data unapplied.** To restore the pre-re-align tree:
  `cd directory-pipeline/output && tar -xzf _ocr_backups/green_books_aligned_2026-09-04/aligned.tar.gz -C . -X _quarantine/hallucinated-blank-pages-2026-10-17/exclude-from-restore.txt`
  (verified byte-identical, 6,208 files). The `-X` list, added 2026-10-17, skips the 50 files
  built from OCR that Gemini invented on blank pages. Without it the restore puts them back where
  extraction will read them. See that folder's README.

After shipping the binder, re-bind and regenerate only the thumbnails that change:

```bash
uv run python tools/patch_canvas_fragments.py output/green_books_and_related/ \
    --aligned-model <slug> --dry-run      # inspect first
python scripts/build_all_thumbs.py --format webp --jobs 7 ...   # resumable, skips existing
python scripts/publish_thumbs.py --resume
```

Thumbnails are content-addressed on `sha1(canvas_fragment)[:12]`, so a changed
fragment makes a new file and orphans the old one on HF. Orphans are harmless.

## What was nearly lost — read this before running anything with `--force`

Two irreplaceable assets had no backup. Both now do.

**Hand alignments — 6,962 lines across 473 pages.** Made in the `--review-alignment` UI,
stored as `confidence: "manual"` inside `*_aligned.json`. `align_ocr.py --force` rewrote
those files *without reading them first*, and `output/` is gitignored, so there was no
recovery path. 3,951 of them are in the 1966–67 edition alone — almost certainly hand-fixed
*because* it is the worst volume in the corpus (7.21% hard error rate).

- Now extracted to **`alignment_ground_truth.json`** in this repo (committed, 2.7 MB),
  rebuilt by `scripts/extract_manual_alignments.py` (has `--check`).
- `align_ocr.py` now preserves manual lines across `--force` (peer's fix, 9 tests).

> **Corrected 2026-09-05 — the preservation evidence is thinner than first reported.**
> "6,962/6,962 survived three forced re-aligns" is arithmetically true and materially
> misleading. Only **859 lines across 144 pages** were in files any run actually
> rewrote; the other 6,103 survived because nothing wrote to them. Of the 859
> genuinely at risk, 859 survived and 0 were lost — so the fix works, at ~12% of the
> claimed scope. **Before any future `--force`, verify on files that will actually be
> written** — select targets by mtime *after* the run, not by what is in the tree.

**Retired-model OCR — 7,412 files.** `gemini-2.0-flash` was retired by the API mid-session
and returns 404. **43 of 45 volumes have it as their only transcription.** It cannot be
regenerated at any price.

- Backed up to `directory-pipeline/output/_ocr_backups/gemini_ocr_text_2026-09-04/`
  (11,354 files, 10 MB, restore-tested: 0 byte mismatches).

> **The rule worth keeping.** Every other artifact — page scans, Surya output, alignments,
> entries, thumbnails — is reproducible from the images. Hand corrections are not, and now
> neither is the 2.0-flash text. They should be what the code protects hardest; instead a
> single flag erased one and a model retirement froze the other.

The hand alignments are also more useful than insurance: they are the **only human-verified
data in the project**, which makes them a ground-truth set. Any future claim about
alignment quality can be checked against them rather than argued. Note the set is skewed —
~70% of the Green Book records are the 1966–67 volume — so it is a hard-case benchmark, not
a representative sample.

---

## What shipped

### This repo

| File | What |
|---|---|
| `alignment_ground_truth.json` | 6,962 hand-verified alignments, lifted out of the gitignored tree |
| `scripts/extract_manual_alignments.py` | Rebuilds it; `--check` fails on drift |
| `alignment_audit.csv` | 8,901 flagged rows — entry text, the text its box actually contains, similarity |
| `alignment_audit_single_col.csv` | Subset used for the single-column investigation |

### directory-pipeline

| File | What |
|---|---|
| `utils/entry_binding.py` | **New.** The shared matcher. Identity fields only, one-to-one assignment, refusal as a first-class outcome |
| `tools/audit_entry_bindings.py` | **New.** Ground-truth-free placement audit + `--a-b`; refuses to run on a tree being written |
| `tools/collate_review_queue.py` | **New.** Collates unplaced entries, ranked by nearest miss |
| `pipeline/extract_entries.py` | Uses the shared matcher; 66 lines of dead matcher removed; stamps `aligned_model` and `unplaced_entries` into each page's output |
| `tools/patch_canvas_fragments.py` | Uses the shared matcher; mode gate widened to `multimodal` |
| `tools/compare_alignments.py` | Collapsed onto `utils/column_utils` helpers (verified identical on 57 real pages) |
| `tests/test_entry_binding.py`, `tests/test_patch_canvas_fragments.py` | 53 tests, one per real misplacement using actual entry text |

**440 tests pass** across both sessions' work.

### Binder measurements (against the pre-re-align tree)

```
961 broken bindings repaired | 935 refused to the review queue | 0.12% regression
```

Two design choices came from measurement, and both first attempts were wrong — noted so
nobody re-proposes them:

- **Monotonic reading-order constraint**: intuitive, much worse (251 regressions, refusing
  bindings scoring a perfect 1.0). NER entry order does not reliably track aligned-line order.
- **Recall-weighted scoring** instead of token-set F1: worse on both axes.

What did work: accepting a match when the entry's full name is *contained* in the line
regardless of what else is there (Green Book lines carry tariff codes the entry doesn't —
`Broadmoor Hotel-(450B) E. $5.25 up`), and falling back to name-only when the address
wrapped to the next line.

---

## Reproducing the measurements

All of it runs offline from files on disk. No API calls, no image fetches.

```bash
cd ~/github/directory-pipeline

# 1. Placement audit of the published CSVs
.venv/bin/python tools/audit_entry_bindings.py output \
  --csv ~/github/green-books/green_book_entries_all.csv \
  --csv ~/github/green-books/travel_guides_all.csv \
  --resolve coverage --report /tmp/audit.csv --a-b

# 2. Verify hand alignments survived
cd ~/github/green-books && python3 scripts/extract_manual_alignments.py --check

# 3. Restore the pre-re-align tree for A/B comparison
mkdir -p /tmp/_oldtree && tar -xzf \
  ~/github/directory-pipeline/output/_ocr_backups/green_books_aligned_2026-09-04/aligned.tar.gz \
  -C /tmp/_oldtree
```

`--resolve` matters: use `overlap` when auditing already-shipped fragments (it identifies
which alignment actually produced the data), `coverage` after a re-align once fragments
have moved.

---

## Traps that cost time today

Every one of these produced a number that looked decisive and was wrong. They are listed
because each is easy to repeat.

1. **Picking a page's aligned JSON with `sorted()[0]`.** Alphabetical order, so
   `gemini-2.0-flash` beat `gemini-3-flash-preview` deterministically. This bug existed
   *simultaneously* in the pipeline (`_detect_aligned_slug`) and in the audit tool written
   to diagnose it. It reported 1,156 orphaned boxes against a true 134, and wrongly
   declared a whole volume unrecoverable. **Root cause: nothing records which alignment
   produced a given `canvas_fragment`.** `extract_entries.py` now stamps `aligned_model`;
   that closes the class.
2. **Auditing a tree while an alignment run is writing it.** Reported 9,588 orphans.
   `audit_entry_bindings.py` now refuses unless `--allow-unstable`.
3. **Extrapolating from the worst pages.** A coverage gain measured on the worst 8% was
   generalised to a corpus that is 59% already-excellent pages. Coverage counts how many
   lines got *a* box; it cannot see whether the box is on the right line.
4. **Reading an aggregate without disaggregating.** A −291 placement result read as "roll
   it back"; bucketing showed gains in every group with headroom and one volume responsible
   for 66% of the loss.
5. **Trusting a verification tool that fails open.** `find -newermt "-60 seconds"` errors
   on this machine (bfs wants ISO 8601) but the pipeline still reports `0`, so a
   quiescence check reads as "quiet" without ever running. `find -mmin -N` works — sanity
   check any such probe by confirming it returns non-zero when it should.
6. **Labelling comparison buckets from the tree under test.** Would let the thing being
   measured move pages between buckets. Bucket labels come from the *old* tree.
7. **`discover_ocr_slug` prefers aligned JSONs, but the aligner needs the `.txt`.**
   In 7 directories (1,448 files) auto-detect returned a slug that had aligned JSONs
   from an earlier run but no OCR text at all, so `align_image` returned `missing` for
   every page. Under `--quiet` nothing printed and the run logged clean while doing
   nothing. This is why `fdb5a8d0` — the 1966-67 volume holding 3,951 manual
   corrections — was never touched, and why the preservation demo page still has an
   April mtime. **Not yet fixed.** The fix (require the slug to have `.txt` files when
   auto-detecting for the aligner) must land before any further re-align, or the next
   run skips the same 1,448 files.
8. **Scoring a comparison with a quantity the comparison can move.** See the metric
   table under "The open decision" — the withdrawn +301 is the worked example.

---

## Still open

| Thread | Detail |
|---|---|
| **The decision above** | Nothing proceeds until it's made |
| 1947 volume (`4bea2040`) | Two-thirds of its regression explained and fixed; the rest isn't. Understand before trusting the aligner on a new collection |
| 3-column pages | −22 placements across 52,610 bindings (0.04%) — noise level, unexplained |
| 80 backward model flips | Pages preferring `gemini-2.0-flash` over `gemini-3-flash-preview` under the new coverage ranking |
| 134 genuine orphans | 132 N.H.A. + 2 stragglers, from an alignment run overwritten before anything recorded it |
| 21 degenerate pages | Need re-OCR; blocked by the model retirement. See `directory-pipeline/docs/plans/degenerate-page-reocr.md` |
| **NER re-extraction — never measured** | Every comparison here holds NER output fixed by construction, so none can see whether better page text would yield better *entries*. Testing it costs a full re-extraction. It was **not** ruled out; it was never run |
| `discover_ocr_slug` | Silently skips directories whose detected slug has no `.txt`. Must be fixed before any further re-align |
| `text_weak` band | ~5,000 rows at 0–0.34 similarity, **uncalibrated**. Sampling showed it is mostly benign (entries wrapped across two lines, correctly bound to the name line). Do not quote it as an error count |

## Contacts / provenance

- Backups: `directory-pipeline/output/_ocr_backups/green_books_aligned_2026-09-04/`
  (aligned JSONs) and `gemini_ocr_text_2026-09-04/` (OCR text). Both have `FILELIST.txt`
  and both were restore-tested with `cmp`, not assumed.
- `output/` is gitignored in `directory-pipeline`. Those backups are the only copies.
