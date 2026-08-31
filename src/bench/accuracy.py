"""Accuracy side of the comparison, swept across input resolution.

    python -m bench.accuracy                 # every model with a checkpoint
    python -m bench.accuracy --split val

Needs a trained checkpoint per model at runs/<model>/best.pt. Models without one
are reported as PENDING rather than skipped silently, so the gap is visible in
docs/model_comparison.md instead of looking like the model was never a candidate.

THE POINT OF THE RESOLUTION SWEEP: floating debris is a small-object problem.
Sachets and bottle caps are a handful of pixels at 640 and sub-pixel at 416.
Downscaling is the cheapest way to hit a latency target and the easiest way to
quietly destroy the only class that matters -- and it will barely move mIoU,
because background and water are large and easy. So this reports debris IoU per
resolution and the percentage drop from the largest, which is the number that
should actually drive the resolution choice.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch
import yaml
from torch.utils.data import DataLoader

from data.schema import REPO_ROOT, load_schema
from models import build_model
from train.dataset import SegDataset
from train.metrics import ConfusionMatrix
from train.train import RUNS_ROOT

from .cost import BENCH_DIR, DEFAULT_CONFIG


@torch.no_grad()
def eval_at(
    model: torch.nn.Module,
    split: str,
    size: int,
    schema,
    device: str,
    batch_size: int,
    workers: int,
) -> dict[str, float]:
    ds = SegDataset(split, size=size, aug_cfg=None, schema=schema, train=False)
    dl = DataLoader(ds, batch_size=batch_size, shuffle=False, num_workers=workers)

    cm = ConfusionMatrix(len(schema.names), schema.ignore_index, device=device)
    model.eval()
    for batch in dl:
        images = batch["image"].to(device, non_blocking=True)
        masks = batch["mask"].to(device, non_blocking=True)
        cm.update(model(images).argmax(1), masks)
    return cm.compute(schema.names)


def _degradation(by_res: dict[str, dict[str, float]], resolutions: list[int]) -> dict[str, Any]:
    """How much debris IoU is lost by downscaling, relative to the largest input.

    Reported next to the mIoU drop on purpose: if debris falls 40% while mIoU
    falls 5%, the aggregate metric is hiding the failure, and that contrast is
    the argument against choosing a resolution on mIoU.
    """
    hi = str(max(resolutions))
    if hi not in by_res:
        return {}

    def drop(key: str, res: str) -> float | None:
        base, cur = by_res[hi].get(key), by_res[res].get(key)
        if base is None or cur is None or base != base or cur != cur or base <= 0:
            return None
        return round(100.0 * (base - cur) / base, 1)

    return {
        "debris_iou_drop_pct": {str(r): drop("iou_debris", str(r)) for r in sorted(resolutions)},
        "miou_drop_pct": {str(r): drop("miou", str(r)) for r in sorted(resolutions)},
    }


def run(
    config: Path = DEFAULT_CONFIG,
    split: str = "test",
    device: str | None = None,
    batch_size: int = 8,
    workers: int = 0,
) -> dict[str, Any]:
    cfg = yaml.safe_load(Path(config).read_text(encoding="utf-8"))
    # Match the schema the checkpoint was TRAINED with. Evaluating a collapsed
    # (clump->debris) model against the 4-class schema would score every clump
    # pixel as a debris error and report nonsense.
    schema = load_schema(REPO_ROOT / cfg["classes"]) if cfg.get("classes") else load_schema()
    resolutions = [int(r) for r in cfg.get("resolutions", [640, 512, 416])]
    device = device or ("cuda" if torch.cuda.is_available() else "cpu")

    entries: list[dict[str, Any]] = []
    for name, spec in cfg["models"].items():
        if spec.get("kind") == "yolo":
            entries.append(
                {
                    "name": name,
                    "status": "NOT_EVALUATED",
                    "reason": (
                        "Instance segmentation with no water class -- cannot produce the "
                        "coverage metric alone. Reference baseline only; see "
                        "src/models/yolo_seg.py."
                    ),
                    "by_resolution": {},
                }
            )
            continue

        # A run directory is named by the training config, which is usually not the
        # model name (runs/riptseg_lraspp holds an lraspp_mnv3). `run:` maps them.
        run_dir = str(spec.get("run", name))
        ckpt = RUNS_ROOT / run_dir / "best.pt"
        if not ckpt.exists():
            entries.append(
                {
                    "name": name,
                    "status": "PENDING",
                    "reason": f"no checkpoint at runs/{run_dir}/best.pt -- train it first",
                    "by_resolution": {},
                }
            )
            print(f"  {name:22s} PENDING (no checkpoint)")
            continue

        state = torch.load(ckpt, map_location=device, weights_only=False)
        args = dict(spec.get("args") or {})
        # Weights come from the checkpoint; downloading pretrained ones here would
        # be wasted work and would mask a state_dict mismatch.
        args["pretrained"] = False
        model = build_model(name, n_classes=len(schema.names), **args).to(device)
        model.load_state_dict(state["model"])

        by_res: dict[str, dict[str, float]] = {}
        for size in resolutions:
            m = eval_at(model, split, size, schema, device, batch_size, workers)
            by_res[str(size)] = {k: v for k, v in m.items() if not k.startswith("_")}
            print(
                f"  {name:22s} {size:>4d}  miou={m['miou']:.4f}  "
                f"iou_debris={m['iou_debris']:.4f}  recall_debris={m['recall_debris']:.4f}"
            )

        entries.append(
            {
                "name": name,
                "status": "OK",
                "checkpoint_epoch": int(state.get("epoch", -1)),
                "by_resolution": by_res,
                **_degradation(by_res, resolutions),
            }
        )

    report = {
        "measured_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "split": split,
        "device": device,
        "resolutions": resolutions,
        "models": entries,
    }

    BENCH_DIR.mkdir(parents=True, exist_ok=True)
    out = BENCH_DIR / "accuracy.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nWrote {out}")
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    # Any split file under data/splits/, not just the three the splitter writes.
    # Held-out sets arrive later than the splitter does -- opsi_test.txt is the
    # 29 usable in-domain frames from the target floodgate -- and a hardcoded
    # choices= turned "evaluate on the real site" into an argparse error.
    ap.add_argument("--split", default="test")
    ap.add_argument("--device", default=None)
    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--workers", type=int, default=0)
    args = ap.parse_args(argv)

    run(
        config=args.config,
        split=args.split,
        device=args.device,
        batch_size=args.batch_size,
        workers=args.workers,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
