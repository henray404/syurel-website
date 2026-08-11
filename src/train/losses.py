"""Losses for a severely imbalanced 4-class problem.

Water is 85-95% of pixels and debris is 1-3%. Plain cross-entropy optimises the
majority class and converges happily to "everything is water", which scores well
on pixel accuracy and is worthless. So:

  dice   -- region overlap, scale-invariant per class, so a 1% class contributes
            as much as a 90% one
  focal  -- down-weights easy pixels (the vast flat expanse of obvious water) so
            gradient goes to the hard boundaries
  ce     -- available, with optional per-class weights, mostly as a baseline that
            demonstrates exactly the failure above
  combo  -- "dice+focal" is the default: dice fixes the class balance, focal
            fixes the within-class easy/hard balance. They fail differently.

All of them honour ignore_index.
"""

from __future__ import annotations

from typing import Any

import torch
import torch.nn as nn
import torch.nn.functional as F


def _valid_mask(target: torch.Tensor, ignore_index: int) -> torch.Tensor:
    return target != ignore_index


class DiceLoss(nn.Module):
    """Soft multi-class Dice. Mean over classes present in the batch."""

    def __init__(self, ignore_index: int = 255, smooth: float = 1.0) -> None:
        super().__init__()
        self.ignore_index = ignore_index
        self.smooth = smooth

    def forward(self, logits: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        n_classes = logits.shape[1]
        probs = logits.softmax(dim=1)

        valid = _valid_mask(target, self.ignore_index)
        safe = target.clone()
        safe[~valid] = 0  # any in-range value; masked out below
        onehot = F.one_hot(safe, n_classes).permute(0, 3, 1, 2).to(probs.dtype)

        v = valid.unsqueeze(1).to(probs.dtype)
        probs, onehot = probs * v, onehot * v

        dims = (0, 2, 3)
        inter = (probs * onehot).sum(dims)
        card = probs.sum(dims) + onehot.sum(dims)
        dice = (2 * inter + self.smooth) / (card + self.smooth)

        # Skip classes absent from this batch: a free 1.0 for an absent class
        # hides real failures on the classes that matter.
        present = onehot.sum(dims) > 0
        if not bool(present.any()):
            return logits.sum() * 0.0
        return 1.0 - dice[present].mean()


class FocalLoss(nn.Module):
    """Multi-class focal loss (Lin et al. 2017)."""

    def __init__(
        self, gamma: float = 2.0, alpha: list[float] | None = None, ignore_index: int = 255
    ) -> None:
        super().__init__()
        self.gamma = gamma
        self.ignore_index = ignore_index
        self.register_buffer(
            "alpha", torch.tensor(alpha, dtype=torch.float32) if alpha else torch.empty(0)
        )

    def forward(self, logits: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        weight = self.alpha.to(logits.device) if self.alpha.numel() else None
        ce = F.cross_entropy(
            logits, target, weight=weight, ignore_index=self.ignore_index, reduction="none"
        )
        pt = torch.exp(-ce)  # ce = -log(pt)
        loss = ((1 - pt) ** self.gamma) * ce

        valid = _valid_mask(target, self.ignore_index)
        n = valid.sum()
        if n == 0:
            return logits.sum() * 0.0
        return loss[valid].sum() / n


class ComboLoss(nn.Module):
    """Weighted sum of named losses, e.g. 0.5*dice + 0.5*focal."""

    def __init__(self, parts: list[tuple[nn.Module, float]]) -> None:
        super().__init__()
        self.mods = nn.ModuleList([m for m, _ in parts])
        self.weights = [w for _, w in parts]

    def forward(self, logits: torch.Tensor, target: torch.Tensor) -> torch.Tensor:
        total = logits.sum() * 0.0
        for m, w in zip(self.mods, self.weights):
            total = total + w * m(logits, target)
        return total


def _one(name: str, cfg: dict[str, Any], n_classes: int, ignore_index: int) -> nn.Module:
    if name == "dice":
        return DiceLoss(ignore_index=ignore_index, smooth=float(cfg.get("smooth", 1.0)))
    if name == "focal":
        return FocalLoss(
            gamma=float(cfg.get("gamma", 2.0)), alpha=cfg.get("alpha"), ignore_index=ignore_index
        )
    if name == "ce":
        w = cfg.get("class_weights")
        return nn.CrossEntropyLoss(
            weight=torch.tensor(w, dtype=torch.float32) if w else None, ignore_index=ignore_index
        )
    raise ValueError(f"unknown loss {name!r}; known: dice, focal, ce (combine with '+')")


def build_loss(cfg: dict[str, Any], n_classes: int, ignore_index: int = 255) -> nn.Module:
    """cfg example::

        loss:
          name: dice+focal
          weights: [0.5, 0.5]
          focal: {gamma: 2.0}
          dice:  {smooth: 1.0}
    """
    name = str(cfg.get("name", "dice+focal"))
    names = [p.strip() for p in name.split("+") if p.strip()]

    if name == "ce":
        # Not an error -- just make sure it was on purpose.
        print(
            "[loss] WARNING: plain cross-entropy on a 1-3% debris class converges to "
            "'everything is water'. Use it as a baseline, not as the real run."
        )

    if len(names) == 1:
        return _one(names[0], cfg.get(names[0]) or {}, n_classes, ignore_index)

    weights = cfg.get("weights") or [1.0 / len(names)] * len(names)
    if len(weights) != len(names):
        raise ValueError(f"loss.weights has {len(weights)} entries but {len(names)} losses")
    parts = [
        (_one(n, cfg.get(n) or {}, n_classes, ignore_index), float(w))
        for n, w in zip(names, weights)
    ]
    return ComboLoss(parts)


def demo() -> None:
    """Self-check: python -m train.losses"""
    torch.manual_seed(0)
    B, C, H, W = 2, 4, 16, 16

    target = torch.ones((B, H, W), dtype=torch.long)  # water
    target[:, :2, :] = 2  # ~12% debris

    perfect = F.one_hot(target, C).permute(0, 3, 1, 2).float() * 20.0
    all_water = torch.zeros((B, C, H, W))
    all_water[:, 1] = 20.0

    for name in ("dice", "focal", "dice+focal"):
        loss = build_loss({"name": name}, C)
        good, bad = float(loss(perfect, target)), float(loss(all_water, target))
        assert good < bad, f"{name}: perfect {good} should beat all-water {bad}"
        assert good >= 0.0

    # ignore_index must be excluded, not silently treated as a class.
    ign = target.clone()
    ign[:, 8:, :] = 255
    assert float(DiceLoss()(perfect, ign)) < 0.1

    # A batch that is entirely ignore must not produce NaN.
    allign = torch.full((B, H, W), 255, dtype=torch.long)
    assert float(DiceLoss()(perfect, allign)) == 0.0
    assert float(FocalLoss()(perfect, allign)) == 0.0

    # Dice must not reward absent classes: clump (id 3) never appears above.
    assert float(DiceLoss()(perfect, target)) < 0.05

    print("losses self-check OK")


if __name__ == "__main__":
    demo()
