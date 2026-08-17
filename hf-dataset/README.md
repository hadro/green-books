---
license: cc0-1.0
pretty_name: African American Travel Guides — Green Book & Companion Directories (1930–1966)
language:
  - en
tags:
  - digital-humanities
  - african-american-history
  - historical-geography
  - green-book
  - gis
  - archives
size_categories:
  - 100K<n<1M
source_datasets:
  - original
task_categories:
  - text-classification
  - token-classification
configs:
  - config_name: default
    data_files:
      - split: train
        path: travel_guides_green_book_all.csv
dataset_info:
  config_name: default
  features:
    - name: publication
      dtype: string
    - name: source_corpus
      dtype: string
    - name: volume_id
      dtype: string
    - name: volume_title
      dtype: string
    - name: volume_year
      dtype: string
    - name: name
      dtype: string
    - name: proprietor
      dtype: string
    - name: category
      dtype: string
    - name: category_normalized
      dtype: string
    - name: address
      dtype: string
    - name: city
      dtype: string
    - name: state
      dtype: string
    - name: state_normalized
      dtype: string
    - name: phone
      dtype: string
    - name: rates
      dtype: string
    - name: notes
      dtype: string
    - name: is_advertisement
      dtype: string
    - name: is_recommended
      dtype: string
    - name: canvas_fragment
      dtype: string
    - name: image
      dtype: string
  splits:
    - name: train
      num_examples: 113827
---

# African American Travel Guides: The Green Book & Companion Directories (1930–1966)

A unified, structured dataset of **113,827 business and lodging listings** transcribed from **50 volumes** of mid-20th-century African American travel guides, spanning **1930–1966**. During the Jim Crow era, these guides told Black travelers which hotels, restaurants, tourist homes, service stations, and other businesses would serve them safely. This dataset brings *The Negro Motorist Green Book* together with seven lesser-known companion publications into a single comparable schema.

Every listing links back to the exact page region of the scanned source via IIIF (`canvas_fragment` / `image`), so any row can be traced to the original document.

> **Note on accuracy:** this data was transcribed and structured by a **vision-language model** (VLM), not by hand — the VLM performs both the OCR and the field extraction. On these dense, multi-column directory pages it sometimes confuses columns, mis-transcribes text, or mis-labels a listing's category. Treat fields as machine-generated, and verify against the source scan (`canvas_fragment` / `image`) when accuracy matters. You can browse the data with the source page images shown for each row in the live viewer: <https://hadro.github.io/green-books/all-volumes>. See [Extraction method](#extraction-method) and [Data quality & caveats](#data-quality--caveats).

## Publications covered

| Publication | Listings | Notes |
|---|---:|---|
| The Green Book | 67,052 | All 24 editions, 1937–1966 (titled *The Negro Motorist Green Book*, later *The Negro Travelers' Green Book* and *The Travelers' Green Book*), normalized to one series label |
| Travelguide | 28,581 | "Vacation & Recreation Without Humiliation", 1947–1962 |
| Go, Guide to Pleasant Motoring | 9,206 | |
| Afro-American's Travel Guide | 4,664 | Published by the Travel Bureau of the *Afro-American* newspapers (Baltimore), 1954–1958 editions |
| Hackley & Harrison's Hotel and Apartment Guide | 1,209 | Board, rooms, garage accommodations across ~300 US & Canadian cities |
| The Travelers Guide | 1,194 | |
| Smith's Tourist Guide | 1,022 | |
| NHA Directory and Guide to Travelers | 899 | |

Source volumes are digitized by **The New York Public Library** (Schomburg Center for Research in Black Culture and others). The 1946 Green Book edition is digitized by the [Library of Congress](https://www.loc.gov/item/2016298176/); all other volumes come from NYPL.

## Schema

20 columns. **Observed** = transcribed from the page; **Derived** = produced by an automated extraction/inference pipeline and should not be treated as ground truth. Note that "Observed" here still means *machine*-transcribed by a vision-language model (see [Extraction method](#extraction-method)), not human-keyed.

| Column | Origin | Fill % | Description |
|---|---|---:|---|
| `publication` | Observed | 100.0 | Series-level publication name (Green Book editions collapsed to "The Green Book") |
| `source_corpus` | Derived | 100.0 | Lineage flag: `green_book` or `travel_guides` |
| `volume_id` | Observed | 100.0 | NYPL Digital Collections UUID for the source volume (or, for the 1946 Green Book, the Library of Congress item ID 2016298176) |
| `volume_title` | Observed | 100.0 | Full title of the specific edition (carries the year) |
| `volume_year` | Observed | 100.0 | Publication year of the edition |
| `name` | Observed | 99.8 | Business or establishment name |
| `proprietor` | Observed | 4.6 | Owner/operator, where printed |
| `category` | **Derived** | 95.4 | Raw listing category as extracted (e.g. HOTELS, RESTAURANTS). Partly section-header-derived and partly model-inferred — see caveats |
| `category_normalized` | Derived | 100.0 | `category` folded to a canonical label (case-fold + typo/synonym groups); blanks → "Blank or no specific category". Folds 760 raw values → 463 |
| `address` | Observed | 92.4 | Street address as printed |
| `city` | Observed | 99.0 | City |
| `state` | Observed | 99.9 | State/region exactly as printed (raw) |
| `state_normalized` | Derived | 99.9 | `state` trimmed + uppercased (case-fold only, no gazetteer). Collapses 276 raw values → 208 |
| `phone` | Observed | 14.0 | Telephone, where printed |
| `rates` | Observed | 2.8 | Room/service rates, where printed |
| `notes` | Observed | 13.0 | Free-text notes from the listing |
| `is_advertisement` | Derived | 23.9 | Heuristic flag: listing came from a display ad |
| `is_recommended` | Derived | 18.2 | Heuristic flag: marked/recommended in source |
| `canvas_fragment` | Observed | 100.0 | IIIF canvas + `#xywh=` region locating the listing on the page |
| `image` | Observed | 100.0 | NYPL image identifier for the source page, or LOC IIIF service identifier for the 1946 edition |

## Rights & licensing

**License: CC0 1.0 (public domain dedication) for the dataset.**

Two independent bases support free reuse of this data:

1. **The listings are facts, and facts are not copyrightable.** Under *Feist Publications, Inc. v. Rural Telephone Service Co.*, 499 U.S. 340 (1991) — a case about a telephone directory — names, addresses, and categories in a directory carry no copyright. A faithful transcription of factual directory data is uncopyrightable regardless of the source document's status.
2. **Source-scan rights, verified against the NYPL API (49 NYPL volumes) and the Library of Congress item record (1 LOC volume):**
   - **49 of 50 volumes** are marked **Public Domain in the United States** — 48 NYPL volumes verified via the NYPL API (`NoC-US`, NYPL status `PDREN`) plus the **1946 Green Book** from the **Library of Congress**, which states no known restrictions on publication (`NoC-US`).
   - **1 of 50** — *Travelguide 1957* (2,483 listings) — is an **in-copyright orphan work** (`InC-RUU`, NYPL status `ICORPHAN`): NYPL identified a copyright notice, could not locate a rights-holder, and released it as an orphan work. Its *scan* is not public domain, but its *factual listings* remain uncopyrightable under (1). It is included here and flagged; per-volume rights are in [`volume_rights.csv`](volume_rights.csv).

   `volume_rights.csv` records one row per volume. Its `copyright_status` column (formerly `nypl_copyright_status`) holds each source institution's own status code or phrase — `PDREN`/`ICORPHAN` for NYPL, a plain-language phrase for LOC — since these vocabularies differ by institution; a `source_institution` column (`NYPL` or `LOC`) disambiguates which vocabulary applies to a given row.

Attribution to NYPL is **not legally required** but is requested as a courtesy: *"From The New York Public Library."* For the 1946 edition: *"From the Library of Congress."*

## Historical sensitivity

These records document real businesses and, in the case of tourist/guest homes, **private residences of real people**, published because segregation made ordinary travel dangerous for Black Americans. Addresses appear as printed. Please use this data with respect for that context — for historical, educational, and research purposes — and be mindful that some listed addresses are private homes.

## Data quality & caveats

This corpus is published as faithfully-transcribed data with **light** post-processing. Known issues:

- **Raw vs normalized `state`/`category`.** The raw `category` and `state` columns appear exactly as extracted, including **case inconsistencies** (`NEW YORK` vs `New York`, `GENERAL` vs `General`) and near-duplicate labels (`Hotels and Motels`, `Hotels-Motels-Tourists`, `Hotels - Motels - Tourist Homes - Restaurants`). For convenience, **`category_normalized` and `state_normalized`** apply a mechanical fold — `category_normalized` uses a case-fold plus an explicit typo/synonym/section-header map (the same logic that powers the companion web explorer, shared via [`gb-categories.json`](https://github.com/hadro/green-books)), collapsing 760 → 463 labels; `state_normalized` is trim + uppercase only, collapsing 276 → 208. Both normalized columns are a mechanical cleanup, **not** an authoritative taxonomy or gazetteer — the `state` long tail still includes OCR noise and non-US locations (e.g. `CANADA`), and rare categories keep their (uppercased) raw form. Use the raw columns when you need the source values verbatim.
- **Vision-language-model extraction errors.** Both the OCR and the field extraction were done by a vision-language model reading the page images (see [Extraction method](#extraction-method)), not a human or a deterministic OCR/layout engine. On these dense, multi-column directory pages the model sometimes **confuses columns** — pulling a value into the wrong field or attaching it to the wrong listing — and can **mis-transcribe** unusual names/abbreviations or **mis-identify** a listing's category (e.g. a section-header category bleeding onto adjacent entries, or a `name`/`address` boundary drawn in the wrong place). These are systematic model-interpretation errors, not random noise, and they surface most in `category`, `name`, and `address`. When accuracy matters for a given row, check it against the source scan via `canvas_fragment` / `image`.
- **`category` is partly inferred**, not purely transcribed. Treat it as a helpful signal, not authoritative classification.
- **No cross-volume deduplication.** The same business recurs across editions and years by design — this is a listings-over-time corpus, not a deduplicated business registry. Group by (`name`, `address`, `city`) if you need unique establishments.
- **Sparse columns are expected**, not errors: `proprietor`, `rates`, `phone`, and `notes` were only printed for some listings and vary widely by publication.
- Internal QA/drift flags from the production pipeline are intentionally **not** included in this public release.

## Reconstructing a page image / viewer link

`canvas_fragment` encodes the IIIF canvas and the `#xywh=x,y,w,h` pixel region of the listing on the page; `image` is the NYPL image ID (or, for the 1946 edition, the LOC IIIF service identifier). Together they let you fetch the source page via NYPL's IIIF Image API — or the Library of Congress's for the 1946 edition — or deep-link into a IIIF viewer to see the original listing in context.

## Loading

```python
from datasets import load_dataset
ds = load_dataset("hadro/green-books-travel-guides")
print(ds["train"][0])
```

## Extraction method

Derived from digitized volumes in the NYPL Digital Collections via an automated, **vision-language-model (VLM) pipeline** — the extraction code is open source: **[hadro/directory-pipeline](https://github.com/hadro/directory-pipeline/)**. Two VLM-driven stages produce the data:

1. **VLM-OCR** — a vision-language model reads each scanned page *image* and transcribes its text, rather than a traditional OCR engine (e.g. Tesseract) operating on glyphs alone.
2. **VLM structuring / NER** — a vision-language model segments each page into individual listings and labels the fields (`name`, `address`, `category`, `phone`, …).

Because both stages depend on a model *interpreting* the page image — and these guides are dense, small-print, multi-column directory layouts — the output carries characteristic VLM error modes (column confusion, mis-transcription, field mis-identification) described under [Data quality & caveats](#data-quality--caveats). The upside of the VLM approach is that it recovers structure and readings that flat OCR misses; the tradeoff is these interpretation errors. Every row keeps a `canvas_fragment` / `image` pointer so any value can be verified against the original scan.

Companion IIIF viewer and Green Book explorer: <https://hadro.github.io/green-books/all-volumes>.

## Citation

```bibtex
@dataset{green_book_travel_guides,
  title  = {African American Travel Guides: The Green Book and Companion Directories (1930--1966)},
  author = {Hadro, Josh},
  year   = {2026},
  note   = {Structured listings transcribed from 50 digitized volumes, New York Public Library and Library of Congress Digital Collections},
  url    = {https://huggingface.co/datasets/hadro/green-books-travel-guides}
}
```
