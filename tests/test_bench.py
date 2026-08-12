"""Checks for the comparison harness.

The harness is the deliverable a model gets chosen from, so the failures that
matter are the ones that would make a wrong model look right.
"""

from __future__ import annotations

import pytest

torch = pytest.importorskip("torch")

import numpy as np  # noqa: E402
import torch.nn as nn  # noqa: E402

from bench.accuracy import _degradation  # noqa: E402
from bench.cost import count_gflops, count_params, disk_size_mb, measure_latency  # noqa: E402
from bench.report import build  # noqa: E402
from models.yolo_seg import merge_instance_masks  # noqa: E402


class _Tiny(nn.Module):
    """Conv with a known parameter count: 3*4*3*3 weights + 4 biases = 112."""

    def __init__(self) -> None:
        super().__init__()
        self.c = nn.Conv2d(3, 4, 3, padding=1)

    def forward(self, x):
        return self.c(x)


class _FakeT:
    def __init__(self, a):
        self._a = a

    def cpu(self):
        return self

    def numpy(self):
        return self._a

    def __len__(self):
        return len(self._a)


class _FakeResult:
    def __init__(self, a):
        self.masks = type("M", (), {"data": _FakeT(a)})()


def test_param_count_is_exact() -> None:
    assert count_params(_Tiny()) == 3 * 4 * 3 * 3 + 4


def test_disk_size_is_measured_and_temp_file_removed(tmp_path) -> None:
    tmp = tmp_path / "m.pt"
    mb = disk_size_mb(_Tiny(), tmp)
    assert mb > 0
    assert not tmp.exists(), "benchmark left a temp checkpoint behind"


def test_gflops_scales_with_input_area() -> None:
    """A conv's FLOPs are linear in pixel count; 512 has ~1.51x the area of 416."""
    small = count_gflops(_Tiny(), 416)
    big = count_gflops(_Tiny(), 512)
    if small is None or big is None:
        pytest.skip("torch.utils.flop_counter unavailable")
    assert big > small
    assert abs((big / small) - (512**2) / (416**2)) < 0.05


def test_latency_reports_tail_not_just_mean() -> None:
    m = measure_latency(_Tiny(), size=64, runs=5, warmup=1)
    for key in ("mean_ms", "p50_ms", "p90_ms", "fps"):
        assert key in m
    assert m["p90_ms"] >= m["p50_ms"]
    assert m["mean_ms"] > 0 and m["fps"] > 0


def test_yolo_masks_are_unioned_never_summed() -> None:
    """Summing per-instance areas double-counts on overlap, and gets worse exactly
    when trash is densest -- the condition the project cares most about."""
    a = np.zeros((20, 20), dtype=np.float32)
    a[0:10, 0:10] = 1.0  # 100 px
    b = np.zeros((20, 20), dtype=np.float32)
    b[5:15, 5:15] = 1.0  # 100 px, 25 overlapping

    merged = merge_instance_masks(_FakeResult(np.stack([a, b])), (20, 20))
    assert int((merged > 0).sum()) == 175, "expected union 175; 200 means areas were summed"


def test_yolo_handles_a_frame_with_no_detections() -> None:
    class _R:
        masks = None

    assert merge_instance_masks(_R(), (8, 8)).sum() == 0
    empty = merge_instance_masks(_FakeResult(np.zeros((0, 8, 8), dtype=np.float32)), (8, 8))
    assert empty.sum() == 0


def test_degradation_is_relative_to_the_largest_resolution() -> None:
    by_res = {
        "640": {"iou_debris": 0.50, "miou": 0.80},
        "512": {"iou_debris": 0.40, "miou": 0.78},
        "416": {"iou_debris": 0.25, "miou": 0.76},
    }
    d = _degradation(by_res, [640, 512, 416])

    assert d["debris_iou_drop_pct"]["640"] == 0.0
    assert d["debris_iou_drop_pct"]["512"] == 20.0
    assert d["debris_iou_drop_pct"]["416"] == 50.0
    # The whole point: debris collapses 50% while mIoU moves 5%. An aggregate
    # metric would have hidden this.
    assert d["miou_drop_pct"]["416"] == 5.0


def test_degradation_survives_nan_and_missing_entries() -> None:
    by_res = {"640": {"iou_debris": float("nan"), "miou": 0.8}, "512": {"iou_debris": 0.4}}
    d = _degradation(by_res, [640, 512])
    assert d["debris_iou_drop_pct"]["512"] is None


def test_report_marks_accuracy_pending_when_untrained() -> None:
    """A missing accuracy table must be loudly PENDING, never an empty section
    that reads as 'measured and unremarkable'."""
    cost = {
        "host": {"cpu": "test", "machine": "x86_64", "torch": "2.0"},
        "threads": 1,
        "runs": 5,
        "warmup": 2,
        "resolutions": [512],
        "is_target_device": False,
        "models": [
            {
                "name": "m",
                "params_m": 1.0,
                "disk_mb": 4.0,
                "license": "MIT",
                "gflops": {"512": 1.0},
                "latency": {"512": {"mean_ms": 10.0, "p90_ms": 12.0}},
            }
        ],
        "failures": {},
    }
    md = build(cost, None)
    assert "PENDING" in md
    assert "PROXY, NOT THE TARGET" in md
    assert "Pixel accuracy appears nowhere" in md


def test_report_flags_target_device_when_measured_on_it() -> None:
    cost = {
        "host": {"cpu": "pi", "machine": "aarch64", "torch": "2.0"},
        "threads": 1,
        "runs": 5,
        "warmup": 2,
        "resolutions": [512],
        "is_target_device": True,
        "models": [],
        "failures": {},
    }
    md = build(cost, None)
    assert "PROXY" not in md
    assert "on the target device" in md
