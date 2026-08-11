"""Checks for the training pieces that can quietly produce a useless model.

Skipped wholesale when torch is absent, so `uv sync` without --extra train still
gives a green suite.
"""

from __future__ import annotations

import pytest

torch = pytest.importorskip("torch")

import torch.nn.functional as F  # noqa: E402

from train.losses import DiceLoss, FocalLoss, build_loss  # noqa: E402
from train.metrics import HEADLINE, ConfusionMatrix  # noqa: E402

NAMES = {0: "background", 1: "water", 2: "debris", 3: "clump"}


def _imbalanced(debris_rows: int = 1, size: int = 10):
    """A frame that is 90% water and 10% debris -- the real class distribution."""
    target = torch.ones((1, size, size), dtype=torch.long)
    target[:, :debris_rows, :] = 2
    return target


def test_all_water_model_scores_high_pixel_acc_and_zero_debris_iou() -> None:
    """The exact failure the brief calls out: ~90% accuracy, completely useless."""
    target = _imbalanced()
    cm = ConfusionMatrix(4)
    cm.update(torch.ones_like(target), target)
    m = cm.compute(NAMES)

    assert m["pixel_acc"] > 0.89
    assert m["iou_debris"] == 0.0
    assert m["recall_debris"] == 0.0


def test_pixel_accuracy_can_never_be_a_headline_metric() -> None:
    assert "pixel_acc" not in HEADLINE
    assert set(HEADLINE) == {"miou", "iou_debris", "precision_debris", "recall_debris"}


def test_absent_classes_are_nan_not_zero() -> None:
    """A class that never appears must not drag mIoU down."""
    target = _imbalanced()
    cm = ConfusionMatrix(4)
    cm.update(target, target)
    m = cm.compute(NAMES)

    assert m["iou_clump"] != m["iou_clump"]  # NaN, class 3 absent
    assert abs(m["miou"] - 1.0) < 1e-6, "perfect prediction must be mIoU 1.0"


def test_confusion_matrix_ignores_ignore_index_and_out_of_range() -> None:
    target = torch.full((1, 4, 4), 255, dtype=torch.long)
    target[0, 0, 0] = 2
    target[0, 1, 1] = 99  # out of schema; must not corrupt a real cell
    cm = ConfusionMatrix(4, ignore_index=255)
    cm.update(torch.full((1, 4, 4), 2, dtype=torch.long), target)
    assert int(cm.mat.sum()) == 1


def test_metrics_accumulate_across_batches() -> None:
    target = _imbalanced()
    cm = ConfusionMatrix(4)
    cm.update(target, target)
    cm.update(target, target)
    assert int(cm.mat.sum()) == 200


@pytest.mark.parametrize("name", ["dice", "focal", "dice+focal", "ce"])
def test_every_loss_prefers_the_correct_prediction(name: str) -> None:
    target = _imbalanced(debris_rows=2, size=16)
    perfect = F.one_hot(target, 4).permute(0, 3, 1, 2).float() * 20.0
    all_water = torch.zeros((1, 4, 16, 16))
    all_water[:, 1] = 20.0

    loss = build_loss({"name": name}, 4)
    assert float(loss(perfect, target)) < float(loss(all_water, target))


def _grad_ratio(loss_name: str) -> float:
    """Mean per-pixel gradient magnitude on debris pixels / on water pixels.

    Loss *values* are not comparable across loss functions -- they live on
    different scales -- so the meaningful question is where the gradient goes.
    """
    target = _imbalanced(debris_rows=1, size=32)  # debris ~3% of pixels
    logits = torch.zeros((1, 4, 32, 32), requires_grad=True)  # uniform prediction
    build_loss({"name": loss_name}, 4)(logits, target).backward()

    g = logits.grad[0].abs().sum(0)
    return float(g[target[0] == 2].mean()) / float(g[target[0] == 1].mean())


def test_ce_spreads_gradient_uniformly_so_a_3_percent_class_gets_3_percent_of_it() -> None:
    """Why plain CE is not the default: every pixel counts the same, so the
    minority class is simply outvoted."""
    assert abs(_grad_ratio("ce") - 1.0) < 0.01


def test_dice_concentrates_gradient_on_the_minority_class() -> None:
    """Dice normalises per class, so a debris pixel carries several times the
    weight of a water pixel. This is the actual mechanism that stops the model
    collapsing to all-water.

    Note focal alone measures ~1.0 here: at uniform logits every pixel is equally
    hard, so focal has nothing to down-weight yet. Its benefit appears once the
    model is partially trained and the easy water is already solved -- which is
    exactly why the default is dice+focal rather than either alone.
    """
    assert _grad_ratio("dice") > 3.0, _grad_ratio("dice")
    assert _grad_ratio("dice+focal") > _grad_ratio("ce")


def test_losses_are_finite_when_batch_is_entirely_ignored() -> None:
    logits = torch.randn(2, 4, 8, 8)
    allign = torch.full((2, 8, 8), 255, dtype=torch.long)
    for fn in (DiceLoss(), FocalLoss()):
        v = float(fn(logits, allign))
        assert v == 0.0 and v == v


def test_combo_weights_are_applied() -> None:
    target = _imbalanced(debris_rows=2, size=16)
    logits = torch.randn(1, 4, 16, 16)

    dice_only = float(build_loss({"name": "dice"}, 4)(logits, target))
    focal_only = float(build_loss({"name": "focal"}, 4)(logits, target))
    combo = float(build_loss({"name": "dice+focal", "weights": [0.25, 0.75]}, 4)(logits, target))
    assert abs(combo - (0.25 * dice_only + 0.75 * focal_only)) < 1e-5


def test_mismatched_combo_weights_are_rejected() -> None:
    with pytest.raises(ValueError, match="loss.weights"):
        build_loss({"name": "dice+focal", "weights": [1.0]}, 4)


def test_unknown_loss_name_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown loss"):
        build_loss({"name": "magic"}, 4)


def test_dice_gradient_reaches_a_one_percent_class() -> None:
    """If the minority class produces no gradient, nothing else matters."""
    target = torch.ones((1, 32, 32), dtype=torch.long)
    target[:, :1, :3] = 2  # 3 pixels of 1024, ~0.3%

    logits = torch.zeros((1, 4, 32, 32), requires_grad=True)
    DiceLoss()(logits, target).backward()

    debris_grad = logits.grad[0, 2, :1, :3].abs().sum()
    assert float(debris_grad) > 0, "no gradient flowed to the debris class"


def test_model_registry_returns_input_resolution_logits() -> None:
    pytest.importorskip("torchvision")
    from models import build_model, registered

    assert "lraspp_mnv3" in registered()
    net = build_model("lraspp_mnv3", n_classes=4, pretrained=False).eval()
    with torch.no_grad():
        out = net(torch.randn(1, 3, 128, 128))
    assert out.shape == (1, 4, 128, 128), out.shape


def test_balanced_sampler_caps_a_dominant_dataset() -> None:
    """Without capping the mix is ~55% RiSID and the model overfits one source."""
    from pathlib import Path

    from train.dataset import BalancedEpochSampler, Item

    items = [Item("risid", f"r{i}", Path("x"), Path("y")) for i in range(1000)]
    items += [Item("riptseg", f"p{i}", Path("x"), Path("y")) for i in range(50)]

    s = BalancedEpochSampler(items, cap=100, weights={"risid": 0.5, "riptseg": 1.0}, seed=1)
    picked = list(s)
    counts = {"risid": 0, "riptseg": 0}
    for i in picked:
        counts[items[i].dataset] += 1

    assert counts["risid"] == 50, counts  # cap 100 * weight 0.5
    assert counts["riptseg"] == 50, counts  # only 50 exist, cannot exceed
    assert len(picked) == len(s)
    assert len(set(picked)) == len(picked), "sampled without replacement"


def test_balanced_sampler_is_reproducible_per_epoch() -> None:
    from pathlib import Path

    from train.dataset import BalancedEpochSampler, Item

    items = [Item("a", f"a{i}", Path("x"), Path("y")) for i in range(100)]
    a = BalancedEpochSampler(items, cap=20, seed=7)
    b = BalancedEpochSampler(items, cap=20, seed=7)
    a.set_epoch(3)
    b.set_epoch(3)
    assert list(a) == list(b)

    a.set_epoch(4)
    assert list(a) != list(b), "epochs must reshuffle"
