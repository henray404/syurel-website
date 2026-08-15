"""Convert one source dataset into the unified semantic-mask format.

    python -m data.convert --dataset riptseg
    python -m data.convert --all --overwrite

Output layout (see docs/datasets.md for why the long side is capped at 1024):

    data/processed/<dataset>/
        images/<sample_id>.jpg      long side <= max_size
        masks/<sample_id>.png       uint8, class indices 0..3
        meta.jsonl                  one JSON object per converted sample
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from PIL import Image
from tqdm import tqdm

from .base import Sample, get_adapter
from .clump import ClumpParams, derive_clump
from .schema import REPO_ROOT, Schema, class_pixel_counts, load_schema, write_mask

CONFIG_DIR = REPO_ROOT / "configs" / "datasets"
RAW_ROOT = REPO_ROOT / "data" / "raw"
PROCESSED_ROOT = REPO_ROOT / "data" / "processed"


def load_dataset_cfg(name: str) -> dict[str, Any]:
    path = CONFIG_DIR / f"{name}.yaml"
    if not path.exists():
        available = sorted(p.stem for p in CONFIG_DIR.glob("*.yaml"))
        raise FileNotFoundError(f"no config {path}. Available datasets: {available}")
    cfg = yaml.safe_load(path.read_text(encoding="utf-8"))
    cfg.setdefault("dataset", name)
    return cfg


def build_slot_lut(labels: list[str], cfg: dict[str, Any], schema: Schema) -> np.ndarray:
    """Map source label slots (1-based, 0 = unlabelled) to target class ids.

    Two independent policies:

    `unmapped`   what happens to a source label the YAML does not mention.
                 Default `error`: a dataset that silently gains a category should
                 break the build, not quietly turn into background.

    `unlabelled` what slot 0 -- pixels no annotation covers -- becomes.
                 Default `background`, correct when the source annotates the whole
                 frame. Set `ignore` when the source annotates only a region:
                 RIPTSeg labels ~20% of each frame around the barrier, so calling
                 the other 80% background would teach the model that real river
                 water is background and poison the coverage denominator.
    """
    label_map: dict[str, str] = cfg.get("label_map") or {}
    policy = str(cfg.get("unmapped", "error"))
    unlabelled = str(cfg.get("unlabelled", "background"))
    if unlabelled not in ("background", "ignore"):
        raise ValueError(f"{cfg['dataset']}: unlabelled must be background|ignore")

    missing = [name for name in labels if name not in label_map]
    if missing:
        if policy == "error":
            raise ValueError(
                f"{cfg['dataset']}: source labels not in label_map: {missing}\n"
                f"Add them to configs/datasets/{cfg['dataset']}.yaml, or set "
                f"`unmapped: background` if they really are background."
            )
        if policy not in ("background", "ignore"):
            raise ValueError(f"{cfg['dataset']}: unmapped must be error|background|ignore")

    lut = np.zeros(256, dtype=np.uint8)
    lut[0] = schema.ignore_index if unlabelled == "ignore" else 0
    for i, name in enumerate(labels):
        slot = i + 1
        if name in label_map:
            lut[slot] = schema.id_of(str(label_map[name]))
        else:
            lut[slot] = schema.ignore_index if policy == "ignore" else 0
    return lut


def resize_long_side(
    img: Image.Image, mask: np.ndarray, max_size: int
) -> tuple[Image.Image, np.ndarray]:
    """Cap the long side. Mask uses NEAREST -- any interpolation invents classes."""
    w, h = img.size
    longest = max(w, h)
    if max_size <= 0 or longest <= max_size:
        return img, mask
    scale = max_size / longest
    new_size = (max(1, round(w * scale)), max(1, round(h * scale)))
    img_r = img.resize(new_size, Image.Resampling.LANCZOS)
    mask_r = np.array(
        Image.fromarray(mask, mode="L").resize(new_size, Image.Resampling.NEAREST),
        dtype=np.uint8,
    )
    return img_r, mask_r


def _mask_from_boxes(sample: Sample, sam: Any, size: tuple[int, int], lut: np.ndarray) -> np.ndarray:
    """SAM box-prompt every box, paint into a slot mask, then remap to target ids."""
    width, height = size
    slot_mask = np.zeros((height, width), dtype=np.uint8)
    label_slot = {name: i + 1 for i, name in enumerate(sample.labels)}

    with Image.open(sample.image_path) as im:
        rgb = np.array(im.convert("RGB"))
    sam.set_image(rgb)

    # Paint in descending box area so small objects sitting on top of big ones survive.
    def area(item: tuple[str, tuple[float, float, float, float]]) -> float:
        (_, (x0, y0, x1, y1)) = item
        return -((x1 - x0) * (y1 - y0))

    for name, box in sorted(sample.boxes or [], key=area):
        binary = sam.mask_from_box(box)
        slot_mask[binary] = label_slot[name]
    return lut[slot_mask]


def convert_dataset(
    name: str,
    *,
    overwrite: bool = False,
    limit: int | None = None,
    schema: Schema | None = None,
) -> dict[str, Any]:
    schema = schema or load_schema()
    cfg = load_dataset_cfg(name)

    adapter_cls = get_adapter(str(cfg["adapter"]))
    adapter = adapter_cls(cfg, RAW_ROOT / name)

    out_dir = PROCESSED_ROOT / name
    img_dir, mask_dir = out_dir / "images", out_dir / "masks"
    img_dir.mkdir(parents=True, exist_ok=True)
    mask_dir.mkdir(parents=True, exist_ok=True)
    meta_path = out_dir / "meta.jsonl"

    max_size = int(cfg.get("max_size", 1024))
    jpeg_quality = int(cfg.get("jpeg_quality", 92))
    water_source = str(cfg.get("water_source", "none"))

    clump_cfg = cfg.get("clump") or {}
    clump_on = bool(clump_cfg.get("enabled", True))
    clump_params = ClumpParams(
        min_area_frac=float(clump_cfg.get("min_area_frac", 0.005)),
        close_kernel=int(clump_cfg.get("close_kernel", 5)),
        connectivity=int(clump_cfg.get("connectivity", 8)),
    )

    sam = None
    if adapter.kind == "bbox":
        from .sam import Sam

        sam = Sam(
            ckpt=REPO_ROOT / str(cfg.get("sam_checkpoint", "data/checkpoints/mobile_sam.pt")),
            device=str(cfg.get("sam_device", "cpu")),
        )

    lut: np.ndarray | None = None
    seen_ids: set[str] = set()
    written = 0
    skipped_existing = 0
    failures: Counter[str] = Counter()
    totals = np.zeros(256, dtype=np.int64)
    groups: Counter[str] = Counter()

    if overwrite and meta_path.exists():
        meta_path.unlink()

    total = len(adapter)
    with meta_path.open("a", encoding="utf-8") as meta_fh:
        for sample in tqdm(adapter.samples(), total=total if total > 0 else None, desc=name):
            if limit is not None and written >= limit:
                break

            # Two samples with the same id would overwrite each other, or be
            # counted as "already converted" and silently dropped. This is a hard
            # failure, not a warning: it is data loss that looks like success.
            if sample.sample_id in seen_ids:
                raise ValueError(
                    f"{name}: duplicate sample_id {sample.sample_id!r} "
                    f"(second source: {sample.image_path}). Adapter ids must be unique "
                    f"across the whole dataset -- derive them from the relative path, "
                    f"not the filename stem."
                )
            seen_ids.add(sample.sample_id)

            out_img = img_dir / f"{sample.sample_id}.jpg"
            out_mask = mask_dir / f"{sample.sample_id}.png"
            if out_mask.exists() and not overwrite:
                skipped_existing += 1
                continue

            # The LUT depends only on the label vocabulary, fixed for mask adapters.
            # voc_bbox discovers labels lazily, so it gets rebuilt each sample.
            if lut is None or adapter.kind == "bbox":
                lut = build_slot_lut(sample.labels, cfg, schema)

            try:
                with Image.open(sample.image_path) as raw_im:
                    im = raw_im.convert("RGB")
                src_w, src_h = im.size

                if sample.boxes is not None:
                    target = _mask_from_boxes(sample, sam, (src_w, src_h), lut)
                else:
                    assert sample.build_mask is not None
                    slot_mask = sample.build_mask()
                    if slot_mask.shape != (src_h, src_w):
                        failures["mask_size_mismatch"] += 1
                        continue
                    target = lut[slot_mask]

                im_r, mask_r = resize_long_side(im, target, max_size)

                n_promoted = 0
                if clump_on:
                    mask_r, n_promoted = derive_clump(mask_r, clump_params)

                im_r.save(out_img, quality=jpeg_quality, subsampling=1)
                write_mask(out_mask, mask_r)
            except Exception as exc:  # keep going; one bad file must not kill a 7k run
                failures[type(exc).__name__] += 1
                continue

            counts = class_pixel_counts(mask_r)
            totals += counts
            groups[sample.group] += 1

            meta_fh.write(
                json.dumps(
                    {
                        "sample_id": sample.sample_id,
                        "dataset": name,
                        "group": sample.group,
                        "image": out_img.relative_to(out_dir).as_posix(),
                        "mask": out_mask.relative_to(out_dir).as_posix(),
                        "width": int(mask_r.shape[1]),
                        "height": int(mask_r.shape[0]),
                        "src_width": src_w,
                        "src_height": src_h,
                        "pixel_counts": {
                            str(cid): int(counts[cid]) for cid in schema.ids if counts[cid]
                        },
                        # "labelled"       -> water came from real annotations
                        # "pseudo_pending" -> water_pseudolabel.py still has to run
                        # "none"           -> this dataset contributes no water class
                        "water_source": water_source,
                        "clump_heuristic": bool(n_promoted),
                        "n_clump_regions": n_promoted,
                        "converted_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                        **{f"src_{k}": v for k, v in sample.extra.items()},
                    }
                )
                + "\n"
            )
            written += 1

    summary = {
        "dataset": name,
        "adapter": cfg["adapter"],
        "written": written,
        "skipped_existing": skipped_existing,
        "failures": dict(failures),
        "n_groups": len(groups),
        "pixel_share": {
            schema.names[cid]: round(float(totals[cid]) / max(1, int(totals.sum())), 5)
            for cid in schema.ids
        },
        "clump_params": asdict(clump_params) if clump_on else None,
        "water_source": water_source,
    }
    (out_dir / "convert_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--dataset", help="dataset name (configs/datasets/<name>.yaml)")
    ap.add_argument("--all", action="store_true", help="convert every configured dataset")
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--limit", type=int, default=None, help="stop after N samples (smoke test)")
    args = ap.parse_args(argv)

    if not args.dataset and not args.all:
        ap.error("pass --dataset NAME or --all")

    names = sorted(p.stem for p in CONFIG_DIR.glob("*.yaml")) if args.all else [args.dataset]
    schema = load_schema()

    rc = 0
    for name in names:
        try:
            summary = convert_dataset(name, overwrite=args.overwrite, limit=args.limit, schema=schema)
        except FileNotFoundError as exc:
            print(f"[skip] {name}: {exc}", file=sys.stderr)
            rc = 1
            continue
        print(json.dumps(summary, indent=2))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
