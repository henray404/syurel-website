"""Checks for the inference metrics.

The failure mode that matters here is a plausible-looking number that is wrong:
a coverage of 0.0 when the ROI is occluded, an m^2/s label on an uncalibrated
pixel ratio, or an alert that fires on a single noisy frame.
"""

from __future__ import annotations

import sqlite3

import numpy as np
import pytest

from data.schema import BACKGROUND, CLUMP, DEBRIS, WATER
from inference.geometry import PixelGeometry, build_geometry, build_masks, polygon_mask
from inference.metrics import (
    BlockageMonitor,
    BlockageParams,
    Smoother,
    SmoothingParams,
    area_flux,
    frame_metrics,
)
from inference.sink import TimeSeriesSink

SHAPE = (100, 100)


@pytest.fixture
def masks():
    return build_masks({"roi": None, "structure": [[0, 0], [50, 0], [50, 50], [0, 50]]}, SHAPE)


@pytest.fixture
def geom():
    return PixelGeometry()


def test_coverage_denominator_is_water_not_frame_area(masks, geom) -> None:
    """Dividing by frame area would make the metric depend on how much sky the
    camera sees, which changes if anyone nudges the mount."""
    m = np.zeros(SHAPE, dtype=np.uint8)  # half the frame is bank/background
    m[50:, :] = WATER
    m[50:60, :] = DEBRIS  # 1000 debris px, 4000 water px

    cov = frame_metrics(m, masks, geom)["coverage"]
    assert abs(cov - 0.2) < 1e-9, f"background leaked into the denominator: {cov}"


def test_clump_counts_as_foreground(masks, geom) -> None:
    a = np.full(SHAPE, WATER, dtype=np.uint8)
    a[:20, :] = DEBRIS
    b = np.full(SHAPE, WATER, dtype=np.uint8)
    b[:10, :] = DEBRIS
    b[10:20, :] = CLUMP
    assert frame_metrics(a, masks, geom)["coverage"] == frame_metrics(b, masks, geom)["coverage"]


def test_occluded_roi_reports_none_not_zero(masks, geom) -> None:
    """A silent 0.0 reads as 'clean river' and is the worst possible value to log
    during a flood."""
    blank = np.full(SHAPE, BACKGROUND, dtype=np.uint8)
    assert frame_metrics(blank, masks, geom)["coverage"] is None


def test_roi_excludes_pixels_outside_it(geom) -> None:
    # NOTE: cv2.fillPoly treats the polygon boundary as INCLUSIVE, so an ROI whose
    # last vertex is x=50 covers columns 0..50. The debris below starts at x=60 to
    # stay clear of that edge rather than testing the boundary convention itself.
    m_local = build_masks({"roi": [[0, 0], [50, 0], [50, 100], [0, 100]]}, SHAPE)
    m = np.full(SHAPE, WATER, dtype=np.uint8)
    m[:, 60:] = DEBRIS  # all debris is OUTSIDE the ROI

    r = frame_metrics(m, m_local, geom)
    assert r["debris_px"] == 0
    assert r["coverage"] == 0.0


def test_roi_boundary_is_inclusive() -> None:
    """Pins cv2.fillPoly's convention so a future change to polygon_mask is caught."""
    mask = polygon_mask([[0, 0], [9, 0], [9, 9], [0, 9]], (20, 20))
    assert mask[0, 9], "boundary column must be inside the polygon"
    assert not mask[0, 10]
    assert int(mask.sum()) == 100  # 10x10, not 9x9


def test_structure_polygon_is_clipped_to_roi() -> None:
    m_local = build_masks(
        {
            "roi": [[0, 0], [60, 0], [60, 60], [0, 60]],
            "structure": [[50, 50], [90, 50], [90, 90], [50, 90]],
        },
        SHAPE,
    )
    assert not (m_local.structure & ~m_local.roi).any()


def test_missing_roi_means_whole_frame() -> None:
    assert polygon_mask(None, SHAPE).all()
    assert polygon_mask([], SHAPE).all()


def test_missing_structure_means_no_structure_not_whole_frame(geom) -> None:
    """Regression, caught on a real run: an absent structure polygon fell back to
    the whole-frame default, so accumulation equalled total debris and a site with
    no surveyed pier raised blockage alerts on ordinary passing trash."""
    for cfg in ({"roi": None}, {"roi": None, "structure": None}, {"roi": None, "structure": []}):
        masks = build_masks(cfg, SHAPE)
        assert masks.structure_pixels == 0, cfg
        assert masks.roi.all(), "ROI must still default to the whole frame"

        m = np.full(SHAPE, WATER, dtype=np.uint8)
        m[:40, :] = DEBRIS  # 40% of the frame is debris
        r = frame_metrics(m, masks, geom)
        assert r["accumulation_px"] == 0
        assert r["accumulation_frac"] == 0.0, "no structure must mean no accumulation"

        mon = BlockageMonitor(BlockageParams(area_threshold=0.3, consecutive=1))
        assert not mon.update(r["accumulation_frac"], 0.0)["alert"]


def test_smoother_drops_none_instead_of_treating_it_as_clean() -> None:
    s = Smoother(SmoothingParams(window=5, method="median"))
    for v in (0.4, 0.5, 0.6):
        s.update(v)
    assert s.update(None) == 0.5
    assert s.n == 3


def test_smoother_median_resists_a_single_glare_spike() -> None:
    s = Smoother(SmoothingParams(window=5, method="median"))
    for v in (0.10, 0.11, 0.12, 0.13):
        s.update(v)
    before = s.value
    s.update(0.99)  # one frame of sun glare
    assert abs(s.value - before) < 0.02, "median should barely move on one outlier"


def test_blockage_needs_a_streak_not_one_frame() -> None:
    mon = BlockageMonitor(BlockageParams(area_threshold=0.3, consecutive=3))
    assert not mon.update(0.9, 0.0)["alert"]
    assert not mon.update(0.9, 1.0)["alert"]
    assert mon.update(0.9, 2.0)["alert"]


def test_blockage_streak_resets_on_a_clean_sample() -> None:
    mon = BlockageMonitor(
        BlockageParams(area_threshold=0.3, growth_threshold_per_min=99.0, consecutive=3)
    )
    mon.update(0.9, 0.0)
    mon.update(0.9, 1.0)
    mon.update(0.0, 2.0)  # clean
    assert not mon.update(0.9, 3.0)["alert"], "streak must restart from zero"


def test_growth_alerts_before_the_area_threshold_is_reached() -> None:
    """Rapid accumulation is the early warning; that is the point of the alert."""
    mon = BlockageMonitor(
        BlockageParams(area_threshold=0.99, growth_threshold_per_min=0.1, consecutive=1)
    )
    mon.update(0.00, 0.0)
    out = mon.update(0.25, 60.0)
    assert out["alert"] and "growth" in out["alert_reason"]
    assert out["growth_per_min"] == pytest.approx(0.25, abs=1e-3)


def test_slow_steady_accumulation_does_not_trip_the_growth_rule() -> None:
    mon = BlockageMonitor(
        BlockageParams(area_threshold=0.99, growth_threshold_per_min=0.1, consecutive=1)
    )
    mon.update(0.00, 0.0)
    out = mon.update(0.02, 60.0)  # 0.02/min, well under threshold
    assert not out["alert"]


def test_flux_is_labelled_relative_until_calibrated(geom) -> None:
    f = area_flux(0.2, 100.0, 12.0, geom)
    assert f["area_flux"] == pytest.approx(240.0)
    assert f["flux_units"] == "relative_index", "uncalibrated flux must never claim m2/s"


def test_flux_is_none_when_velocity_is_unknown(geom) -> None:
    assert area_flux(0.2, None, 12.0, geom)["area_flux"] is None
    assert area_flux(None, 100.0, 12.0, geom)["area_flux"] is None


def test_enabling_homography_refuses_rather_than_faking_a_scale() -> None:
    with pytest.raises(NotImplementedError, match="Phase 2"):
        build_geometry({"homography": {"enabled": True}})


def test_default_geometry_is_honest_about_units() -> None:
    g = build_geometry({})
    assert g.is_metric is False
    assert g.units_area == "px2" and g.units_velocity == "px/s"
    assert g.area(500) == 500.0


def test_sink_writes_utc_and_preserves_nulls(tmp_path) -> None:
    with TimeSeriesSink(tmp_path / "s", site="bridge_a") as sink:
        sink.write({"ts_epoch": 1_786_000_000.0, "frame_idx": 0, "coverage": 0.3})
        sink.write({"ts_epoch": 1_786_000_060.0, "frame_idx": 1, "coverage": None})

    conn = sqlite3.connect(tmp_path / "s" / "timeseries.sqlite")
    rows = conn.execute(
        "SELECT ts_utc, site, coverage FROM observations ORDER BY ts_epoch"
    ).fetchall()
    conn.close()

    assert rows[0][0].endswith("Z"), "timestamps must be explicit UTC for the rainfall join"
    assert rows[0][1] == "bridge_a"
    assert rows[1][2] is None, "a missing coverage must stay NULL, not become 0.0"


def test_sink_uses_wal_journal_mode(tmp_path) -> None:
    """The dashboard reads this file while inference writes it.

    In the default rollback-journal mode a reader blocks the writer, which would
    stall the inference loop every time someone opens a page.
    """
    with TimeSeriesSink(tmp_path / "s", site="a") as s:
        mode = s._conn.execute("PRAGMA journal_mode").fetchone()[0]

    assert mode.lower() == "wal", f"expected wal, got {mode!r}"


def test_sink_appends_without_duplicating_the_csv_header(tmp_path) -> None:
    out = tmp_path / "s"
    with TimeSeriesSink(out, site="a") as s:
        s.write({"ts_epoch": 1.0, "coverage": 0.1})
    with TimeSeriesSink(out, site="a") as s:
        s.write({"ts_epoch": 2.0, "coverage": 0.2})

    lines = (out / "timeseries.csv").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 3, lines
    assert lines[0].startswith("ts_utc")
    assert "ts_utc" not in lines[2]
