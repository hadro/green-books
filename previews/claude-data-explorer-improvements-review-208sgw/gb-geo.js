// gb-geo.js — shared Nominatim geocode cache for the Green Book explorers.
// Loaded by explorer.html (Green Book only) and all-volumes.html (Green Book
// + travel guides merged).
//
// Persistent geocode cache: re-opening an entry (or another entry that falls
// back to the same city query), reloading the page, or switching between
// explorer.html and all-volumes.html all reuse the earlier result instead of
// re-hitting Nominatim — friendlier to its 1 req/s usage policy, and it
// survives across sessions since results are keyed by query text and rarely
// change. Empty results are cached too.
//
// Storage shape (single localStorage key GB_GEO_STORAGE_KEY):
//   { v: 1, entries: { [query]: { p: [{lat, lon}, ...], t: <ms timestamp> } } }
// Only lat/lon are persisted (Nominatim returns extra fields callers don't
// use); entries are capped at GB_GEO_MAX_ENTRIES, evicting the oldest by `t`
// when over the cap.
const GB_GEO_STORAGE_KEY = "gbGeoCache";
const GB_GEO_MAX_ENTRIES = 300;
const GB_GEO_EVICT_COUNT = 50;

// Nominatim's usage policy asks that automated clients identify themselves so
// they can be contacted before being blocked. Browsers send a Referer from
// hadro.github.io, which partly covers it, but an explicit contact address is
// what the policy actually asks for; it is appended as &email= on every lookup.
//
// This is a relay alias, not a personal inbox — the value is public in this repo
// and visible in Nominatim's request logs, so it should stay one. Set it to ""
// to send nothing. Request volume is already low: callers debounce, results are
// cached in localStorage, and NYC entries use precomputed coordinates instead.
const GB_GEO_CONTACT = "quinoa-surname-3h@icloud.com";

const _geoCache = new Map();
let _geoCacheLoaded = false;

function _gbGeoLoad() {
  if (_geoCacheLoaded) return;
  _geoCacheLoaded = true;
  try {
    const raw = localStorage.getItem(GB_GEO_STORAGE_KEY);
    if (!raw) return;
    const blob = JSON.parse(raw);
    if (!blob || blob.v !== 1 || typeof blob.entries !== "object") return;
    Object.entries(blob.entries).forEach(([query, entry]) => {
      if (entry && Array.isArray(entry.p) && typeof entry.t === "number") {
        _geoCache.set(query, entry);
      }
    });
  } catch (err) {
    // Corrupt JSON, unavailable storage, etc. — discard and run memory-only.
  }
}

function _gbGeoPersist() {
  try {
    if (_geoCache.size > GB_GEO_MAX_ENTRIES) {
      const byAge = [..._geoCache.entries()].sort((a, b) => a[1].t - b[1].t);
      for (let i = 0; i < GB_GEO_EVICT_COUNT && i < byAge.length; i++) {
        _geoCache.delete(byAge[i][0]);
      }
    }
    const entries = {};
    _geoCache.forEach((entry, query) => { entries[query] = entry; });
    localStorage.setItem(GB_GEO_STORAGE_KEY, JSON.stringify({ v: 1, entries }));
  } catch (err) {
    // Storage unavailable or over quota — drop the persisted blob and
    // continue serving the in-memory Map only.
    try { localStorage.removeItem(GB_GEO_STORAGE_KEY); } catch (err2) { /* ignore */ }
  }
}

function gbGeocode(query, signal) {
  _gbGeoLoad();
  const cached = _geoCache.get(query);
  if (cached) return Promise.resolve(cached.p);
  const contact = GB_GEO_CONTACT ? "&email=" + encodeURIComponent(GB_GEO_CONTACT) : "";
  return fetch("https://nominatim.openstreetmap.org/search?format=json&limit=1&q=" + encodeURIComponent(query) + contact, { signal })
    .then(r => r.json())
    .then(results => {
      const trimmed = (results || []).map(r => ({ lat: r.lat, lon: r.lon }));
      _geoCache.set(query, { p: trimmed, t: Date.now() });
      _gbGeoPersist();
      return trimmed;
    });
}
