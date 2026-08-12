"""YOLO11n-seg reference baseline.

NOT a training candidate and NOT eligible to win the comparison. Two reasons,
both structural:

1. LICENCE. ultralytics is AGPL-3.0. Deploying it in a networked system can
   oblige you to release your own source. Kept in the `yolo` extra so it is
   never installed by accident.

2. IT CANNOT PRODUCE THE METRIC. Coverage is
   (debris+clump) / (debris+clump+water). YOLO gives instance masks for debris
   and has NO water class, so the denominator does not exist. A YOLO-only
   deployment would still need a second model for water. This is the honest
   reason semantic segmentation was the right call, and the number this baseline
   contributes is "how good is debris masking alone", nothing more.

Masks are merged with bitwise OR, never by summing per-instance areas: two
overlapping instances covering 100 px of river are 100 px of debris, not 200.
Summing is the standard way to silently overstate coverage, and it gets worse
exactly when trash is densest -- the condition the project cares most about.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from data.schema import DEBRIS

_INSTALL_HINT = (
    "ultralytics is not installed (AGPL-3.0 -- read the module docstring first). "
    "Run: uv sync --extra yolo"
)


def load_yolo(weights: str | Path = "yolo11n-seg.pt"):
    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise RuntimeError(_INSTALL_HINT) from exc
    return YOLO(str(weights))


def merge_instance_masks(result, shape: tuple[int, int]) -> np.ndarray:
    """Ultralytics result -> semantic mask with only background and debris.

    bitwise OR over instances. Never a sum.
    """
    out = np.zeros(shape, dtype=np.uint8)
    masks = getattr(result, "masks", None)
    if masks is None or masks.data is None or len(masks.data) == 0:
        return out

    union = np.zeros(shape, dtype=bool)
    for m in masks.data.cpu().numpy():
        if m.shape != shape:
            from PIL import Image

            m = np.array(
                Image.fromarray((m > 0.5).astype(np.uint8)).resize(
                    (shape[1], shape[0]), Image.Resampling.NEAREST
                )
            )
        union |= m > 0.5  # OR, not +=

    out[union] = DEBRIS
    return out


def demo() -> None:
    """Self-check: python -m models.yolo_seg  (no ultralytics needed)"""

    class _FakeTensor:
        def __init__(self, arr):
            self._arr = arr

        def cpu(self):
            return self

        def numpy(self):
            return self._arr

        def __len__(self):
            return len(self._arr)

    class _FakeMasks:
        def __init__(self, arr):
            self.data = _FakeTensor(arr)

    class _FakeResult:
        def __init__(self, arr):
            self.masks = _FakeMasks(arr)

    # Two instances overlapping on 25 px. Union is 175; the sum would be 200.
    a = np.zeros((20, 20), dtype=np.float32)
    a[0:10, 0:10] = 1.0  # 100 px
    b = np.zeros((20, 20), dtype=np.float32)
    b[5:15, 5:15] = 1.0  # 100 px, 25 shared

    merged = merge_instance_masks(_FakeResult(np.stack([a, b])), (20, 20))
    n = int((merged == DEBRIS).sum())
    assert n == 175, f"expected union 175, got {n} (200 means areas were summed)"

    empty = merge_instance_masks(_FakeResult(np.zeros((0, 20, 20), dtype=np.float32)), (20, 20))
    assert empty.sum() == 0

    print("yolo_seg self-check OK (union 175, not 200)")


if __name__ == "__main__":
    demo()
