"""Segmentation metrics built on a confusion matrix.

PIXEL ACCURACY IS NOT A HEADLINE METRIC HERE. Water is 85-95% of pixels, so a
model that predicts "all water" and detects nothing scores ~0.9 and looks great.
It is computed (it is free, and a sudden collapse is informative) but it is
deliberately excluded from HEADLINE and from early stopping. Judge runs on
per-class IoU, mean IoU, and debris precision/recall.
"""

from __future__ import annotations

import torch

#: Metrics allowed to be printed as a run's summary or used for model selection.
HEADLINE = ("miou", "iou_debris", "precision_debris", "recall_debris")


class ConfusionMatrix:
    """Accumulates an (n_classes x n_classes) matrix: rows = truth, cols = pred."""

    def __init__(self, n_classes: int, ignore_index: int = 255, device: str = "cpu") -> None:
        self.n = n_classes
        self.ignore_index = ignore_index
        self.mat = torch.zeros((n_classes, n_classes), dtype=torch.int64, device=device)

    def reset(self) -> None:
        self.mat.zero_()

    @torch.no_grad()
    def update(self, pred: torch.Tensor, target: torch.Tensor) -> None:
        """pred, target: (B, H, W) int64 class indices."""
        pred = pred.reshape(-1)
        target = target.reshape(-1)

        keep = target != self.ignore_index
        # Guard against labels outside the schema. Without this, bincount silently
        # writes into the wrong cell and every IoU is quietly wrong.
        keep &= (target >= 0) & (target < self.n)
        pred, target = pred[keep], target[keep]

        idx = target * self.n + pred
        counts = torch.bincount(idx, minlength=self.n**2).reshape(self.n, self.n)
        self.mat += counts.to(self.mat.device)

    def compute(self, class_names: dict[int, str]) -> dict[str, float]:
        mat = self.mat.double()
        tp = mat.diag()
        fp = mat.sum(0) - tp
        fn = mat.sum(1) - tp

        eps = 1e-9
        iou = tp / (tp + fp + fn + eps)
        precision = tp / (tp + fp + eps)
        recall = tp / (tp + fn + eps)

        # Classes absent from BOTH truth and prediction are undefined, not zero.
        # Averaging in a 0 for a class that never appears drags mIoU down for a
        # reason that has nothing to do with the model.
        present = (mat.sum(1) + mat.sum(0)) > 0

        out: dict[str, float] = {}
        for cid, name in class_names.items():
            if cid >= self.n:
                continue
            out[f"iou_{name}"] = float(iou[cid]) if present[cid] else float("nan")
            out[f"precision_{name}"] = float(precision[cid]) if present[cid] else float("nan")
            out[f"recall_{name}"] = float(recall[cid]) if present[cid] else float("nan")

        out["miou"] = float(iou[present].mean()) if bool(present.any()) else float("nan")
        # Diagnostic only -- see the module docstring. Never select a model on this.
        out["pixel_acc"] = float(tp.sum() / (mat.sum() + eps))
        return out


def format_headline(metrics: dict[str, float]) -> str:
    return "  ".join(f"{k}={metrics[k]:.4f}" for k in HEADLINE if k in metrics)


def demo() -> None:
    """Self-check: python -m train.metrics"""
    names = {0: "background", 1: "water", 2: "debris", 3: "clump"}

    # The failure this whole module exists to catch: predict all water on a frame
    # that is 90% water and 10% debris.
    target = torch.ones((1, 10, 10), dtype=torch.long)
    target[:, :1, :] = 2  # 10% debris
    pred = torch.ones_like(target)  # all water

    cm = ConfusionMatrix(4)
    cm.update(pred, target)
    m = cm.compute(names)

    assert m["pixel_acc"] > 0.89, m["pixel_acc"]  # looks excellent
    assert m["iou_debris"] == 0.0  # is useless
    assert m["recall_debris"] == 0.0
    assert m["miou"] < 0.5, m["miou"]
    assert "pixel_acc" not in HEADLINE

    # Absent classes must be NaN, not 0, so they cannot drag mIoU down.
    assert m["iou_background"] != m["iou_background"]  # NaN
    assert m["iou_clump"] != m["iou_clump"]

    # Perfect prediction.
    cm2 = ConfusionMatrix(4)
    cm2.update(target, target)
    m2 = cm2.compute(names)
    assert abs(m2["iou_debris"] - 1.0) < 1e-6
    assert abs(m2["miou"] - 1.0) < 1e-6

    # ignore_index must not contribute.
    t3 = torch.full((1, 4, 4), 255, dtype=torch.long)
    t3[0, 0, 0] = 2
    cm3 = ConfusionMatrix(4, ignore_index=255)
    cm3.update(torch.full((1, 4, 4), 2, dtype=torch.long), t3)
    assert int(cm3.mat.sum()) == 1, cm3.mat.sum()

    print("metrics self-check OK")


if __name__ == "__main__":
    demo()
