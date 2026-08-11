"""Heuristic `clump` derivation.

No source dataset has a clump class. This promotes large connected regions of
debris to `clump` so the class exists at all before Phase 2 hand-annotation.

These labels are WEAKER THAN THE REST and every mask touched by this function is
flagged `clump_heuristic: true` in meta.jsonl. Treat clump IoU as indicative, not
as ground truth, and remember the documented fallback: collapse clump into debris
in configs/classes.yaml and derive clumps post-hoc at inference time instead.
"""

from __future__ import annotations

from dataclasses import dataclass

import cv2
import numpy as np

from .schema import CLUMP, DEBRIS


@dataclass(frozen=True)
class ClumpParams:
    #: Region promoted to clump when its area exceeds this fraction of the image.
    min_area_frac: float = 0.005
    #: Morphological closing (px) applied to the debris mask before finding
    #: components. Individual items that are merely touching read as one mat to a
    #: human annotator; without closing they stay separate components and nothing
    #: ever crosses the area threshold. 0 disables.
    close_kernel: int = 5
    #: 4 or 8. 8-connectivity matches how a human reads a diagonal chain of items.
    connectivity: int = 8


def derive_clump(mask: np.ndarray, params: ClumpParams) -> tuple[np.ndarray, int]:
    """Promote large debris components to clump.

    Returns (new_mask, n_promoted). Input is not modified.
    """
    debris = (mask == DEBRIS).astype(np.uint8)
    if not debris.any():
        return mask, 0

    probe = debris
    if params.close_kernel > 0:
        k = np.ones((params.close_kernel, params.close_kernel), np.uint8)
        probe = cv2.morphologyEx(debris, cv2.MORPH_CLOSE, k)

    n_labels, labels, stats, _ = cv2.connectedComponentsWithStats(
        probe, connectivity=params.connectivity
    )
    min_area = params.min_area_frac * mask.size

    out = mask.copy()
    n_promoted = 0
    for i in range(1, n_labels):  # 0 is background
        if stats[i, cv2.CC_STAT_AREA] < min_area:
            continue
        # Promote only pixels that were really debris: closing can bridge across
        # water, and painting those as clump would invent foreground area, which
        # would corrupt the coverage metric this whole project is built on.
        out[(labels == i) & (mask == DEBRIS)] = CLUMP
        n_promoted += 1

    return out, n_promoted


def demo() -> None:
    """Self-check: python -m data.clump"""
    params = ClumpParams(min_area_frac=0.01, close_kernel=3)

    # One big blob (should promote) and one speck (should not).
    m = np.ones((100, 100), np.uint8)  # water
    m[10:40, 10:40] = DEBRIS  # 900 px = 9% of 10000
    m[90:92, 90:92] = DEBRIS  # 4 px
    out, n = derive_clump(m, params)
    assert n == 1, n
    assert (out[10:40, 10:40] == CLUMP).all()
    assert (out[90:92, 90:92] == DEBRIS).all()

    # Closing must not invent foreground: two blobs separated by water bridge to
    # one component, but the water between them stays water.
    m2 = np.ones((100, 100), np.uint8)
    m2[40:60, 10:50] = DEBRIS
    m2[40:60, 52:90] = DEBRIS
    out2, n2 = derive_clump(m2, params)
    assert n2 == 1, n2
    assert (out2[40:60, 50:52] == 1).all(), "closing leaked clump onto water pixels"

    # No debris -> untouched, and the original array is never mutated.
    m3 = np.ones((10, 10), np.uint8)
    out3, n3 = derive_clump(m3, params)
    assert n3 == 0 and (out3 == m3).all()

    print("clump self-check OK")


if __name__ == "__main__":
    demo()
