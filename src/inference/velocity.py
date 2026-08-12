"""Surface velocity from optical flow on RAW frames.

DESIGN NOTE, and it is the important one in this module.

The obvious implementation is to run optical flow over consecutive *segmentation
masks*. That does not work here, and the Task 4 benchmark is what shows why: on a
Pi-class CPU the segmentation model runs at roughly 1-2 s/frame. Debris drifting
at 0.5 m/s has moved 0.5-1 m between two consecutive model outputs and may have
left the ROI entirely, so there is no correspondence left for flow to find. Masks
are also nearly featureless -- flat blobs give a flow field almost no gradient to
lock onto.

So flow runs on **raw grayscale frames at camera rate**, where consecutive frames
are ~33 ms apart and full of texture. The segmentation mask is used only to decide
which flow vectors count as debris. That decouples velocity accuracy from model
latency completely: the model can be slow without the velocity becoming wrong.

Consequence for the caller: it must keep feeding frames at camera rate even while
segmentation is skipped. run.py does this.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

import cv2
import numpy as np


@dataclass
class VelocityParams:
    #: Downscale before flow. Flow is the cheap part, but a Pi is a Pi.
    scale: float = 0.5
    #: Ignore vectors below this magnitude (px/frame); still water is not motion.
    min_magnitude_px: float = 0.3
    #: Median over this many recent estimates. Optical flow is spiky.
    smooth_window: int = 15
    #: Farneback parameters. Defaults are the usual starting point.
    pyr_scale: float = 0.5
    levels: int = 3
    winsize: int = 21
    iterations: int = 3
    poly_n: int = 5
    poly_sigma: float = 1.2


@dataclass
class VelocityEstimator:
    params: VelocityParams = field(default_factory=VelocityParams)
    _prev: np.ndarray | None = field(default=None, repr=False)
    _history: deque = field(default_factory=deque, repr=False)

    def __post_init__(self) -> None:
        self._history = deque(maxlen=max(1, self.params.smooth_window))

    def _prep(self, frame_bgr: np.ndarray) -> np.ndarray:
        gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        s = self.params.scale
        if s != 1.0:
            gray = cv2.resize(gray, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
        return gray

    def update(
        self, frame_bgr: np.ndarray, debris_mask: np.ndarray | None, dt_seconds: float
    ) -> dict[str, float | int | None]:
        """Feed one raw frame. Call at camera rate, not at model rate.

        `debris_mask` may be a cached mask from an older segmentation pass -- that
        is the point of the decoupling. Pass None to measure whole-frame flow.
        """
        gray = self._prep(frame_bgr)
        if self._prev is None or self._prev.shape != gray.shape:
            self._prev = gray
            return {"velocity_px_s": None, "n_vectors": 0, "raw_px_s": None}

        flow = cv2.calcOpticalFlowFarneback(
            self._prev,
            gray,
            None,
            self.params.pyr_scale,
            self.params.levels,
            self.params.winsize,
            self.params.iterations,
            self.params.poly_n,
            self.params.poly_sigma,
            0,
        )
        self._prev = gray

        mag = np.linalg.norm(flow, axis=2)
        sel = mag > self.params.min_magnitude_px

        if debris_mask is not None:
            small = cv2.resize(
                debris_mask.astype(np.uint8),
                (mag.shape[1], mag.shape[0]),
                interpolation=cv2.INTER_NEAREST,
            ).astype(bool)
            sel &= small

        n = int(sel.sum())
        if n == 0 or dt_seconds <= 0:
            return {"velocity_px_s": self.smoothed(), "n_vectors": 0, "raw_px_s": None}

        # Median, not mean: glare and rain streaks produce large spurious vectors,
        # and a mean lets a handful of them set the answer.
        px_per_frame = float(np.median(mag[sel]))
        # Undo the downscale so the result is in ORIGINAL pixel units.
        raw = px_per_frame / max(1e-9, self.params.scale) / dt_seconds

        self._history.append(raw)
        return {"velocity_px_s": self.smoothed(), "n_vectors": n, "raw_px_s": round(raw, 3)}

    def smoothed(self) -> float | None:
        if not self._history:
            return None
        return round(float(np.median(self._history)), 3)

    def reset(self) -> None:
        self._prev = None
        self._history.clear()


def demo() -> None:
    """Self-check: python -m inference.velocity"""
    rng = np.random.default_rng(0)
    # Textured frame; a flat frame gives optical flow nothing to track.
    base = rng.integers(0, 255, size=(120, 160, 3), dtype=np.uint8)

    est = VelocityEstimator(VelocityParams(scale=1.0, smooth_window=5, min_magnitude_px=0.1))

    first = est.update(base, None, 1 / 30)
    assert first["velocity_px_s"] is None, "first frame cannot have a velocity"

    # Shift right 4 px per frame at 30 fps -> 120 px/s.
    prev = base
    out = first
    for _ in range(6):
        moved = np.roll(prev, 4, axis=1)
        out = est.update(moved, None, 1 / 30)
        prev = moved

    v = out["velocity_px_s"]
    assert v is not None
    assert 90 < v < 150, f"expected ~120 px/s, got {v}"

    # A still scene must not report motion.
    est2 = VelocityEstimator(VelocityParams(scale=1.0, min_magnitude_px=0.3))
    est2.update(base, None, 1 / 30)
    still = est2.update(base, None, 1 / 30)
    assert still["n_vectors"] == 0, still

    # An empty debris mask means no debris vectors, not a crash.
    est3 = VelocityEstimator(VelocityParams(scale=1.0, min_magnitude_px=0.1))
    empty = np.zeros((120, 160), dtype=bool)
    est3.update(base, empty, 1 / 30)
    masked = est3.update(np.roll(base, 4, axis=1), empty, 1 / 30)
    assert masked["n_vectors"] == 0, masked

    print(f"velocity self-check OK (measured {v} px/s for a 4 px/frame shift at 30 fps)")


if __name__ == "__main__":
    demo()
