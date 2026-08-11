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
import sys
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
            ("images.zip", "https://zenodo.org/records/16927238/files/images.zip?download=1"),
            (
                "annotations_2cat.json",
                "https://zenodo.org/records/16927238/files/annotations_2cat.json?download=1",
            ),
        ],
        "5.6 GB for images.zip. CC BY 4.0. The 7cat/5cat annotation files are not "
        "needed for training but are worth keeping for composition analysis.",
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


def fetch(name: str) -> int:
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
            print(f"  {filename} already present ({out.stat().st_size / 1e6:.0f} MB), skipping")
            continue
        print(f"  fetching {filename}")
        try:
            urllib.request.urlretrieve(url, out, reporthook=_progress)
            print()
        except Exception as exc:
            print(f"\n  FAILED: {exc}", file=sys.stderr)
            if out.exists():
                out.unlink()  # never leave a truncated archive behind
            return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--dataset", help="one of --list")
    ap.add_argument("--list", action="store_true")
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

    return fetch(args.dataset)


if __name__ == "__main__":
    raise SystemExit(main())
