"""In-domain evaluation on the target floodgate, and the coverage numbers behind it.

    python scripts/eval_opsi.py --ckpt runs/combined_v3_segformer_b0_640/best.pt
    python scripts/eval_opsi.py --all-runs            # rank every checkpoint

Two things bench.accuracy does not do, both needed here.

FIRST, it sweeps the models named in configs/bench.yaml and looks for
runs/<model>/best.pt. Our checkpoints are keyed by RUN name, not model name
(runs/combined_v3_segformer_b0_640/), so a checkpoint comparison has to address
files directly.

SECOND, IoU is not the number the website shows. The operator sees a coverage
percentage -- (debris+clump)/(debris+clump+water) -- and a verdict derived from
it. A model can hold a respectable debris IoU and still misreport coverage,
because IoU is symmetric in the two error directions and coverage is not: pixels
the model calls water instead of debris shrink the numerator AND grow the
denominator. So this reports per-image predicted coverage against the coverage
computed from the human labels, which is the quantity the dashboard claims.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
import yaml
from torch.utils.data import DataLoader

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from data.schema import CLUMP, DEBRIS, WATER, load_schema  # noqa: E402
from models import build_model  # noqa: E402
from train.dataset import SegDataset  # noqa: E402
from train.metrics import ConfusionMatrix  # noqa: E402

SCHEMA_COLLAPSED = REPO / "configs" / "classes_collapsed.yaml"


def coverage(mask: np.ndarray) -> float | None:
    """Fraction of the visible water surface taken up by debris.

    None, never 0.0, when nothing water-like is visible: 0.0 reads as "clean
    river", which is the one thing this must never invent. Same rule as
    src/inference/metrics.py.
    """
    debris = int(((mask == DEBRIS) | (mask == CLUMP)).sum())
    water = int((mask == WATER).sum())
    denom = debris + water
    return None if denom == 0 else debris / denom


@torch.no_grad()
def evaluate(ckpt_path: Path, split: str, size: int, device: str) -> dict:
    ckpt = torch.load(ckpt_path, map_location="cpu", weights_only=False)
    schema = load_schema(SCHEMA_COLLAPSED)

    state = ckpt.get("model", ckpt.get("state_dict", ckpt))
    # train.py writes the effective config next to the checkpoint, so the run
    # states its own architecture. Prefer that over guessing from key prefixes --
    # the guess cannot separate the torchvision and smp families, which share the
    # `net.backbone.` stem across lraspp/deeplabv3/unet.
    cfg_path = ckpt_path.parent / "config.yaml"
    arch = None
    if cfg_path.exists():
        cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
        arch = (cfg.get("model") or {}).get("name")
    if arch is None:
        # Fold checkpoints from the cloud runs arrive without their config. Both
        # SegFormer sizes are told apart by the width the decoder projects from
        # (B0 160, B2 320 at stage 1).
        w = state.get("decoder.mlp_stage.1.linear.weight")
        arch = "segformer_b2" if w is not None and w.shape[1] == 320 else "segformer_b0"
    model = build_model(arch, n_classes=len(schema.names), pretrained=False)
    model.load_state_dict(state)
    model.to(device).eval()

    ds = SegDataset(split, size=size, aug_cfg=None, schema=schema, train=False)
    dl = DataLoader(ds, batch_size=4, shuffle=False, num_workers=0)

    cm = ConfusionMatrix(len(schema.names), schema.ignore_index, device=device)
    per_image: list[dict] = []
    i = 0
    for batch in dl:
        images = batch["image"].to(device)
        masks = batch["mask"].to(device)
        pred = model(images).argmax(1)
        cm.update(pred, masks)

        p = pred.cpu().numpy()
        t = masks.cpu().numpy()
        for b in range(p.shape[0]):
            item = ds.items[i]
            i += 1
            # Score the prediction ONLY where the label has an opinion.
            #
            # RIPTSeg sets `unlabelled: ignore`, so roughly 80% of each frame --
            # everything away from the barrier -- carries no ground truth. The
            # model still predicts there, and most of it is water, which lands in
            # the denominator of the prediction's coverage but not the label's.
            # Comparing the two then measures the size of the unannotated region,
            # not the model: it reported MAE 10.79 pp and a fitted slope of 0.200,
            # against 2.47 pp and 0.933 once the ignore region is excluded.
            pm = p[b].copy()
            pm[t[b] == schema.ignore_index] = schema.ignore_index
            cov_t, cov_p = coverage(t[b]), coverage(pm)
            per_image.append(
                {
                    "sample_id": item.sample_id,
                    "coverage_label": cov_t,
                    "coverage_pred": cov_p,
                    "abs_error": None if (cov_t is None or cov_p is None) else abs(cov_p - cov_t),
                }
            )

    metrics = cm.compute(schema.names)
    errs = [r["abs_error"] for r in per_image if r["abs_error"] is not None]
    metrics["coverage_mae"] = float(np.mean(errs)) if errs else float("nan")
    metrics["coverage_max_abs_error"] = float(np.max(errs)) if errs else float("nan")
    return {
        "checkpoint": str(ckpt_path.relative_to(REPO)),
        "arch": arch,
        "split": split,
        "size": size,
        "n_images": len(per_image),
        "trained_epoch": ckpt.get("epoch"),
        "trained_score": ckpt.get("score"),
        "metrics": metrics,
        "per_image": per_image,
        "evaluated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ckpt", type=Path, help="one checkpoint to evaluate")
    ap.add_argument("--all-runs", action="store_true", help="every runs/*/best.pt, ranked")
    ap.add_argument("--split", default="opsi_test")
    ap.add_argument("--size", type=int, default=640)
    ap.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    ap.add_argument("--out", type=Path, default=None, help="write full JSON here")
    args = ap.parse_args(argv)

    if args.all_runs:
        paths = sorted(REPO.glob("runs/*/best.pt"))
    elif args.ckpt:
        paths = [args.ckpt if args.ckpt.is_absolute() else REPO / args.ckpt]
    else:
        ap.error("pass --ckpt PATH or --all-runs")

    results = []
    for p in paths:
        try:
            r = evaluate(p, args.split, args.size, args.device)
        except Exception as exc:  # a broken checkpoint must not kill the sweep
            print(f"[skip] {p.parent.name}: {type(exc).__name__}: {exc}")
            continue
        m = r["metrics"]
        print(
            f"{p.parent.name:<36} iou_debris={m['iou_debris']:.4f} "
            f"iou_water={m['iou_water']:.4f} miou={m['miou']:.4f} "
            f"P={m['precision_debris']:.3f} R={m['recall_debris']:.3f} "
            f"cov_MAE={m['coverage_mae'] * 100:.2f}pp"
        )
        results.append(r)

    results.sort(key=lambda r: r["metrics"]["iou_debris"], reverse=True)
    if results:
        best = results[0]
        print(
            f"\nterbaik di {args.split}: {best['checkpoint']} "
            f"(iou_debris {best['metrics']['iou_debris']:.4f})"
        )
    if args.out:
        args.out.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"ditulis: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
