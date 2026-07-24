#!/usr/bin/env python3
"""Publish the pre-cropped thumbnail set to a Hugging Face dataset repo, which
serves them as a CDN for the explorers (zero NYPL/LOC traffic at view time).

The thumbs/ tree (~420 MB, ~108k WebP files, sharded <tid[:2]>/<tid>.webp) is
deliberately NOT committed to this Git repo / GitHub Pages — HF is the sole host.
Uploads mirror the folder's CONTENTS to the repo root, so the shard dirs (00/,
01/, ...) sit at the repo root and files resolve at:
  https://huggingface.co/datasets/<repo-id>/resolve/main/<tid[:2]>/<tid>.webp
(the explorers' HF_THUMB_BASE therefore ends at .../resolve/main).

Uploads in BATCHED commits (one per 2-hex shard), NOT via upload_large_folder:
its Xet backend reliably hangs on 100k-file folders (workers stall at ~7 MB with
0% CPU).

Critically, the committed .gitattributes keeps *.webp OUT of Git-LFS, so HF
inlines each 4 KB file into the commit payload — one commit costs ~2 API calls
regardless of file count. Per-file LFS uploads (the default) cost ~1.5 calls each
and blow HF's 3000-request / 5-minute quota within a single 6.7k-file batch.
Xet is disabled by default (it hangs); pass --xet to re-enable.

Auth: uses cached `huggingface-cli login` credentials, or the HF_TOKEN env var.

Usage (from the green-books repo root, after build_all_thumbs.py):

  scripts/publish_thumbs.py                 # all 256 shards, resumable
  scripts/publish_thumbs.py --only 00       # one shard (smoke test / resume)
"""

import argparse
import os
import sys

DEFAULT_REPO = "hadro/green-books-thumbnails"
HEXD = "0123456789abcdef"


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--repo-id", default=DEFAULT_REPO)
    ap.add_argument("--folder", default="thumbs",
                    help="local thumbnail tree to upload (its shard dirs go to the repo root)")
    ap.add_argument("--private", action="store_true")
    ap.add_argument("--token", default=os.environ.get("HF_TOKEN"))
    _repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ap.add_argument("--readme", default=os.path.join(_repo_root, "hf-dataset-thumbs", "README.md"),
                    help="dataset card to upload as the repo README.md (pass '' to skip)")
    ap.add_argument("--only", metavar="GROUP",
                    help="upload only this group — a 1-hex nibble (e.g. 0 = shards 00..0f) "
                         "or a full 2-hex shard (e.g. 00). Smoke test / targeted resume.")
    ap.add_argument("--by-nibble", action="store_true",
                    help="commit per 1-hex nibble (16 big commits) instead of per shard (256). "
                         "Bigger inline payloads (~36 MB) — may exceed HF's commit size limit.")
    ap.add_argument("--reset", action="store_true",
                    help="delete + recreate the repo first for a clean slate (drops any "
                         "partial/LFS-committed state from a failed run)")
    ap.add_argument("--resume", action="store_true",
                    help="skip groups whose files are already fully present on the repo")
    ap.add_argument("--sleep", type=float, default=0.3,
                    help="seconds to pause between commits (rate-limit headroom)")
    ap.add_argument("--xet", action="store_true",
                    help="allow the Xet backend (default OFF — it hangs on large folders)")
    args = ap.parse_args()

    if not args.xet:
        os.environ["HF_HUB_DISABLE_XET"] = "1"  # must precede the import below

    import time
    try:
        from huggingface_hub import HfApi
    except ImportError:
        sys.exit("huggingface_hub not installed: pip install huggingface_hub")

    folder = os.path.abspath(args.folder)
    if not os.path.isdir(folder):
        sys.exit(f"no such folder: {folder}")

    # A "group" is either one nibble (matches shards 0x..) or one full shard.
    if args.only:
        groups = [args.only]
    elif args.by_nibble:
        groups = list(HEXD)
    else:
        groups = [a + b for a in HEXD for b in HEXD]

    def shards_of(g):
        return [g + b for b in HEXD] if len(g) == 1 else [g]

    def pattern_of(g):
        return f"{g}*/*.webp" if len(g) == 1 else f"{g}/*.webp"

    # local file counts per group, so --resume knows what "fully present" means
    local_counts = {}
    for g in groups:
        local_counts[g] = sum(
            len(os.listdir(os.path.join(folder, s)))
            for s in shards_of(g) if os.path.isdir(os.path.join(folder, s)))

    api = HfApi(token=args.token)
    if args.reset:
        try:
            api.delete_repo(args.repo_id, repo_type="dataset", missing_ok=True)
            print(f"deleted {args.repo_id} for clean slate", flush=True)
        except Exception as e:  # noqa: BLE001
            print(f"delete skipped: {e}", flush=True)
    api.create_repo(args.repo_id, repo_type="dataset", private=args.private, exist_ok=True)

    # Commit .gitattributes FIRST so HF's per-commit upload-mode check sees that
    # *.webp is not LFS-tracked and inlines the blobs (cheap, quota-friendly).
    ga = os.path.join(folder, ".gitattributes")
    if os.path.exists(ga) and not args.only:
        api.upload_file(path_or_fileobj=ga, path_in_repo=".gitattributes",
                        repo_id=args.repo_id, repo_type="dataset",
                        commit_message="Keep *.webp out of LFS (inline small thumbs)")
        print("committed .gitattributes (webp = regular blobs, not LFS)", flush=True)

    if args.readme and os.path.exists(args.readme) and not args.only:
        api.upload_file(path_or_fileobj=args.readme, path_in_repo="README.md",
                        repo_id=args.repo_id, repo_type="dataset",
                        commit_message="Add dataset card")
        print(f"committed README.md from {args.readme}", flush=True)

    have_shard = {}
    if args.resume:
        for f in api.list_repo_files(args.repo_id, repo_type="dataset"):
            if f.endswith(".webp"):
                have_shard[f[:2]] = have_shard.get(f[:2], 0) + 1

    done = skipped = 0
    for i, g in enumerate(groups, 1):
        if local_counts.get(g, 0) == 0:
            continue
        have = sum(have_shard.get(s, 0) for s in shards_of(g))
        if args.resume and have >= local_counts[g]:
            skipped += 1
            continue
        print(f"[{i}/{len(groups)}] group {g}: uploading {local_counts[g]} files "
              f"(already on repo: {have})", flush=True)
        api.upload_folder(
            repo_id=args.repo_id,
            repo_type="dataset",
            folder_path=folder,
            allow_patterns=[pattern_of(g)],
            commit_message=f"Add thumbnail group {g}",
        )
        done += 1
        if args.sleep:
            time.sleep(args.sleep)

    # tiny build-stats file at the repo root
    stats = os.path.join(folder, "_build_stats.json")
    if os.path.exists(stats) and not args.only:
        api.upload_file(path_or_fileobj=stats, path_in_repo="_build_stats.json",
                        repo_id=args.repo_id, repo_type="dataset",
                        commit_message="Add build stats")

    print(f"\ndone: {done} groups uploaded, {skipped} skipped. base URL: "
          f"https://huggingface.co/datasets/{args.repo_id}/resolve/main/")


if __name__ == "__main__":
    main()
