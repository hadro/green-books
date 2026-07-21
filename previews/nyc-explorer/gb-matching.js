// gb-matching.js — shared business-matching resolver for the Green Books
// explorers. Loaded by all-volumes.html (production index build) and
// address-keying-test.html (the validation harness at /address-keying-test.html,
// which compares this resolver against the legacy name+city keying).
//
// Pipeline: rows bucket by (gbNewNameStem, gbNormCity), then gbResolveGroups
// separates each bucket into business-level groups using address signatures
// (house number + fuzzy street tokens) with dominance-based anchoring for
// intersection forms and a fallback ladder for rows with no address signal.
// All normalization is for KEYING ONLY — displayed values keep their
// original text.

// ────────────────────────────────────────────────────────────────────────────
// Name helpers — copied from production so the OLD column matches what's
// currently shipping.
// ────────────────────────────────────────────────────────────────────────────
function gbNormName(s) {
  return (s || "").toLowerCase().replace(/[^a-z0-9\s]/g, "").replace(/\s+/g, " ").trim();
}
const NAME_TAIL_NOISE = [
  /\s+tourist\s+homes?$/i, /\s+tourist\s+rooms?$/i, /\s+guest\s+house$/i,
  /\s+bar\s*&\s*grill$/i, /\s+night\s+club$/i, /\s+beauty\s+parlou?rs?$/i,
  /\s+beauty\s+shop$/i, /\s+barber\s+shop$/i, /\s+service\s+station$/i,
  /\s+drug\s+stores?$/i, /\s+hotels?$/i, /\s+motels?$/i, /\s+restaurants?$/i,
  /\s+cafes?$/i, /\s+caf[ée]$/i, /\s+cafeterias?$/i, /\s+inns?$/i,
  /\s+lodges?$/i, /\s+lodgings?$/i, /\s+taverns?$/i, /\s+grills?$/i,
  /\s+clubs?$/i, /\s+rooms?$/i, /\s+apartments?$/i, /\s+apt\.?$/i,
  /\s+pharmacy$/i, /\s+dining$/i, /\s+&$/, /\s+and$/i,
];
function gbStripNameTail(name) {
  let s = (name || "").trim();
  let changed = true;
  while (changed) {
    changed = false;
    for (const re of NAME_TAIL_NOISE) {
      const next = s.replace(re, "").trim();
      if (next !== s && next.length >= 3) { s = next; changed = true; break; }
    }
  }
  return s;
}

// ────────────────────────────────────────────────────────────────────────────
// Name stem (PROPOSED side only). On top of the production tail-strip:
//   - parenthetical descriptors: "Dew Drop Inn (Nite Club)" → "Dew Drop Inn"
//   - quoted taglines: 'ROSE META "House of Beauty"' → "ROSE META"
//   - possessive 's folds INTO a bare s ("Slaughter's" → "Slaughters"), not
//     away: the guides print the same business both ways ("Slaughters" /
//     "SLAUGHTER'S"), so deleting the s split them into different buckets.
//     Case-insensitive — the old /'s\b/ missed uppercase "SLAUGHTER'S".
//   - final-token plural fold ("slaughters" → "slaughter", token >= 5 chars,
//     never after "ss") so bare-s and s-less printings share one bucket.
//     Safe because bucketing only nominates candidates — the address
//     signature phases still decide the actual business-level merges
//     (full-dataset check: the fold changed 153 groups; a random sample was
//     uniformly the same business at the same address, and the West End /
//     St. Louis hard case keeps its splits).
// ────────────────────────────────────────────────────────────────────────────
function gbNewNameStem(name) {
  let s = (name || "").replace(/\([^)]*\)/g, " ");
  const unquoted = s.replace(/"[^"]*"/g, " ").replace(/\s+/g, " ").trim();
  if (unquoted.length >= 3) s = unquoted;
  s = s.replace(/['’]s\b/gi, "s");
  return gbNormName(gbStripNameTail(s)).replace(/([a-z]{3,}[^s\s])s$/, "$1");
}

// ────────────────────────────────────────────────────────────────────────────
// City normalization (PROPOSED side only — keying, never display).
// Rules verified against the data: 3,946 raw city strings → 2,601 keys.
//   - parentheticals are sub_region leakage: "NEW YORK CITY (HARLEM)"
//   - first comma starts state text: "St. Louis, Mo." / "New York, N. Y."
//   - punctuation/whitespace folds "St. Louis"/"ST. LOUIS", kills "§CHICAGO"
// The alias map is deliberately tiny: a generic "<X> city" → "<X>" fold is
// WRONG on this data (elizabeth city NC ≠ elizabeth NJ; boulder city NV ≠
// boulder CO; quebec city ≠ quebec province). Only aliases proven safe.
// ────────────────────────────────────────────────────────────────────────────
const CITY_ALIASES = {
  "new york city": "new york",   // 3,028 + 3,151 rows — same place, both forms heavily used
};
function gbNormCity(c) {
  let s = (c || "").toLowerCase();
  s = s.replace(/\([^)]*\)/g, " ");
  s = s.split(",")[0];
  s = s.replace(/[^\w\s]/g, " ").replace(/\s+/g, " ").trim();
  return CITY_ALIASES[s] || s;
}

// ────────────────────────────────────────────────────────────────────────────
// Old keying — current production. One bucket per (stripped name, city).
// ────────────────────────────────────────────────────────────────────────────
function oldKey(row) {
  const nf = ["name", "establishment_name", "firm_name", "business_name"]
    .find(k => row[k]);
  if (!nf) return null;
  const stem = gbNormName(gbStripNameTail(row[nf]));
  const city = (row.city || "").toLowerCase().trim();
  if (stem.length < 3) return null;
  return stem + "|" + city;
}

// ────────────────────────────────────────────────────────────────────────────
// Proposed: parse address into { number, streets }, then group rows whose
// signatures are "compatible" via pairwise union-find within each name+city
// bucket. Compatibility = shared street token (fuzzy) AND matching-or-null
// number.
// ────────────────────────────────────────────────────────────────────────────
const STREET_SUFFIXES = /\s*\b(sts?|streets?|aves?|avenues?|blvds?|boulevards?|rds?|roads?|pls?|places?|cts?|courts?|drs?|drives?|lns?|lanes?|hwys?|highways?|pkwys?|parkways?|terr?|terraces?|sqs?|squares?|way|circles?|cirs?)\.?\s*$/i;
const STREET_DIRECTIONALS = /\b(north|south|east|west|n|s|e|w|ne|nw|se|sw)\b\.?/gi;
// "at" joins intersection forms too: "7th Ave. at 125th St."
const STREET_SPLIT = /\s*(?:&| and | at |\/|,)\s*/i;

// Spelled-out ordinals → numeric, so "Seventh Ave." and "7th Ave." produce
// the same token. Covers the range that actually appears in street names.
const SPELLED_ORDINALS = {
  first: "1st", second: "2nd", third: "3rd", fourth: "4th", fifth: "5th",
  sixth: "6th", seventh: "7th", eighth: "8th", ninth: "9th", tenth: "10th",
  eleventh: "11th", twelfth: "12th",
};

// Placeholder strings that mean "no address", not an address. Parsing them
// would mint phantom street tokens ("specified"), creating a fake second
// signal group that strands genuinely-blank rows as singletons.
const ADDR_PLACEHOLDER = /^(n\/?a|not\s+specified|not\s+given|not\s+listed|none|unknown|unspecified|see\s+.*)$/i;

function gbParseAddress(addr, city, state) {
  const raw = (addr || "").trim();
  if (!raw || ADDR_PLACEHOLDER.test(raw)) return { number: null, streets: new Set(), raw: "" };
  // House number = leading digits NOT followed by an ordinal suffix —
  // "7th Ave. & 125th St." starts with a street name, not a house number.
  // The (?!\d…) also blocks backtracking from matching a PREFIX of an
  // ordinal ("125th" must not yield house number 12).
  const numMatch = raw.match(/^\s*(\d+)(?!\d|\s*(?:st|nd|rd|th)\b)/i);
  const number = numMatch ? parseInt(numMatch[1], 10) : null;
  const noNum = number !== null ? raw.replace(/^\s*\d+\s*/, "") : raw;
  const parts = noNum.split(STREET_SPLIT);
  // Address fields sometimes carry trailing city/state text ("…, New York 27,
  // N. Y." / "Miami, Florida") — tokens from the row's own city or state
  // fields are noise, not street names.
  const cityWords = new Set(
    ((city || "") + " " + (state || "")).toLowerCase()
      .replace(/[^a-z0-9\s]/g, " ").split(/\s+/).filter(w => w.length >= 3)
  );
  const streets = new Set();
  for (const p of parts) {
    const cleaned = p
      .replace(STREET_SUFFIXES, "")
      .replace(STREET_DIRECTIONALS, "")
      .replace(/[^a-zA-Z0-9\s]/g, "")  // keep digits so "3rd"/"42nd" survive
      .trim()
      .toLowerCase();
    const words = cleaned.split(/\s+/)
      .map(t => SPELLED_ORDINALS[t] || t)
      // Canonicalize numeric ordinals to bare digits so "148 St." and
      // "148th St." produce the same token (exact digit equality still
      // applies — "125" never matches "126").
      .map(t => t.replace(/^(\d+)(?:st|nd|rd|th)$/i, "$1"))
      .filter(t => t && !cityWords.has(t));
    // The 3-char floor drops alphabetic particles ("la", "de") but numeric
    // street tokens are meaningful at any length ("7" ← "7th Ave").
    const tokens = words.filter(t => t.length >= 3 || /^\d+$/.test(t));
    if (tokens.length > 0) streets.add(tokens[tokens.length - 1]);
    // Also add the concatenation of the part's words, so spacing variants of
    // the same street match: "La Salle" → {salle, lasalle} meets "LaSalle" →
    // {lasalle}. Short particles ("la", "de") survive inside the concat even
    // though they fall below the standalone token floor.
    if (words.length >= 2) {
      const concat = words.join("");
      if (concat.length >= 3) streets.add(concat);
    }
  }
  return { number, streets, raw };
}

// Levenshtein distance ≤ 1 — handles single-character OCR drifts like
// belle/beele/bell, vanderventer/vandeventer.
function leq1(a, b) {
  if (a === b) return true;
  const la = a.length, lb = b.length;
  if (Math.abs(la - lb) > 1) return false;
  // Walk both strings; allow at most one mismatch.
  let i = 0, j = 0, slack = 1;
  while (i < la && j < lb) {
    if (a[i] === b[j]) { i++; j++; continue; }
    if (slack === 0) return false;
    slack = 0;
    if (la === lb)       { i++; j++; }   // substitution
    else if (la < lb)    { j++; }         // insertion into a
    else                  { i++; }         // deletion from a
  }
  return (la - i) + (lb - j) <= slack;
}
// Numbered streets must match exactly — Levenshtein ≤ 1 would merge adjacent
// streets in grid cities ("7th" vs "8th", "5th" vs "6th").
const NUMERIC_ORDINAL = /^\d+(st|nd|rd|th)?$/;
function tokensMatch(a, b) {
  if (a === b) return true;
  if (NUMERIC_ORDINAL.test(a) || NUMERIC_ORDINAL.test(b)) return false;
  return leq1(a, b);
}
function streetsShareToken(a, b) {
  for (const ta of a) for (const tb of b) if (tokensMatch(ta, tb)) return true;
  return false;
}

// Bounded Levenshtein: true iff edit distance ≤ max. Early-exits per row so
// short street tokens stay cheap.
function levLE(a, b, max) {
  const la = a.length, lb = b.length;
  if (Math.abs(la - lb) > max) return false;
  let prev = new Array(lb + 1);
  for (let j = 0; j <= lb; j++) prev[j] = j;
  for (let i = 1; i <= la; i++) {
    const cur = new Array(lb + 1);
    cur[0] = i;
    let rowMin = cur[0];
    const ai = a[i - 1];
    for (let j = 1; j <= lb; j++) {
      const cost = ai === b[j - 1] ? 0 : 1;
      cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost);
      if (cur[j] < rowMin) rowMin = cur[j];
    }
    if (rowMin > max) return false;
    prev = cur;
  }
  return prev[lb] <= max;
}
// Looser token match, used ONLY where an exact house number already anchors the
// pair (phase 1). A shared house number + name stem + city makes a same-number
// street collision between two *different* businesses vanishingly unlikely, so
// we can absorb 2-edit OCR drift on longer street names ("albemarle" /
// "albermarle" / "albermale"; "willis" / "wlis") that Levenshtein ≤1 misses.
// The 2-edit budget applies only to tokens length ≥6, so short tokens ("oak" vs
// "elm") can't collapse; numbered streets stay exact (never merge 7th/8th).
function tokensMatchLoose(a, b) {
  if (a === b) return true;
  if (NUMERIC_ORDINAL.test(a) || NUMERIC_ORDINAL.test(b)) return false;
  const cap = Math.max(a.length, b.length) >= 6 ? 2 : 1;
  return levLE(a, b, cap);
}
function streetsShareTokenLoose(a, b) {
  for (const ta of a) for (const tb of b) if (tokensMatchLoose(ta, tb)) return true;
  return false;
}

// Phase-based resolver. Numbered rows merge with each other on (same number,
// fuzzy street match). Non-numbered rows then get *anchored* to one numbered
// group via a "fewest-listings on shared street wins" rule — preventing
// intersection addresses from bridging unrelated businesses on the corner.
function gbResolveGroups(rows) {
  const sigs = rows.map(r => gbParseAddress(r.address, r.city, r.state));
  const parent = rows.map((_, i) => i);
  function find(i) { while (parent[i] !== i) { parent[i] = parent[parent[i]]; i = parent[i]; } return i; }
  function union(i, j) { const ri = find(i), rj = find(j); if (ri !== rj) parent[ri] = rj; }

  const numberedIdx = [], nullIdx = [];
  rows.forEach((_, i) => (sigs[i].number !== null ? numberedIdx : nullIdx).push(i));

  // 1. Merge numbered rows pairwise: equal number AND (fuzzy street-token
  //    match OR at least one street set is empty — empty means we couldn't
  //    parse a street, not that the streets are different). The street test is
  //    the *loose* one here because the exact house number already anchors the
  //    pair, so 2-edit OCR drift on the street ("willis"/"wlis") shouldn't
  //    strand the same address as separate businesses.
  for (let a = 0; a < numberedIdx.length; a++) {
    for (let b = a + 1; b < numberedIdx.length; b++) {
      const i = numberedIdx[a], j = numberedIdx[b];
      if (sigs[i].number !== sigs[j].number) continue;
      const ei = sigs[i].streets.size === 0, ej = sigs[j].streets.size === 0;
      if (ei || ej || streetsShareTokenLoose(sigs[i].streets, sigs[j].streets)) union(i, j);
    }
  }

  // 2. Build a map of numbered groups → street tokens + size.
  const numberedGroups = new Map();  // root → { streets: Set, size: number }
  numberedIdx.forEach(i => {
    const root = find(i);
    if (!numberedGroups.has(root)) numberedGroups.set(root, { streets: new Set(), size: 0 });
    sigs[i].streets.forEach(s => numberedGroups.get(root).streets.add(s));
    numberedGroups.get(root).size++;
  });

  // 3. Anchor each non-numbered row to a numbered group when the choice is
  //    unambiguous: a sole candidate sharing street tokens, or one candidate
  //    dominating the runner-up ≥3× (a lone OCR-mangled house number like
  //    "2029" beside eleven "2090" listings shouldn't veto anchoring).
  //    Genuinely contested corners — West End's "Belle & Vandevanter"
  //    bridging the hotel and three Vanderventer businesses of similar
  //    weight — stay unanchored, to merge in phase 4 only with other
  //    null-number rows via shared streets.
  nullIdx.forEach(nIdx => {
    const nStreets = sigs[nIdx].streets;
    if (nStreets.size === 0) return;
    const candidates = [];
    for (const [groot, g] of numberedGroups) {
      if (streetsShareToken(nStreets, g.streets)) candidates.push({ root: groot, size: g.size });
    }
    candidates.sort((a, b) => b.size - a.size);
    if (candidates.length === 1 ||
        (candidates.length > 1 && candidates[0].size >= 3 * candidates[1].size)) {
      union(nIdx, candidates[0].root);
    }
  });

  // 4. Merge remaining non-numbered singletons that share streets with each
  //    other (intersection variants of the same intersection).
  const stillSingleton = nullIdx.filter(i => find(i) === i);
  for (let a = 0; a < stillSingleton.length; a++) {
    for (let b = a + 1; b < stillSingleton.length; b++) {
      const i = stillSingleton[a], j = stillSingleton[b];
      if (find(i) === find(j)) continue;
      if (sigs[i].streets.size && sigs[j].streets.size &&
          streetsShareToken(sigs[i].streets, sigs[j].streets)) union(i, j);
    }
  }

  // 5. No-signal rows (blank address, or address that reduced to pure
  //    city/state text). Ladder:
  //      - bucket has ONE signal-bearing group, or one that dominates the
  //        runner-up ≥3× → join it (the overwhelmingly plausible home)
  //      - bucket has NO signal-bearing groups → merge no-signal rows with
  //        each other (pure name+city fallback — matches old behavior for
  //        the ~8% of rows with no address at all)
  //      - otherwise → genuinely ambiguous; leave as singletons
  const noSignal = rows.map((_, i) => i)
    .filter(i => sigs[i].number === null && sigs[i].streets.size === 0);
  const signalRootSize = new Map();
  rows.forEach((_, i) => {
    if (sigs[i].number !== null || sigs[i].streets.size > 0) {
      const r0 = find(i);
      signalRootSize.set(r0, (signalRootSize.get(r0) || 0) + 1);
    }
  });
  const ranked = [...signalRootSize.entries()].sort((a, b) => b[1] - a[1]);
  if (ranked.length === 1 || (ranked.length > 1 && ranked[0][1] >= 3 * ranked[1][1])) {
    noSignal.forEach(i => union(i, ranked[0][0]));
  } else if (ranked.length === 0) {
    for (let a = 1; a < noSignal.length; a++) union(noSignal[a], noSignal[0]);
  }

  const groups = new Map();
  rows.forEach((r, i) => {
    const root = find(i);
    if (!groups.has(root)) groups.set(root, { rows: [], sigs: [] });
    groups.get(root).rows.push(r);
    groups.get(root).sigs.push(sigs[i]);
  });
  return [...groups.values()];
}

// ────────────────────────────────────────────────────────────────────────────
// Production entry points
// ────────────────────────────────────────────────────────────────────────────

// Build the full cross-listing index for a merged row set. Returns
// { index: Map<groupKey, row[]>, rowToKey: Map<row, groupKey> }.
// Records its own build time on gbBuildMatchIndex.lastBuildMs.
function gbBuildMatchIndex(rows) {
  const t0 = (typeof performance !== "undefined" ? performance.now() : Date.now());
  const nf = rows.length
    ? ["name", "establishment_name", "firm_name", "business_name"].find(k => k in rows[0])
    : null;
  const index = new Map();
  const rowToKey = new Map();
  if (!nf) { gbBuildMatchIndex.lastBuildMs = 0; return { index, rowToKey }; }

  const buckets = new Map();
  for (const row of rows) {
    const stem = gbNewNameStem(row[nf]);
    if (stem.length < 3) continue;
    const bk = stem + "|" + gbNormCity(row.city);
    let b = buckets.get(bk);
    if (!b) buckets.set(bk, b = []);
    b.push(row);
  }
  buckets.forEach((bucketRows, bk) => {
    if (bucketRows.length === 1) {
      // Fast path: nothing to resolve.
      index.set(bk, bucketRows);
      rowToKey.set(bucketRows[0], bk);
      return;
    }
    gbResolveGroups(bucketRows).forEach((g, gi) => {
      const key = bk + "#" + gi;
      index.set(key, g.rows);
      g.rows.forEach(r => rowToKey.set(r, key));
    });
  });
  gbBuildMatchIndex.lastBuildMs =
    (typeof performance !== "undefined" ? performance.now() : Date.now()) - t0;
  return { index, rowToKey };
}

// Human-readable search query for "See all likely match listings": applies
// the same descriptor strips as gbNewNameStem but keeps the original casing
// so the search box shows a natural-looking query.
function gbSearchQueryName(name) {
  let s = (name || "").replace(/\([^)]*\)/g, " ");
  const unquoted = s.replace(/"[^"]*"/g, " ").replace(/\s+/g, " ").trim();
  if (unquoted.length >= 3) s = unquoted;
  // Fold the possessive into a bare s rather than deleting it: search
  // normalization strips the apostrophe from haystacks ("Ada's" \u2192 "adas"),
  // so "Adas" matches both printed forms while "Ada" matches neither.
  s = s.replace(/['\u2019]s\b/gi, "s");
  return gbStripNameTail(s.replace(/\s+/g, " ").trim());
}
