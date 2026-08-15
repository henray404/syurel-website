"""ROI / structure polygons, and the homography hook.

Two jobs:

1. Rasterise the static polygons from the site config. A fixed camera means these
   never move, so they are drawn once and reused for every frame.

2. Hold the interface for pixel -> metric conversion WITHOUT implementing it.
   Calibration needs the site, which does not exist yet (Phase 2). Until then
   every areal and velocity figure is a PIXEL RATIO, and this module makes that
   impossible to forget: `PixelGeometry.is_metric` is False, and every consumer
   labels its output as a relative index rather than m^2 or m/s.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import cv2
import numpy as np

_PHASE2 = (
    "Homography calibration is Phase 2 and is not implemented.\n"
    "It needs four surveyed points on the water surface at the deployment site.\n"
    "Set homography.enabled: false to keep pixel-ratio output, which is a valid "
    "RELATIVE INDEX for trend and correlation work -- just not a physical measurement."
)


def polygon_mask(points: list[list[float]] | None, shape: tuple[int, int]) -> np.ndarray:
    """Filled bool mask from [[x, y], ...]. None/empty -> all True (whole frame)."""
    h, w = shape
    if not points:
        return np.ones((h, w), dtype=bool)
    pts = np.array([[int(round(x)), int(round(y))] for x, y in points], dtype=np.int32)
    canvas = np.zeros((h, w), dtype=np.uint8)
    cv2.fillPoly(canvas, [pts], 1)
    return canvas.astype(bool)


class Geometry(Protocol):
    """Pixel -> world conversion. See PixelGeometry for the un-calibrated default."""

    is_metric: bool
    units_area: str
    units_velocity: str

    def area(self, n_pixels: int) -> float: ...
    def velocity(self, pixels_per_second: float) -> float: ...


@dataclass(frozen=True)
class PixelGeometry:
    """No calibration. Everything stays in pixel units.

    Not a placeholder that silently returns wrong numbers -- it returns honest
    pixel counts and flags them as such, so no CSV column ever claims to be m^2
    when it is px^2.
    """

    is_metric: bool = False
    units_area: str = "px2"
    units_velocity: str = "px/s"

    def area(self, n_pixels: int) -> float:
        return float(n_pixels)

    def velocity(self, pixels_per_second: float) -> float:
        return float(pixels_per_second)


@dataclass(frozen=True)
class HomographyGeometry:
    """Phase 2. Deliberately NOT implemented.

    Implementing this without site measurements would mean inventing a scale
    factor, and every downstream m^2/s figure would be fiction dressed as a
    measurement. The interface exists so the call sites are already correct; the
    body lands once there are four surveyed points on the water surface.

    Config shape it will consume (see configs/inference/site_example.yaml):

        homography:
          enabled: true
          image_points:  [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]   # pixels
          world_points:  [[X1,Y1], [X2,Y2], [X3,Y3], [X4,Y4]]   # metres
          cross_section_width_m: 12.0
    """

    is_metric: bool = True
    units_area: str = "m2"
    units_velocity: str = "m/s"

    def area(self, n_pixels: int) -> float:
        raise NotImplementedError(_PHASE2)

    def velocity(self, pixels_per_second: float) -> float:
        raise NotImplementedError(_PHASE2)


def build_geometry(cfg: dict[str, Any]) -> Geometry:
    homography = cfg.get("homography") or {}
    if homography.get("enabled"):
        raise NotImplementedError(_PHASE2)
    return PixelGeometry()


@dataclass
class SiteMasks:
    roi: np.ndarray
    structure: np.ndarray
    shape: tuple[int, int]

    @property
    def roi_pixels(self) -> int:
        return int(self.roi.sum())

    @property
    def structure_pixels(self) -> int:
        return int(self.structure.sum())


def build_masks(cfg: dict[str, Any], shape: tuple[int, int]) -> SiteMasks:
    # An absent ROI means "the whole frame"; an absent STRUCTURE means "there is no
    # structure", which is not the same thing. Reusing the whole-frame default for
    # the structure made accumulation equal to total debris, so a site with no
    # surveyed pier raised blockage alerts on ordinary passing trash.
    roi = polygon_mask(cfg.get("roi"), shape)
    if cfg.get("structure"):
        # The structure sits inside the field of view; intersecting with the ROI
        # keeps accumulation from counting pier pixels deliberately excluded.
        structure = polygon_mask(cfg["structure"], shape) & roi
    else:
        structure = np.zeros(shape, dtype=bool)
    return SiteMasks(roi=roi, structure=structure, shape=shape)


def demo() -> None:
    """Self-check: python -m inference.geometry"""
    shape = (100, 100)

    assert polygon_mask(None, shape).all(), "no ROI configured must mean the whole frame"

    square = polygon_mask([[10, 10], [50, 10], [50, 50], [10, 50]], shape)
    assert 1500 < int(square.sum()) < 1700, int(square.sum())  # ~40x40

    cfg = {
        "roi": [[0, 0], [60, 0], [60, 60], [0, 60]],
        "structure": [[50, 50], [90, 50], [90, 90], [50, 90]],
    }
    masks = build_masks(cfg, shape)
    # Structure is clipped to the ROI: only the overlapping corner survives.
    assert masks.structure_pixels < 400, masks.structure_pixels
    assert not (masks.structure & ~masks.roi).any(), "structure leaked outside the ROI"

    g = build_geometry({})
    assert g.is_metric is False
    assert g.area(500) == 500.0 and g.units_area == "px2"

    try:
        build_geometry({"homography": {"enabled": True}})
    except NotImplementedError as exc:
        assert "Phase 2" in str(exc)
    else:
        raise AssertionError("enabling homography must refuse, not silently fake a scale")

    print("geometry self-check OK")


if __name__ == "__main__":
    demo()
