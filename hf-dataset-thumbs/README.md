---
license: cc0-1.0
pretty_name: African American Travel Guides — Listing Thumbnails (Green Book & Companion Directories)
language:
  - en
tags:
  - digital-humanities
  - african-american-history
  - green-book
  - iiif
  - images
  - archives
size_categories:
  - 100K<n<1M
source_datasets:
  - hadro/green-books-travel-guides
viewer: false
---

# African American Travel Guides: Listing Thumbnails

**113,053 pre-cropped thumbnail images — one per listing — from 50 volumes of mid-20th-century African American travel guides (1930–1966).** Each image is a small snippet of a scanned directory page cropped down to a single business or lodging listing: the exact region a traveler would have read.

This is the **image companion** to the structured-listings dataset [**hadro/green-books-travel-guides**](https://huggingface.co/datasets/hadro/green-books-travel-guides). That dataset holds the transcribed *text* of each listing; this one holds the *picture* of it. They join on a content hash of each listing's IIIF region (see [Finding a listing's thumbnail](#finding-a-listings-thumbnail)).

Its purpose is practical: it lets the companion web explorer show the source snippet for every one of ~114k listings **without sending live requests to the New York Public Library or Library of Congress image servers**. Browse it in context here: <https://hadro.github.io/green-books/all-volumes>.

## What's in here

- **Format:** WebP, quality 75, **400 px wide** (height varies with the listing), averaging ~3.9 KB per image; ~439 MB total.
- **Layout:** content-addressed and sharded — `<tid[:2]>/<tid>.webp`, where `tid` is the first 12 hex characters of `sha1(canvas_fragment)`. 256 shard folders (`00/` … `ff/`), ~440 files each. There is no per-file metadata table in this repo — the filename *is* the key back to the tabular dataset.
- **Crop geometry:** a left-anchored window around the listing's `#xywh=x,y,w,h` region (padded vertically, and widened to give the entry room), cropped from the source page master and scaled to 400 px wide. The crop is deterministic — the same math the live viewer would use for an on-the-fly IIIF crop, pre-computed once.

## Coverage

| | Count |
|---|---:|
| Listings in the companion dataset | 113,827 |
| **Thumbnails here** | **113,053** (99.3%) |
| Volumes | 50 |

The ~774 listings without a thumbnail are ones whose page region couldn't be resolved to a croppable IIIF canvas (missing/degenerate `#xywh=`). In the web explorer those rows fall back to a live IIIF crop, so nothing is lost at view time — this repo simply doesn't pre-host them.

All 24 Green Book editions and all seven companion publications are represented, including the **1946 Green Book digitized by the Library of Congress** (item [2016298176](https://www.loc.gov/item/2016298176/)); every other volume is from **NYPL**.

## Finding a listing's thumbnail

The filename is `sha1(canvas_fragment)[:12]`, sharded by its first two characters. Given any row from the [companion dataset](https://huggingface.co/datasets/hadro/green-books-travel-guides), compute its thumbnail path:

```python
import hashlib

def thumb_path(canvas_fragment: str) -> str:
    tid = hashlib.sha1(canvas_fragment.encode()).hexdigest()[:12]
    return f"{tid[:2]}/{tid}.webp"

BASE = "https://huggingface.co/datasets/hadro/green-books-thumbnails/resolve/main"

# join the text dataset to its images:
from datasets import load_dataset
rows = load_dataset("hadro/green-books-travel-guides", split="train")
row = rows[0]
url = f"{BASE}/{thumb_path(row['canvas_fragment'])}"   # -> the snippet image for this listing
```

Because the key is a hash of the full `canvas_fragment` (URL + `#xywh=` region), identical regions collapse to one file automatically.

## Rights & licensing

**License: CC0 1.0 (public domain dedication) for this thumbnail compilation.**

Unlike the *facts* in the companion dataset (which are uncopyrightable directory data under *Feist v. Rural Telephone*, 499 U.S. 340), these files are **image crops of the source scans**, so the scans' own status matters directly. Verified against the NYPL API (49 NYPL volumes) and the LOC item record (1 LOC volume):

- **49 of 50 volumes** are **Public Domain in the United States** — 48 NYPL volumes (`NoC-US`, NYPL status `PDREN`) plus the **1946 Green Book** from the Library of Congress (no known publication restrictions, `NoC-US`). Crops of these pages are in the public domain.
- **1 of 50 — *Travelguide 1957*** — is an **in-copyright orphan work** (`InC-RUU`, NYPL status `ICORPHAN`): NYPL found a copyright notice, could not locate a rights-holder, and released the scan as an orphan work. Its listings' *facts* are free to reuse, but its page *scans* are not public domain, so the ~2,483 thumbnails cropped from it are **derivatives of an orphan-work scan**. They are included and flagged here for parity with the text dataset; downstream users who need a strictly-public-domain image set should exclude that volume. Per-volume rights are in [`volume_rights.csv`](https://huggingface.co/datasets/hadro/green-books-travel-guides/blob/main/volume_rights.csv) in the companion dataset.

Attribution is not legally required for the public-domain volumes but is requested as a courtesy: *"From The New York Public Library"* (NYPL volumes) / *"From the Library of Congress"* (1946 edition).

## Historical sensitivity

These snippets show real businesses and, for tourist/guest homes, **the printed addresses of private residences** — published because segregation made ordinary travel dangerous for Black Americans during the Jim Crow era. Please use them for historical, educational, and research purposes, with respect for that context and awareness that some images show private homes.

## How they were made

Cropped from the digitized page images with an open-source pipeline — the crop script is [`scripts/build_all_thumbs.py`](https://github.com/hadro/green-books) in the explorer repo, which reads each listing's `canvas_fragment` region and cuts it from the local source-page master (no calls to NYPL/LOC at build time). The upstream page transcription + region extraction comes from the vision-language-model pipeline [**hadro/directory-pipeline**](https://github.com/hadro/directory-pipeline/); see the companion dataset's card for extraction method and quality caveats. Because the *regions* come from that automated pipeline, an occasional crop may be mis-aligned or capture the wrong listing — verify against the full page via `canvas_fragment` when precision matters.

## Companion resources

- **Structured listings (text):** <https://huggingface.co/datasets/hadro/green-books-travel-guides>
- **Live explorer + IIIF viewer:** <https://hadro.github.io/green-books/all-volumes>
- **Pipeline source:** <https://github.com/hadro/directory-pipeline/>

## Citation

```bibtex
@dataset{green_book_thumbnails,
  title  = {African American Travel Guides: Listing Thumbnails (Green Book and Companion Directories, 1930--1966)},
  author = {Hadro, Josh},
  year   = {2026},
  note   = {113,053 per-listing snippet images cropped from 50 digitized volumes, New York Public Library and Library of Congress Digital Collections},
  url    = {https://huggingface.co/datasets/hadro/green-books-thumbnails}
}
```
