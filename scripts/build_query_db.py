#!/usr/bin/env python3
"""build_query_db.py — fold the two source CSVs into one queryable SQLite file.

The explorers read the CSVs directly in the browser; this builds the same corpus
as a local read-only database so agents and scripts can ask questions of it
without parsing 34 MB of CSV per query.

    python3 scripts/build_query_db.py            # -> green_books.sqlite
    python3 scripts/build_query_db.py --check    # exit 1 if stale/missing

What it produces:

  listings      109,163 rows, both corpora in one schema (the Hugging Face
                20-column schema plus the fields the explorers use). Adds
                `thumb_id` (the content-addressed thumbnail/geo key),
                `category_normalized` and `state_normalized` (folded through
                gb_categories.py, the same logic the browser uses), a `flags`
                summary column, and NYC coordinates joined from nyc_geo.json.
  listings_fts  FTS5 index over name / address / notes / proprietor.
  volumes       46 rows from hf-dataset/volume_rights.csv — per-volume rights
                provenance, so anything redistributing rows can check them.

The database is a derived artifact and is gitignored; rebuild it whenever the
CSVs change. `scripts/build_mcp_db.py` (see docs/mcp-server-plan.md) is planned
as a superset of this script, adding the precomputed cross-edition business
group IDs that the MCP server needs.
"""
import argparse
import csv
import hashlib
import json
import os
import sqlite3
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from gb_categories import gb_category_group, gb_state_normalize  # noqa: E402

DB_PATH = os.path.join(ROOT, "green_books.sqlite")
GB_CSV = os.path.join(ROOT, "green_book_entries_all.csv")
TG_CSV = os.path.join(ROOT, "travel_guides_all.csv")
GEO_JSON = os.path.join(ROOT, "nyc_geo.json")
RIGHTS_CSV = os.path.join(ROOT, "hf-dataset", "volume_rights.csv")

# Every Green Book edition collapses to one series label, matching the Hugging
# Face build — the volume_title still carries the specific edition and year.
GB_PUBLICATION = "The Green Book"

# Columns shared by both CSVs and carried through verbatim.
SHARED = [
    "volume_id", "volume_title", "volume_year",
    "name", "address", "state", "city", "sub_region",
    "category", "notes", "phone", "proprietor",
    "amenities_services", "rates", "personnel", "reference_number",
    "is_advertisement", "is_recommended", "canvas_fragment", "image",
]

# Quality columns. Both CSVs carry flag_*; only the Green Book CSV carries
# drift_*. A row's set flags are summarised into one comma-joined `flags`
# column so a query can filter on them without knowing which corpus it is in.
FLAG_COLS = [
    "flag_state_invalid", "flag_state_eq_city", "flag_name_address",
    "flag_header_row", "flag_duplicate", "flag_unanchored",
    "flag_hallucinated",
    "drift_geonames", "drift_window", "drift_cross_volume", "drift_alignment",
]

SCHEMA = """
CREATE TABLE listings (
  id                  INTEGER PRIMARY KEY,
  thumb_id            TEXT NOT NULL,
  source_corpus       TEXT NOT NULL,
  publication         TEXT NOT NULL,
  volume_id           TEXT NOT NULL,
  volume_title        TEXT,
  volume_year         INTEGER,
  name                TEXT,
  proprietor          TEXT,
  category            TEXT,
  category_normalized TEXT,
  address             TEXT,
  city                TEXT,
  sub_region          TEXT,
  state               TEXT,
  state_normalized    TEXT,
  phone               TEXT,
  rates               TEXT,
  notes               TEXT,
  amenities_services  TEXT,
  personnel           TEXT,
  reference_number    TEXT,
  is_advertisement    TEXT,
  is_recommended      TEXT,
  canvas_fragment     TEXT NOT NULL,
  image               TEXT,
  flags               TEXT,
  drift_score         REAL,
  lat                 REAL,
  lon                 REAL,
  neighborhood        TEXT,
  borough             TEXT,
  geo_approx          INTEGER
);

CREATE INDEX idx_listings_year        ON listings(volume_year);
CREATE INDEX idx_listings_publication ON listings(publication);
CREATE INDEX idx_listings_volume      ON listings(volume_id);
CREATE INDEX idx_listings_state       ON listings(state_normalized);
CREATE INDEX idx_listings_city        ON listings(city, state_normalized);
CREATE INDEX idx_listings_category    ON listings(category_normalized);
CREATE INDEX idx_listings_thumb       ON listings(thumb_id);
CREATE INDEX idx_listings_hood        ON listings(neighborhood);

CREATE VIRTUAL TABLE listings_fts USING fts5(
  name, address, notes, proprietor,
  content='listings', content_rowid='id', tokenize='unicode61'
);

CREATE TABLE volumes (
  volume_id           TEXT PRIMARY KEY,
  publication         TEXT,
  volume_title        TEXT,
  source_corpus       TEXT,
  rows                INTEGER,
  source_institution  TEXT,
  copyright_status    TEXT,
  rights_statement_uri TEXT,
  public_domain       TEXT
);

CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
"""


def thumb_id(canvas_fragment):
    """Content-addressed id: sha1(canvas_fragment)[:12].

    The same key the thumbnail CDN shards on and nyc_geo.json is keyed by, so it
    joins the corpus to both without a per-entry manifest.
    """
    return hashlib.sha1((canvas_fragment or "").encode("utf-8")).hexdigest()[:12]


def summarize_flags(row):
    """Comma-join the quality flags that are actually set on this row.

    A flag is 'set' when it is non-empty and not the literal 'ok'/'0' the
    pipeline writes for a clean check.
    """
    hits = []
    for col in FLAG_COLS:
        v = (row.get(col) or "").strip()
        if v and v.lower() not in ("ok", "0", "false", "no"):
            hits.append(col)
    return ",".join(hits)


def to_int(v):
    try:
        return int(str(v).strip())
    except (TypeError, ValueError):
        return None


def to_float(v):
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None


def read_rows(path, corpus, geo):
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            cf = row.get("canvas_fragment") or ""
            tid = thumb_id(cf)
            g = geo.get(tid) or [None, None, None, None, None]
            rec = {c: (row.get(c) or "").strip() for c in SHARED}
            rec.update(
                thumb_id=tid,
                source_corpus=corpus,
                # The Green Book CSV has no publication column — every row in it
                # is the same series.
                publication=(row.get("publication") or "").strip() or GB_PUBLICATION,
                volume_year=to_int(row.get("volume_year")),
                category_normalized=gb_category_group(row.get("category")),
                state_normalized=gb_state_normalize(row.get("state")),
                flags=summarize_flags(row),
                drift_score=to_float(row.get("drift_score")),
                lat=g[0], lon=g[1], neighborhood=g[2], borough=g[3],
                geo_approx=g[4],
            )
            yield rec


COLUMNS = [
    "thumb_id", "source_corpus", "publication",
    "volume_id", "volume_title", "volume_year",
    "name", "proprietor", "category", "category_normalized",
    "address", "city", "sub_region", "state", "state_normalized",
    "phone", "rates", "notes", "amenities_services", "personnel",
    "reference_number", "is_advertisement", "is_recommended",
    "canvas_fragment", "image", "flags", "drift_score",
    "lat", "lon", "neighborhood", "borough", "geo_approx",
]


def build(db_path):
    if os.path.exists(db_path):
        os.remove(db_path)
    geo = {}
    if os.path.exists(GEO_JSON):
        with open(GEO_JSON, encoding="utf-8") as f:
            geo = json.load(f)

    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)
    placeholders = ",".join("?" * len(COLUMNS))
    insert = f"INSERT INTO listings ({','.join(COLUMNS)}) VALUES ({placeholders})"

    total = 0
    for path, corpus in ((GB_CSV, "green_book"), (TG_CSV, "travel_guides")):
        batch = []
        for rec in read_rows(path, corpus, geo):
            batch.append([rec.get(c) for c in COLUMNS])
            if len(batch) >= 5000:
                con.executemany(insert, batch)
                total += len(batch)
                batch = []
        if batch:
            con.executemany(insert, batch)
            total += len(batch)

    # External-content FTS: populate once. The corpus is read-only after the
    # build, so no sync triggers are needed.
    con.execute(
        "INSERT INTO listings_fts(rowid, name, address, notes, proprietor) "
        "SELECT id, name, address, notes, proprietor FROM listings"
    )

    if os.path.exists(RIGHTS_CSV):
        with open(RIGHTS_CSV, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        con.executemany(
            "INSERT OR REPLACE INTO volumes VALUES (?,?,?,?,?,?,?,?,?)",
            [(r["volume_id"], r["publication"], r["volume_title"],
              r["source_corpus"], to_int(r["rows"]), r["source_institution"],
              r["copyright_status"], r["rights_statement_uri"],
              r["public_domain"]) for r in rows],
        )

    con.executemany(
        "INSERT INTO meta VALUES (?,?)",
        [("listings", str(total)),
         ("geocoded", str(sum(1 for v in geo.values() if v))),
         ("source_csv_sha", source_signature())],
    )
    con.commit()
    con.execute("VACUUM")
    con.execute("ANALYZE")
    con.commit()
    con.close()
    return total


def source_signature():
    """Cheap staleness signature: size + mtime of each source CSV."""
    parts = []
    for p in (GB_CSV, TG_CSV, GEO_JSON):
        if os.path.exists(p):
            st = os.stat(p)
            parts.append(f"{os.path.basename(p)}:{st.st_size}:{int(st.st_mtime)}")
    return "|".join(parts)


def check(db_path):
    if not os.path.exists(db_path):
        print(f"missing: {db_path} — run scripts/build_query_db.py", file=sys.stderr)
        return 1
    con = sqlite3.connect(db_path)
    try:
        stored = con.execute(
            "SELECT value FROM meta WHERE key='source_csv_sha'"
        ).fetchone()
    except sqlite3.DatabaseError:
        stored = None
    con.close()
    if not stored or stored[0] != source_signature():
        print("stale: source CSVs changed — rebuild with scripts/build_query_db.py",
              file=sys.stderr)
        return 1
    print("up to date")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--db", default=DB_PATH, help="output path (default green_books.sqlite)")
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if the database is missing or stale")
    args = ap.parse_args()

    if args.check:
        sys.exit(check(args.db))

    total = build(args.db)
    size_mb = os.path.getsize(args.db) / 1e6
    print(f"wrote {args.db} — {total:,} listings, {size_mb:.1f} MB")


if __name__ == "__main__":
    main()
