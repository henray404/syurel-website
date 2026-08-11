"""Single training entry point.

    python -m train.train --config configs/train/baseline.yaml
    python -m train.train --config configs/train/baseline.yaml --resume
    python -m train.train --config configs/train/baseline.yaml --smoke

Everything that defines a run lives in the YAML, and a copy of the resolved
config is written into the run directory -- a run you cannot reproduce from its
own output directory is not a result.

Outputs, all local, no account required anywhere:

    runs/<name>/config.yaml     exact config used
    runs/<name>/metrics.csv     one row per epoch
    runs/<name>/tb/             tensorboard --logdir runs
    runs/<name>/last.pt         resume point (model+optim+scaler+epoch)
    runs/<name>/best.pt         best `select_metric` so far
    runs/<name>/summary.json    final numbers
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import torch
import yaml

from data.schema import REPO_ROOT, load_schema
from models import build_model

from .dataset import build_dataloaders
from .losses import build_loss
from .metrics import HEADLINE, ConfusionMatrix, format_headline

RUNS_ROOT = REPO_ROOT / "runs"


def set_seed(seed: int, deterministic: bool = False) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    if deterministic:
        # Slower, and some conv kernels have no deterministic implementation.
        # Off by default; turn it on when a result must be exactly repeatable.
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
    else:
        torch.backends.cudnn.benchmark = True


def build_optimizer(model: torch.nn.Module, cfg: dict[str, Any]):
    name = str(cfg.get("name", "adamw")).lower()
    lr = float(cfg.get("lr", 3e-4))
    wd = float(cfg.get("weight_decay", 1e-4))
    if name == "adamw":
        return torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=wd)
    if name == "sgd":
        return torch.optim.SGD(
            model.parameters(), lr=lr, momentum=float(cfg.get("momentum", 0.9)), weight_decay=wd
        )
    raise ValueError(f"unknown optimizer {name!r}; known: adamw, sgd")


def build_scheduler(opt, cfg: dict[str, Any], epochs: int):
    name = str(cfg.get("name", "cosine")).lower()
    if name == "none":
        return None
    if name == "cosine":
        return torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=max(1, epochs))
    if name == "poly":
        return torch.optim.lr_scheduler.PolynomialLR(
            opt, total_iters=max(1, epochs), power=float(cfg.get("power", 0.9))
        )
    raise ValueError(f"unknown scheduler {name!r}; known: cosine, poly, none")


class CsvLogger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.fields: list[str] | None = None
        if path.exists():  # resuming: keep the existing header and append
            with path.open(encoding="utf-8", newline="") as fh:
                header = next(csv.reader(fh), None)
            self.fields = header or None

    def log(self, row: dict[str, Any]) -> None:
        if self.fields is None:
            self.fields = list(row)
            with self.path.open("w", encoding="utf-8", newline="") as fh:
                csv.DictWriter(fh, fieldnames=self.fields).writeheader()
        with self.path.open("a", encoding="utf-8", newline="") as fh:
            csv.DictWriter(fh, fieldnames=self.fields, extrasaction="ignore").writerow(row)


@torch.no_grad()
def evaluate(model, loader, loss_fn, device, schema, n_classes: int) -> dict[str, Any]:
    model.eval()
    overall = ConfusionMatrix(n_classes, schema.ignore_index, device=device)
    per_ds: dict[str, ConfusionMatrix] = defaultdict(
        lambda: ConfusionMatrix(n_classes, schema.ignore_index, device=device)
    )
    total_loss, n_batches = 0.0, 0

    for batch in loader:
        images = batch["image"].to(device, non_blocking=True)
        masks = batch["mask"].to(device, non_blocking=True)
        logits = model(images)
        total_loss += float(loss_fn(logits, masks))
        n_batches += 1

        pred = logits.argmax(1)
        overall.update(pred, masks)
        for i, ds in enumerate(batch["dataset"]):
            per_ds[ds].update(pred[i : i + 1], masks[i : i + 1])

    metrics = overall.compute(schema.names)
    metrics["loss"] = total_loss / max(1, n_batches)
    # Per-dataset IoU is how a dataset that fights the others gets identified
    # (docs/datasets.md s6). Cheap here, impossible to reconstruct later.
    metrics["_per_dataset"] = {
        ds: {k: v for k, v in cm.compute(schema.names).items() if k in HEADLINE}
        for ds, cm in sorted(per_ds.items())
    }
    return metrics


def train(config_path: Path, resume: bool = False, smoke: bool = False) -> dict[str, Any]:
    cfg = yaml.safe_load(Path(config_path).read_text(encoding="utf-8"))
    schema = load_schema()
    n_classes = len(schema.names)

    seed = int(cfg.get("seed", 0))
    set_seed(seed, bool(cfg.get("deterministic", False)))

    run_dir = RUNS_ROOT / str(cfg.get("name", Path(config_path).stem))
    (run_dir / "tb").mkdir(parents=True, exist_ok=True)
    (run_dir / "config.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")

    device = str(cfg.get("device") or ("cuda" if torch.cuda.is_available() else "cpu"))
    epochs = 1 if smoke else int(cfg["train"].get("epochs", 60))

    train_dl, val_dl, sampler = build_dataloaders(cfg, schema)
    model = build_model(
        str(cfg["model"]["name"]), n_classes=n_classes, **(cfg["model"].get("args") or {})
    )
    model.to(device)

    loss_fn = build_loss(cfg.get("loss") or {}, n_classes, schema.ignore_index).to(device)
    opt = build_optimizer(model, cfg.get("optimizer") or {})
    sched = build_scheduler(opt, cfg.get("scheduler") or {}, epochs)

    # AMP only helps on CUDA; on CPU it is a slowdown and a source of NaNs.
    amp = bool(cfg["train"].get("amp", True)) and device.startswith("cuda")
    scaler = torch.amp.GradScaler("cuda", enabled=amp)
    clip = float(cfg["train"].get("grad_clip", 0.0))

    select = str(cfg["train"].get("select_metric", "iou_debris"))
    if select not in HEADLINE:
        raise ValueError(
            f"select_metric={select!r} is not in HEADLINE {HEADLINE}. "
            f"Selecting on pixel accuracy in particular is how you ship an all-water model."
        )
    patience = int(cfg["train"].get("early_stopping_patience", 12))

    start_epoch, best_score, bad_epochs = 0, -float("inf"), 0
    ckpt_path, best_path = run_dir / "last.pt", run_dir / "best.pt"
    if resume and ckpt_path.exists():
        state = torch.load(ckpt_path, map_location=device, weights_only=False)
        model.load_state_dict(state["model"])
        opt.load_state_dict(state["optimizer"])
        if sched is not None and state.get("scheduler"):
            sched.load_state_dict(state["scheduler"])
        scaler.load_state_dict(state["scaler"])
        start_epoch = int(state["epoch"]) + 1
        best_score = float(state.get("best_score", -float("inf")))
        bad_epochs = int(state.get("bad_epochs", 0))
        print(f"resumed from {ckpt_path} at epoch {start_epoch} (best {select}={best_score:.4f})")

    from torch.utils.tensorboard import SummaryWriter

    tb = SummaryWriter(str(run_dir / "tb"))
    csv_log = CsvLogger(run_dir / "metrics.csv")

    print(
        f"run={run_dir.name} device={device} amp={amp} epochs={epochs} "
        f"train={len(train_dl.dataset)} val={len(val_dl.dataset)} "
        f"steps/epoch={len(train_dl)} select={select}"
    )

    stopped_early = False
    epoch = start_epoch - 1
    for epoch in range(start_epoch, epochs):
        if sampler is not None:
            sampler.set_epoch(epoch)

        model.train()
        t0 = time.time()
        running, n_steps = 0.0, 0
        for step, batch in enumerate(train_dl):
            images = batch["image"].to(device, non_blocking=True)
            masks = batch["mask"].to(device, non_blocking=True)

            opt.zero_grad(set_to_none=True)
            with torch.amp.autocast("cuda", enabled=amp):
                loss = loss_fn(model(images), masks)
            scaler.scale(loss).backward()
            if clip > 0:
                scaler.unscale_(opt)
                torch.nn.utils.clip_grad_norm_(model.parameters(), clip)
            scaler.step(opt)
            scaler.update()

            running += float(loss.detach())
            n_steps += 1
            if smoke and step >= 1:
                break

        if sched is not None:
            sched.step()

        train_loss = running / max(1, n_steps)
        val = evaluate(model, val_dl, loss_fn, device, schema, n_classes)
        secs = time.time() - t0
        lr_now = opt.param_groups[0]["lr"]

        print(
            f"[{epoch:03d}] train_loss={train_loss:.4f} val_loss={val['loss']:.4f}  "
            f"{format_headline(val)}  ({secs:.0f}s)"
        )

        row = {"epoch": epoch, "train_loss": train_loss, "lr": lr_now, "seconds": round(secs, 1)}
        row.update({f"val_{k}": v for k, v in val.items() if not k.startswith("_")})
        for ds, m in val["_per_dataset"].items():
            row.update({f"val_{ds}_{k}": v for k, v in m.items()})
        csv_log.log(row)

        tb.add_scalar("loss/train", train_loss, epoch)
        tb.add_scalar("loss/val", val["loss"], epoch)
        tb.add_scalar("lr", lr_now, epoch)
        for k, v in val.items():
            if not k.startswith("_") and k != "loss" and v == v:  # skip NaN
                tb.add_scalar(f"val/{k}", v, epoch)
        for ds, m in val["_per_dataset"].items():
            for k, v in m.items():
                if v == v:
                    tb.add_scalar(f"val_{ds}/{k}", v, epoch)

        score = val.get(select, float("nan"))
        improved = score == score and score > best_score
        if improved:
            best_score, bad_epochs = score, 0
            torch.save(
                {"model": model.state_dict(), "epoch": epoch, "score": score, "config": cfg},
                best_path,
            )
        else:
            bad_epochs += 1

        torch.save(
            {
                "model": model.state_dict(),
                "optimizer": opt.state_dict(),
                "scheduler": sched.state_dict() if sched is not None else None,
                "scaler": scaler.state_dict(),
                "epoch": epoch,
                "best_score": best_score,
                "bad_epochs": bad_epochs,
                "config": cfg,
            },
            ckpt_path,
        )

        if patience > 0 and bad_epochs >= patience:
            print(f"early stop: no {select} improvement for {patience} epochs")
            stopped_early = True
            break

    tb.close()
    summary = {
        "run": run_dir.name,
        "model": cfg["model"]["name"],
        "select_metric": select,
        "best_score": best_score,
        "epochs_run": epoch + 1,
        "stopped_early": stopped_early,
        "device": device,
        "finished_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--config", required=True, type=Path)
    ap.add_argument("--resume", action="store_true", help="continue from runs/<name>/last.pt")
    ap.add_argument("--smoke", action="store_true", help="1 epoch, 2 steps -- wiring check only")
    args = ap.parse_args(argv)
    train(args.config, resume=args.resume, smoke=args.smoke)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
