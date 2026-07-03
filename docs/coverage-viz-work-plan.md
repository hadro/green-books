# Work plan: "Coverage across publications" grid

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

- [ ] **Shorten the longest row labels.** "Hackley & Harrison's" → "Hackley's"
      (or "H&H"), "Travelers Guide" → "Travelers". Keep full names in the cell
      aria-labels/tooltips. (Alternative if truncation feels lossy: stack each
      publication label on its own line above its cell row.)
- [ ] **Collapse dead spans into marked breaks.** 1932–1936 and 1942–1946 have
      *no* publication active. Render each as one narrow `⋯` break column
      instead of 5 hatched columns (−10 of 37 columns). Label the second break
      explicitly — e.g. a small "WWII gap" note — it's the most historically
      interesting feature of the grid and currently reads as unexplained noise.
- [ ] **Safety net:** `overflow-x: auto` on the grid's wrapper so future data
      (new publications/years) degrades to scroll instead of silent clipping.
- [ ] **Acceptance:** at 420px sidebar width, the 1966 column is fully visible
      and clickable; a Green Book 1966 listing can be jumped to from the grid.

## Phase 2 — Make it the payoff feature

- [ ] **Summary headline line** under the "Coverage across publications"
      heading: e.g. **"Listed 22 times across 4 publications, 1938–1966."**
      Computed from the resolved group. This is also the accessible summary
      (see Phase 4).
- [ ] **Hover/focus tooltips on every cell.** Minimum: `title` attribute.
      Right version: small styled tooltip showing publication + year, and for
      listed cells the **name-as-printed and address for that year** (variants
      like "Miami Carver" vs "Miami Carver Hotel" are a feature — they expose
      the resolver's work and build trust). Same content on keyboard focus.
- [ ] **Quiet the "not published" state.** Drop the 45° hatch to near-nothing
      (very faint dot, or empty) so listings dominate the ink. "No listing"
      cells keep their visible outline, so absence-of-outline still reads as
      "not published." Update the legend to match.
- [ ] **Fix the legend/chart contradiction.** Legend's "Listed" swatch is
      black (`--gb-ink`) but listed cells are painted per-publication colors.
      Either label it "Listed (colored by publication)" or repaint listed
      cells in a single ink color. Preference: keep per-publication color
      (ties to table stripes + facet dots) and fix the legend text.
- [ ] **Bigger hit targets.** After Phase 1 frees width, target ~11–12px
      cells; extend each button's hit area beyond its painted square (the 1px
      gap can belong to the button; padding + background-clip, or a
      transparent border).
- [ ] **Rename the escape hatch.** "See all likely match listings" →
      "Show all N matching listings in the table →" (reuse the summary count).

## Phase 3 — Mobile compact mode

Current behavior keeps only years that have listings, rendered as adjacent
equal cells — the time axis silently becomes categorical (1938 can sit next to
1953). And because header labels only render on years divisible by 5, a
business listed in e.g. 1938 + 1941 gets **no year labels at all**. Legend is
skipped on mobile while hatch/empty states still appear.

- [ ] Keep the axis **contiguous** but trim to the group's min→max year
      (± 1 year of context) instead of listing-years-only.
- [ ] **Always label the first and last column**, plus every 5th in between.
- [ ] Show a **one-line legend** whenever empty/inactive states are present.
- [ ] Acceptance: on a 390px viewport, a two-listing group shows a labeled,
      temporally honest axis.

## Phase 4 — Accessibility

- [ ] **Replace the invalid ARIA grid.** `role="grid"` currently has cells as
      direct children (no `role="row"` wrappers), `aria-hidden` headers, and
      buttons without gridcell roles — screen readers will mangle it.
      Simplest correct structure: container as `role="img"` labeled with the
      Phase-2 summary sentence; listed-cell buttons remain ordinary labeled
      buttons in tab order.
- [ ] **Un-disable the current-entry cell.** `disabled` removes it from tab
      order, so keyboard users can never find "you are here." Use an enabled
      no-op button with `aria-current="true"` instead.
- [ ] Tooltip content must be reachable on keyboard focus, not hover-only.

## Phase 5 — Data honesty & palette (wider scope than this element)

- [ ] **Firmer over-merge cue.** Groups with strong divergence signals (many
      categories, many distinct addresses — e.g. the "Liberty Apt." group
      spans all 7 publications and 12 categories, almost certainly several
      businesses) should get a warning-toned note — "These listings may be
      more than one business" — not the current trivia-toned category count.
      The grid is exactly where an over-merge becomes a confident-looking
      false narrative ("this business survived 36 years").
- [ ] **Palette CVD pass** (affects table stripes and facet dots more than
      the grid, where row labels carry identity): nudge Travelers Guide
      purple lighter/pinker away from Go Guide blue; separate Green Book
      green / Hackley green / NHA teal in lightness. Re-validate adjacent
      pairs to ΔE ≥ 12 under deutan simulation before committing.

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
