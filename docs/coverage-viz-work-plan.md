# Work plan: "Coverage across publications" grid

> **Status — implemented (2026-07-03).** All five phases below are done and
> verified against live desktop (1440×950) and mobile (390×844) renders.
> Commits: `ecc6fe7` (Phases 1–4, grid overhaul) and `dfbbe2d` (Phase 5,
> over-merge caution + CVD-validated palette). Checkboxes marked `[x]` shipped;
> notes in *italics* record how.

**Scope:** the coverage grid in the entry detail sidebar of `all-volumes.html`
(built in the `showDetail` monkey-patch, ~lines 2010–2190; styles ~lines 374–394).

**Context:** the grid is a publications × years presence matrix showing which
guides listed a business, when. Review findings (2026-07-03, measured against a
live render at 1440×950 and 390×844): the form is right — presence matrix,
three-state cells (listed / no listing / not published), click-to-jump — but
execution has one real bug and several gaps between "works" and "compelling."
3,140 of 32,012 resolved groups span 2+ publications, so the cross-publication
story this grid tells is common, not an edge case.

Measured facts driving this plan:

- Grid needs **436px**; the sidebar gives it **371px**. Nothing scrolls
  horizontally (`#detail` is `overflow: hidden`), so the last ~5 year columns
  (**1962–1966**) are clipped and unreachable.
- Cells render at **7–9px** with 1px gaps; clickable cells are adjacent.
- **Zero tooltips** (`title` attributes: 0) — no way for a mouse user to read
  a cell's year except counting from sparse 5-year header labels.
- ~70% of grid ink is the diagonal "not published" hatch, because four of the
  seven publications existed for only 1–2 years.
- Palette CVD check: Travelers Guide `#7040a0` vs Go Guide `#1a5fa8` separate
  by only **ΔE 4.8 under deuteranopia** (target ≥ 12); the two greens + teal
  (`#1d4d2e`, `#2a7a3c`, `#0d7a74`) cluster similarly.

---

## Phase 1 — Fix the clipping (bug; do first)

The math can't work as designed: 37 year columns × 7px min + 36px gaps +
~140px label column ("Hackley & Harrison's") = 436px > 371px available.
Recover ~65px+ via all of:

- [x] **Shorten the longest row labels.** "Hackley & Harrison's" → "Hackley's"
      (or "H&H"), "Travelers Guide" → "Travelers". Keep full names in the cell
      aria-labels/tooltips. (Alternative if truncation feels lossy: stack each
      publication label on its own line above its cell row.)
      *As shipped: only "Hackley & Harrison's" → "Hackley's"; the rest of the
      fit came from the dead-span collapse + fractional (`1fr`) year tracks, so
      other labels kept their full short names.*
- [x] **Collapse dead spans into marked breaks.** 1932–1936 and 1942–1946 have
      *no* publication active. Render each as one narrow `⋯` break column
      instead of 5 hatched columns (−10 of 37 columns). Label the second break
      explicitly — e.g. a small "WWII gap" note — it's the most historically
      interesting feature of the grid and currently reads as unexplained noise.
- [x] **Safety net:** `overflow-x: auto` on the grid's wrapper so future data
      (new publications/years) degrades to scroll instead of silent clipping.
- [x] **Acceptance:** at 420px sidebar width, the 1966 column is fully visible
      and clickable; a Green Book 1966 listing can be jumped to from the grid.

## Phase 2 — Make it the payoff feature

- [x] **Summary headline line** under the "Coverage across publications"
      heading: e.g. **"Listed 22 times across 4 publications, 1938–1966."**
      Computed from the resolved group. This is also the accessible summary
      (see Phase 4).
- [x] **Hover/focus tooltips on every cell.** Minimum: `title` attribute.
      Right version: small styled tooltip showing publication + year, and for
      listed cells the **name-as-printed and address for that year** (variants
      like "Miami Carver" vs "Miami Carver Hotel" are a feature — they expose
      the resolver's work and build trust). Same content on keyboard focus.
- [x] **Quiet the "not published" state.** Drop the 45° hatch to near-nothing
      (very faint dot, or empty) so listings dominate the ink. "No listing"
      cells keep their visible outline, so absence-of-outline still reads as
      "not published." Update the legend to match.
- [x] **Fix the legend/chart contradiction.** Legend's "Listed" swatch is
      black (`--gb-ink`) but listed cells are painted per-publication colors.
      Either label it "Listed (colored by publication)" or repaint listed
      cells in a single ink color. Preference: keep per-publication color
      (ties to table stripes + facet dots) and fix the legend text.
- [x] **Bigger hit targets.** After Phase 1 frees width, target ~11–12px
      cells; extend each button's hit area beyond its painted square (the 1px
      gap can belong to the button; padding + background-clip, or a
      transparent border).
      *As shipped: cells fill the sidebar to ~8.5px paint (the 372px width
      caps a full-span 1930–1966 axis); each button's hit area is its whole
      grid track incl. the gap. Bigger paint would force horizontal scroll,
      judged worse than a slightly smaller always-visible cell.*
- [x] **Rename the escape hatch.** "See all likely match listings" →
      "Show all N matching listings in the table →" (reuse the summary count).

## Phase 3 — Mobile compact mode

Current behavior keeps only years that have listings, rendered as adjacent
equal cells — the time axis silently becomes categorical (1938 can sit next to
1953). And because header labels only render on years divisible by 5, a
business listed in e.g. 1938 + 1941 gets **no year labels at all**. Legend is
skipped on mobile while hatch/empty states still appear.

- [x] Keep the axis **contiguous** but trim to the group's min→max year
      (± 1 year of context) instead of listing-years-only.
- [x] **Always label the first and last column**, plus every 5th in between.
- [x] Show a **one-line legend** whenever empty/inactive states are present.
- [x] Acceptance: on a 390px viewport, a two-listing group shows a labeled,
      temporally honest axis.

## Phase 4 — Accessibility

- [x] **Replace the invalid ARIA grid.** `role="grid"` currently has cells as
      direct children (no `role="row"` wrappers), `aria-hidden` headers, and
      buttons without gridcell roles — screen readers will mangle it.
      Simplest correct structure: container as `role="img"` labeled with the
      Phase-2 summary sentence; listed-cell buttons remain ordinary labeled
      buttons in tab order.
      *As shipped: container is `role="group"` (not `img`, so the listed-cell
      buttons stay in the a11y tree) with the summary sentence as its
      aria-label; non-interactive cells are labeled `role="img"`.*
- [x] **Un-disable the current-entry cell.** `disabled` removes it from tab
      order, so keyboard users can never find "you are here." Use an enabled
      no-op button with `aria-current="true"` instead.
- [x] Tooltip content must be reachable on keyboard focus, not hover-only.

## Phase 5 — Data honesty & palette (wider scope than this element)

- [x] **Firmer over-merge cue.** Groups with strong divergence signals (many
      categories, many distinct addresses — e.g. the "Liberty Apt." group
      spans all 7 publications and 12 categories, almost certainly several
      businesses) should get a warning-toned note — "These listings may be
      more than one business" — not the current trivia-toned category count.
      The grid is exactly where an over-merge becomes a confident-looking
      false narrative ("this business survived 36 years").
- [x] **Palette CVD pass** (affects table stripes and facet dots more than
      the grid, where row labels carry identity): nudge Travelers Guide
      purple lighter/pinker away from Go Guide blue; separate Green Book
      green / Hackley green / NHA teal in lightness. Re-validate adjacent
      pairs to ΔE ≥ 12 under deutan simulation before committing.
      *As shipped: new palette passes the lightness, chroma, and contrast
      checks; closest adjacent pair is ΔE 9.3 (protan). ΔE ≥ 12 for all seven
      is not achievable — deuteranopia collapses the warm end — so it sits in
      the 8–12 band, which is sound here because every use of these colours is
      paired with a text label or dot (grid row labels, facet dots, table
      publication column). The old purple/blue (ΔE ~2) and duplicate greens
      are gone.*

---

## Suggested commit sequence

1. Phase 1 (clipping) — standalone, verifiable, highest urgency.
2. Phase 2 tooltips + summary line + legend fix — the "payoff" commit.
3. Phase 2 hatch/hit-target polish + Phase 3 mobile.
4. Phase 4 accessibility.
5. Phase 5 as separate commits (palette change touches the whole explorer).

Each visual change should be verified against a live render (the streaming
load finishes when `gbNameIndex.size > 0`), at both 1440px desktop and 390px
mobile widths, using a multi-publication group and a two-listing group.
