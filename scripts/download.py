"""Download raw datasets. Nothing runs unless you name a dataset explicitly.

    python scripts/download.py --list
    python scripts/download.py --dataset riptseg
    python scripts/download.py --dataset mobile_sam

Deliberately NOT automatic and deliberately NOT bundled into convert.py: these
are multi-GB pulls, and which ones you want depends on how far the conversion
waves have got (docs/datasets.md s6).

Archives land in data/raw/<dataset>/ and are left compressed -- unpack them
yourself so you can see what the layout really is before pointing the dataset
YAML at it. Several YAMLs carry "VERIFY after download" notes for exactly this.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import time
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = REPO_ROOT / "data" / "raw"
CKPT_ROOT = REPO_ROOT / "data" / "checkpoints"

# name -> (destination dir, [(filename, url)], note)
DIRECT: dict[str, tuple[Path, list[tuple[str, str]], str]] = {
    "riptseg": (
        RAW_ROOT / "riptseg",
        [
            (
                "paper_dataset.zip",
                "https://data.4tu.nl/file/90d13261-b0fe-444a-b408-c5a63db3d887/30516cb5-e51e-4783-987d-eb59190b6c37",
            )
        ],
        "290 MB, CC BY 4.0. Unzip, then point configs/datasets/riptseg.yaml at the "
        "real image dir and instances JSON.",
    ),
    "risid": (
        RAW_ROOT / "risid",
        [
            (
                "annotations_2cat.json",
                "https://zenodo.org/records/16927238/files/annotations_2cat.json?download=1",
            ),
            (
                "annotations_7cat.json",
                "https://zenodo.org/records/16927238/files/annotations_7cat.json?download=1",
            ),
            ("images.zip", "https://zenodo.org/records/16927238/files/images.zip?download=1"),
        ],
        "5.6 GB for images.zip. CC BY 4.0. Annotations are listed first so the 8 MB "
        "files land before the multi-GB one -- EDA only needs the annotations "
        "(see docs/eda_risid.md).",
    ),
    "iwhr": (
        RAW_ROOT / "iwhr",
        [
            ("package1.zip", "https://ndownloader.figshare.com/files/50111817"),
            ("package2.zip", "https://ndownloader.figshare.com/files/50113386"),
        ],
        "1.01 GB + 1.22 GB, Apache 2.0. VOC XML annotations.",
    ),
    "mobile_sam": (
        CKPT_ROOT,
        [
            (
                "mobile_sam.pt",
                "https://raw.githubusercontent.com/ChaoningZhang/MobileSAM/master/weights/mobile_sam.pt",
            )
        ],
        "~40 MB. Needed for water pseudo-labelling and bbox->mask conversion.",
    ),
}

MANUAL: dict[str, str] = {
    "lars": (
        "https://lojzezust.github.io/lars-dataset/ -- registration/agreement form. "
        "Extract images + semantic masks into data/raw/lars/."
    ),
    "usvinland": (
        "https://github.com/ORCA-Uboat/USVInland-Dataset -- follow the repo's access "
        "instructions. Extract ONLY the water-segmentation subset into "
        "data/raw/usvinland/; skip the lidar/radar payload."
    ),
    "roboflow_river_trash": (
        "Roboflow Universe, two projects, each exported as **Pascal VOC** (not YOLO): "
        "https://universe.roboflow.com/try-uqrjj/trash-in-river and "
        "https://universe.roboflow.com/trisha-lingat-m9vjl/river-trash-final-k9997 -- "
        "merge both into data/raw/roboflow_river_trash/{images,annotations}/."
    ),
}


def _progress(done: int, block: int, total: int) -> None:
    if total <= 0:
        return
    pct = min(100.0, done * block * 100.0 / total)
    print(f"\r  {pct:5.1f}%  ({done * block / 1e6:.0f}/{total / 1e6:.0f} MB)", end="", flush=True)


def _content_length(url: str, tries: int = 5) -> int:
    """Total size via a HEAD request. 0 when the server will not say."""
    for _ in range(tries):
        try:
            req = urllib.request.Request(url, method="HEAD")
            with urllib.request.urlopen(req, timeout=60) as r:
                n = int(r.headers.get("Content-Length") or 0)
                if n > 0:
                    return n
        except Exception:
            time.sleep(3)
    return 0


def _fetch_chunked(url: str, out: Path, chunk_mb: int = 32, tries: int = 12) -> bool:
    """Download in byte ranges over short connections, then join.

    A single long transfer is not reliable on every link -- this one reproducibly
    dies around 140 MB regardless of client or host, which silently truncates
    multi-GB archives. Ranged requests keep each connection short, every chunk is
    verified against its expected byte count, and re-running resumes because
    complete chunks are skipped. Nothing lands at `out` until all chunks verify,
    so a partial download can never be mistaken for a finished one.
    """
    total = _content_length(url)
    if total <= 0:
        print("    could not determine size; falling back to a single request")
        try:
            urllib.request.urlretrieve(url, out, reporthook=_progress)
            print()
            return True
        except Exception as exc:
            print(f"\n    FAILED: {exc}", file=sys.stderr)
            out.unlink(missing_ok=True)
            return False

    part_dir = out.with_suffix(out.suffix + ".parts")
    part_dir.mkdir(parents=True, exist_ok=True)
    size = chunk_mb * 1024 * 1024
    n_chunks = -(-total // size)
    print(f"    {total / 1e6:.0f} MB in {n_chunks} chunks of {chunk_mb} MB")

    for i in range(n_chunks):
        start = i * size
        end = min(start + size - 1, total - 1)
        want = end - start + 1
        part = part_dir / f"{i:05d}.part"
        if part.exists() and part.stat().st_size == want:
            continue

        for _ in range(tries):
            try:
                req = urllib.request.Request(url, headers={"Range": f"bytes={start}-{end}"})
                with urllib.request.urlopen(req, timeout=300) as r, part.open("wb") as fh:
                    shutil.copyfileobj(r, fh)
                if part.stat().st_size == want:
                    break
            except Exception:
                pass
            time.sleep(3)
        else:
            print(
                f"\n    chunk {i} failed after {tries} tries -- re-run to resume",
                file=sys.stderr,
            )
            return False

        done = (i + 1) * 100 // n_chunks
        print(
            f"\r    {done:3d}%  ({(i + 1) * chunk_mb} / {total // 1024 // 1024} MB)",
            end="",
            flush=True,
        )

    with out.open("wb") as fh:
        for part in sorted(part_dir.glob("*.part")):
            fh.write(part.read_bytes())

    got = out.stat().st_size
    if got != total:
        print(f"\n    SIZE MISMATCH got={got} want={total}", file=sys.stderr)
        out.unlink(missing_ok=True)
        return False

    shutil.rmtree(part_dir, ignore_errors=True)
    print(f"\r    done, {got / 1e6:.0f} MB" + " " * 24)
    return True


def fetch(name: str, chunk_mb: int = 32) -> int:
    if name in MANUAL:
        print(f"{name}: manual download required.\n  {MANUAL[name]}")
        return 0
    if name not in DIRECT:
        print(f"unknown dataset {name!r}. Try --list", file=sys.stderr)
        return 1

    dest, files, note = DIRECT[name]
    dest.mkdir(parents=True, exist_ok=True)
    print(f"{name}: {note}\n  -> {dest}")

    for filename, url in files:
        out = dest / filename
        if out.exists():
            # Verify rather than trust: a truncated file from an interrupted run
            # is non-zero, and "it exists" would skip straight past it.
            expected = _content_length(url)
            actual = out.stat().st_size
            if expected == 0 or actual == expected:
                print(f"  {filename} already present ({actual / 1e6:.0f} MB), skipping")
                continue
            print(
                f"  {filename} is TRUNCATED ({actual / 1e6:.0f} of {expected / 1e6:.0f} MB), "
                f"refetching"
            )
            out.unlink()

        print(f"  fetching {filename}")
        if not _fetch_chunked(url, out, chunk_mb=chunk_mb):
            return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--dataset", help="one of --list")
    ap.add_argument("--list", action="store_true")
    ap.add_argument(
        "--chunk-mb",
        type=int,
        default=32,
        help="byte-range chunk size. Lower it if the connection drops mid-chunk.",
    )
    args = ap.parse_args(argv)

    if args.list or not args.dataset:
        print("Direct download:")
        for k, (_, files, note) in DIRECT.items():
            print(f"  {k:22s} {len(files)} file(s)  -- {note.splitlines()[0]}")
        print("\nManual (gated / requires an account or export step):")
        for k, note in MANUAL.items():
            print(f"  {k:22s} {note[:70]}...")
        print("\nRun: python scripts/download.py --dataset NAME")
        return 0

    return fetch(args.dataset, chunk_mb=args.chunk_mb)


if __name__ == "__main__":
    raise SystemExit(main())
