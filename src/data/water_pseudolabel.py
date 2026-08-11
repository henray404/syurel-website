"""SAM-assisted water pseudo-labelling.

    python -m data.water_pseudolabel --dataset risid
    python -m data.review --dataset risid            # look at the overlays
    python -m data.review --dataset risid --apply    # drop the ones you rejected

Only RIPTSeg labels water; every other debris dataset leaves it unknown. This
fills it in, and DOES NOT trust the result:

  * every image gets a review overlay written to review/<dataset>/
  * obviously-broken outputs are auto-flagged (water fraction out of range, low
    SAM score) so review can start with the worst ones
  * nothing enters the training splits until review.py has run

Seeding strategy: debris floats *on* water, so pixels in a ring just outside the
debris are near-certain water. That gives free, image-specific positive prompts
without a single hand-clicked point. Images with no debris fall back to a centre
grid, which is weaker -- those are auto-flagged so they get looked at.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from PIL import Image
from tqdm import tqdm

from .convert import PROCESSED_ROOT, load_dataset_cfg
from .schema import BACKGROUND, CLUMP, DEBRIS, REPO_ROOT, WATER, read_mask, write_mask

REVIEW_ROOT = REPO_ROOT / "review"


@dataclass(frozen=True)
class PseudoParams:
    ring_dilate: int = 25
    n_seeds: int = 8
    negative_top_frac: float = 0.0  # >0 marks a top band as not-water (sky / far bank)
    min_water_frac: float = 0.15
    max_water_frac: float = 0.98
    min_sam_score: float = 0.80
    seed: int = 1337


def _seed_points(
    mask: np.ndarray, params: PseudoParams, rng: np.random.Generator
) -> tuple[np.ndarray, np.ndarray]:
    """Return (points Nx2 xy, labels N) -- 1 = water, 0 = not water."""
    h, w = mask.shape
    fg = ((mask == DEBRIS) | (mask == CLUMP)).astype(np.uint8)

    pts: list[tuple[int, int]] = []
    labels: list[int] = []

    if fg.any() and params.ring_dilate > 0:
        k = np.ones((params.ring_dilate, params.ring_dilate), np.uint8)
        ring = (cv2.dilate(fg, k) - fg) > 0
        ys, xs = np.nonzero(ring)
        if len(xs) > 0:
            idx = rng.choice(len(xs), size=min(params.n_seeds, len(xs)), replace=False)
            pts += [(int(xs[i]), int(ys[i])) for i in idx]
            labels += [1] * len(idx)

    if not pts:
        # No debris to key off. Grid over the middle band, which is water in the
        # overwhelming majority of river-surface framings. Weak; flagged later.
        for fy in (0.45, 0.6, 0.75):
            for fx in (0.3, 0.5, 0.7):
                pts.append((int(fx * w), int(fy * h)))
                labels.append(1)

    if params.negative_top_frac > 0:
        y = int(params.negative_top_frac * h * 0.5)
        for fx in (0.25, 0.5, 0.75):
            pts.append((int(fx * w), y))
            labels.append(0)

    # Debris itself is an explicit negative: it is *on* the water, not water.
    ys, xs = np.nonzero(fg)
    if len(xs) > 0:
        idx = rng.choice(len(xs), size=min(3, len(xs)), replace=False)
        pts += [(int(xs[i]), int(ys[i])) for i in idx]
        labels += [0] * len(idx)

    return np.array(pts, dtype=np.float32), np.array(labels, dtype=np.int32)


def _overlay(image_path: Path, mask: np.ndarray, out_path: Path) -> None:
    """Water blue, debris red, clump yellow. For eyeballing only."""
    with Image.open(image_path) as im:
        rgb = np.array(im.convert("RGB"))
    if rgb.shape[:2] != mask.shape:
        rgb = cv2.resize(rgb, (mask.shape[1], mask.shape[0]), interpolation=cv2.INTER_AREA)

    tint = np.zeros_like(rgb)
    tint[mask == WATER] = (40, 90, 255)
    tint[mask == DEBRIS] = (255, 40, 40)
    tint[mask == CLUMP] = (255, 220, 0)
    blended = np.where(
        mask[..., None] == BACKGROUND, rgb, (0.55 * rgb + 0.45 * tint)
    ).astype(np.uint8)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(blended).save(out_path, optimize=True)


def run(dataset: str, *, limit: int | None = None, overwrite: bool = False) -> dict[str, Any]:
    from .sam import Sam  # heavy; imported only when this actually runs

    cfg = load_dataset_cfg(dataset)
    if str(cfg.get("water_source")) != "pseudo_pending":
        raise SystemExit(
            f"{dataset}: water_source is {cfg.get('water_source')!r}, not 'pseudo_pending'. "
            f"Nothing to pseudo-label."
        )

    raw = cfg.get("pseudolabel") or {}
    params = PseudoParams(
        ring_dilate=int(raw.get("ring_dilate", 25)),
        n_seeds=int(raw.get("n_seeds", 8)),
        negative_top_frac=float(raw.get("negative_top_frac", 0.0)),
        min_water_frac=float(raw.get("min_water_frac", 0.15)),
        max_water_frac=float(raw.get("max_water_frac", 0.98)),
        min_sam_score=float(raw.get("min_sam_score", 0.80)),
        seed=int(raw.get("seed", 1337)),
    )

    ds_dir = PROCESSED_ROOT / dataset
    meta_path = ds_dir / "meta.jsonl"
    if not meta_path.exists():
        raise SystemExit(
            f"{dataset}: no {meta_path}. Run `python -m data.convert --dataset {dataset}` first."
        )

    records = [
        json.loads(line)
        for line in meta_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    out_path = ds_dir / "pseudolabel.jsonl"
    done: set[str] = set()
    if out_path.exists() and overwrite:
        out_path.unlink()
    elif out_path.exists():
        done = {
            json.loads(line)["sample_id"]
            for line in out_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        }

    sam = Sam(
        ckpt=REPO_ROOT / str(cfg.get("sam_checkpoint", "data/checkpoints/mobile_sam.pt")),
        device=str(cfg.get("sam_device", "cpu")),
    )
    rng = np.random.default_rng(params.seed)
    review_dir = REVIEW_ROOT / dataset

    n_done = 0
    flags: dict[str, int] = {}
    with out_path.open("a", encoding="utf-8") as fh:
        for rec in tqdm(records, desc=f"{dataset}: water"):
            if limit is not None and n_done >= limit:
                break
            if rec["sample_id"] in done:
                continue

            mask_path = ds_dir / rec["mask"]
            image_path = ds_dir / rec["image"]
            mask = read_mask(mask_path)

            points, labels = _seed_points(mask, params, rng)
            with Image.open(image_path) as im:
                rgb = np.array(im.convert("RGB"))
            sam.set_image(rgb)
            water, score = sam.mask_from_points(points, labels)

            # Water may only claim currently-unknown pixels. Debris annotations are
            # real labels and must never be overwritten by a pseudo-label.
            new_mask = mask.copy()
            new_mask[(mask == BACKGROUND) & water] = WATER

            water_frac = float((new_mask == WATER).mean())
            flag = ""
            if water_frac < params.min_water_frac:
                flag = "water_too_small"
            elif water_frac > params.max_water_frac:
                flag = "water_too_large"
            elif score < params.min_sam_score:
                flag = "low_score"
            elif not ((mask == DEBRIS) | (mask == CLUMP)).any():
                flag = "no_debris_seed"
            flags[flag or "ok"] = flags.get(flag or "ok", 0) + 1

            write_mask(mask_path, new_mask)
            _overlay(image_path, new_mask, review_dir / f"overlay_{rec['sample_id']}.png")

            fh.write(
                json.dumps(
                    {
                        "sample_id": rec["sample_id"],
                        "water_frac": round(water_frac, 5),
                        "sam_score": round(score, 4),
                        "auto_flag": flag,
                        "n_seed_points": int(len(points)),
                        "run_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    }
                )
                + "\n"
            )
            n_done += 1

    summary = {"dataset": dataset, "pseudolabelled": n_done, "auto_flags": flags}
    print(json.dumps(summary, indent=2))
    print(
        f"\nNext: review the overlays in {review_dir}\n"
        f"  python -m data.review --dataset {dataset}          # writes the verdict CSV\n"
        f"  python -m data.review --dataset {dataset} --apply  # excludes rejects from splits\n"
        f"\nNothing is trusted until you do. Start with auto_flag != '' in {out_path.name}."
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--overwrite", action="store_true")
    args = ap.parse_args(argv)
    run(args.dataset, limit=args.limit, overwrite=args.overwrite)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
