"""Coverage, temporal smoothing, area flux, and the blockage alert.

Coverage is defined against WATER, not against the frame:

    coverage = (debris + clump) / (debris + clump + water)

all counted inside the ROI. Dividing by frame area instead would make the number
depend on how much sky and bank the camera happens to see, which changes if anyone
ever nudges the mount. Dividing by water makes it a property of the river.

If the denominator is zero -- no water and no debris visible, e.g. the ROI is
fully occluded or the model collapsed -- coverage is None, never 0.0. A silent 0.0
reads as "clean river" and is exactly the wrong thing to log during a flood.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from data.schema import CLUMP, DEBRIS, WATER

from .geometry import Geometry, SiteMasks


@dataclass
class SmoothingParams:
    #: Number of recent coverage samples in the rolling window.
    window: int = 30
    #: "median" resists single-frame spikes from glare; "mean" tracks faster.
    method: str = "median"


@dataclass
class BlockageParams:
    #: Fraction of the structure polygon covered by debris before alerting.
    area_threshold: float = 0.30
    #: Growth rate over `growth_window_s` that alerts even below the area
    #: threshold. Rapid accumulation is the early warning; a slow steady mat is
    #: expected and is not an emergency.
    growth_threshold_per_min: float = 0.10
    growth_window_s: float = 300.0
    #: Consecutive samples above threshold before the alert fires. One noisy frame
    #: must not dispatch a cleanup crew.
    consecutive: int = 3


def frame_metrics(mask: np.ndarray, masks: SiteMasks, geometry: Geometry) -> dict[str, Any]:
    """Per-frame counts. `mask` is a class-index mask, same shape as the ROI."""
    in_roi = mask[masks.roi]

    debris_px = int(((in_roi == DEBRIS) | (in_roi == CLUMP)).sum())
    water_px = int((in_roi == WATER).sum())
    denom = debris_px + water_px

    in_struct = mask[masks.structure]
    accum_px = int(((in_struct == DEBRIS) | (in_struct == CLUMP)).sum())
    struct_total = max(1, masks.structure_pixels)

    return {
        "coverage": (debris_px / denom) if denom > 0 else None,
        "debris_px": debris_px,
        "water_px": water_px,
        "roi_px": masks.roi_pixels,
        "accumulation_px": accum_px,
        "accumulation_frac": accum_px / struct_total,
        "debris_area": geometry.area(debris_px),
        "accumulation_area": geometry.area(accum_px),
        "area_units": geometry.units_area,
        "is_metric": geometry.is_metric,
    }


@dataclass
class Smoother:
    params: SmoothingParams = field(default_factory=SmoothingParams)
    _values: deque = field(default_factory=deque, repr=False)

    def __post_init__(self) -> None:
        self._values = deque(maxlen=max(1, self.params.window))

    def update(self, value: float | None) -> float | None:
        # None means "not measurable this frame". Dropping it is right: pushing a
        # 0.0 would drag the smoothed value toward "clean" on missing data.
        if value is not None:
            self._values.append(float(value))
        return self.value

    @property
    def value(self) -> float | None:
        if not self._values:
            return None
        arr = np.asarray(self._values, dtype=float)
        v = float(np.median(arr)) if self.params.method == "median" else float(arr.mean())
        return round(v, 6)

    @property
    def n(self) -> int:
        return len(self._values)


@dataclass
class BlockageMonitor:
    """Alerts on accumulation area against the structure, and on its growth rate."""

    params: BlockageParams = field(default_factory=BlockageParams)
    _history: deque = field(default_factory=deque, repr=False)  # (timestamp, frac)
    _streak: int = 0
    _latched: bool = False

    def update(self, accumulation_frac: float, timestamp: float) -> dict[str, Any]:
        self._history.append((timestamp, float(accumulation_frac)))
        cutoff = timestamp - self.params.growth_window_s
        while len(self._history) > 2 and self._history[0][0] < cutoff:
            self._history.popleft()

        growth_per_min: float | None = None
        if len(self._history) >= 2:
            (t0, f0), (t1, f1) = self._history[0], self._history[-1]
            dt_min = (t1 - t0) / 60.0
            if dt_min > 1e-6:
                growth_per_min = (f1 - f0) / dt_min

        over_area = accumulation_frac >= self.params.area_threshold
        over_growth = (
            growth_per_min is not None and growth_per_min >= self.params.growth_threshold_per_min
        )
        triggered = over_area or over_growth

        self._streak = self._streak + 1 if triggered else 0
        alert = self._streak >= self.params.consecutive
        self._latched = self._latched or alert

        reason = ""
        if alert:
            parts = []
            if over_area:
                parts.append(f"area {accumulation_frac:.2f} >= {self.params.area_threshold}")
            if over_growth:
                parts.append(
                    f"growth {growth_per_min:.3f}/min >= {self.params.growth_threshold_per_min}"
                )
            reason = "; ".join(parts)

        return {
            "alert": bool(alert),
            "alert_reason": reason,
            "growth_per_min": None if growth_per_min is None else round(growth_per_min, 5),
            "streak": self._streak,
            "ever_alerted": self._latched,
        }


def area_flux(
    coverage: float | None,
    velocity: float | None,
    cross_section_width: float,
    geometry: Geometry,
) -> dict[str, Any]:
    """flux = coverage * velocity * width.

    With PixelGeometry this is a RELATIVE INDEX, not m^2/s. The units field says
    so, and run.py writes it into the CSV, so a later analysis cannot mistake it
    for a physical measurement.
    """
    if coverage is None or velocity is None:
        return {"area_flux": None, "flux_units": "n/a"}

    value = coverage * velocity * cross_section_width
    units = f"{geometry.units_area}/s" if geometry.is_metric else "relative_index"
    return {"area_flux": round(value, 6), "flux_units": units}


def demo() -> None:
    """Self-check: python -m inference.metrics"""
    from .geometry import PixelGeometry, build_masks

    shape = (100, 100)
    masks = build_masks({"roi": None, "structure": [[0, 0], [50, 0], [50, 50], [0, 50]]}, shape)
    geom = PixelGeometry()

    # 20% of the water surface is debris.
    m = np.full(shape, WATER, dtype=np.uint8)
    m[:20, :] = DEBRIS
    r = frame_metrics(m, masks, geom)
    assert abs(r["coverage"] - 0.20) < 1e-6, r["coverage"]
    assert r["area_units"] == "px2" and r["is_metric"] is False

    # clump must count as foreground alongside debris.
    m2 = np.full(shape, WATER, dtype=np.uint8)
    m2[:10, :] = DEBRIS
    m2[10:20, :] = CLUMP
    assert abs(frame_metrics(m2, masks, geom)["coverage"] - 0.20) < 1e-6

    # Background must not enter the denominator: half the frame is bank.
    m3 = np.zeros(shape, dtype=np.uint8)  # background
    m3[50:, :] = WATER
    m3[50:60, :] = DEBRIS
    cov = frame_metrics(m3, masks, geom)["coverage"]
    assert abs(cov - 0.20) < 1e-6, f"background leaked into the denominator: {cov}"

    # No water and no debris -> None, never 0.0.
    assert frame_metrics(np.zeros(shape, dtype=np.uint8), masks, geom)["coverage"] is None

    # Smoothing ignores None rather than treating it as clean water.
    s = Smoother(SmoothingParams(window=5, method="median"))
    for v in (0.1, 0.2, 0.3):
        s.update(v)
    assert s.update(None) == 0.2 and s.n == 3

    # Blockage: needs a streak, then latches.
    mon = BlockageMonitor(BlockageParams(area_threshold=0.3, consecutive=3))
    assert not mon.update(0.5, 0.0)["alert"]
    assert not mon.update(0.5, 1.0)["alert"]
    third = mon.update(0.5, 2.0)
    assert third["alert"] and "area" in third["alert_reason"]

    # Growth alone can alert while area is still below threshold.
    mon2 = BlockageMonitor(
        BlockageParams(area_threshold=0.9, growth_threshold_per_min=0.1, consecutive=1)
    )
    mon2.update(0.00, 0.0)
    grow = mon2.update(0.20, 60.0)  # +0.20 over one minute
    assert grow["alert"] and "growth" in grow["alert_reason"], grow

    # A single spike must not alert.
    mon3 = BlockageMonitor(BlockageParams(area_threshold=0.3, consecutive=3))
    mon3.update(0.5, 0.0)
    assert not mon3.update(0.0, 1.0)["alert"]
    assert mon3.update(0.5, 2.0)["streak"] == 1

    # Flux is labelled relative while un-calibrated.
    f = area_flux(0.2, 100.0, 12.0, geom)
    assert f["flux_units"] == "relative_index"
    assert area_flux(None, 100.0, 12.0, geom)["area_flux"] is None

    print("metrics self-check OK")


if __name__ == "__main__":
    demo()
