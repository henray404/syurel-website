"""Afflux, and the external rainfall sources.

The failure mode that matters here is a confident number built on a guess. The
site geometry is uncalibrated by default, and every path that could turn a
missing measurement into "the gate is clear" is asserted against.
"""

from __future__ import annotations

import json
import math
import sqlite3

import pytest

from external.rainfall import Reading, _parse_iso, store
from physics import (
    BF_MAX_TRUSTED,
    Gate,
    Site,
    afflux_ratio,
    blockage_factor,
    critical_bf,
    load_site,
    summary,
)

# Mirrors SITE in web/tests/fisika.test.ts. Same numbers, both languages.
GATE = Gate(b_m=2.0, a_m=1.0, Cd=0.61, h_bersih_m=0.8, z_jalan_m=1.6)
SITE = Site(gate=GATE, bias=0.0, skala=1.0, calibrated=False, lat=None, lon=None, adm4=None)


def test_afflux_matches_the_web_contract() -> None:
    """Same cases as web/tests/fisika.test.ts. Change one, change the other."""
    assert afflux_ratio(0.0) == 1.0
    assert afflux_ratio(0.5) == pytest.approx(4.0)
    assert afflux_ratio(0.9) is None
    assert afflux_ratio(BF_MAX_TRUSTED) is None


def test_a_missing_measurement_never_becomes_a_clear_gate() -> None:
    """0.0 would read as "no blockage", which is the dangerous direction."""
    assert blockage_factor(None, SITE) is None
    assert blockage_factor(float("nan"), SITE) is None
    assert summary(None, SITE)["afflux_m"] is None


def test_calibration_from_experiment_e2_is_applied() -> None:
    biased = Site(gate=GATE, bias=0.02, skala=1.3, calibrated=True, lat=None, lon=None, adm4=None)
    assert blockage_factor(0.24, biased) == pytest.approx(0.332)


def test_critical_bf_predicts_the_road_flooding() -> None:
    """The number worth stating out loud before a demonstration."""
    bfc = critical_bf(SITE)
    assert bfc == pytest.approx(1 - math.sqrt(0.5))

    s = summary(bfc, SITE)
    assert s["head_m"] == pytest.approx(GATE.z_jalan_m)
    assert s["margin_to_road_m"] == pytest.approx(0.0, abs=1e-9)


def test_critical_bf_is_none_when_the_road_is_below_the_clear_level() -> None:
    low = Site(
        gate=Gate(b_m=2.0, a_m=1.0, Cd=0.61, h_bersih_m=0.8, z_jalan_m=0.8),
        bias=0.0,
        skala=1.0,
        calibrated=False,
        lat=None,
        lon=None,
        adm4=None,
    )
    assert critical_bf(low) is None


def test_summary_reports_capacity_lost_at_an_unchanged_level() -> None:
    """Not the discharge at the afflux head -- that equals the clear discharge.

    Q = Cd*A0(1-BF)*sqrt(2g*h0/(1-BF)^2) = Cd*A0*sqrt(2g*h0) = Q0, exactly. The
    head rises by the amount needed for the same flow to still get through,
    which is what afflux IS. Printing it as a second column would show one
    number twice.
    """
    s = summary(0.5, SITE)
    assert s["discharge_tersumbat_m3s"] < s["discharge_bersih_m3s"]
    assert s["discharge_tersumbat_m3s"] / s["discharge_bersih_m3s"] == pytest.approx(0.5)


def test_site_json_is_uncalibrated_unless_it_says_otherwise(tmp_path) -> None:
    """A missing status must not silently promote guesses to measurements."""
    p = tmp_path / "site.json"
    body = {
        "gate": {"b_m": 2.0, "a_m": 1.0, "Cd": 0.61, "h_bersih_m": 0.8, "z_jalan_m": 1.6},
        "kalibrasi_kamera": {"bias": 0.0, "skala": 1.0},
    }
    p.write_text(json.dumps(body), encoding="utf-8")
    assert load_site(p).calibrated is False

    p.write_text(json.dumps({**body, "status": "CALIBRATED"}), encoding="utf-8")
    assert load_site(p).calibrated is True


def test_the_shipped_site_config_is_still_marked_uncalibrated() -> None:
    """Nothing has been surveyed yet. If this fails, check it was deliberate."""
    assert load_site().calibrated is False


def test_rainfall_timestamps_use_the_projects_one_format() -> None:
    r = Reading("open-meteo-archive", 1787407200, 2.5, 3600, "observed")
    assert r.ts_utc == "2026-08-22T14:00:00Z"
    # Open-Meteo sends naive local time; BMKG sends a trailing Z. Both must land
    # on the same instant, or the two sources would plot hours apart.
    assert _parse_iso("2026-08-22T14:00") == 1787407200
    assert _parse_iso("2026-08-22T14:00:00Z") == 1787407200


def test_a_revised_forecast_replaces_rather_than_duplicates(tmp_path) -> None:
    """Unlike a sensor row, a forecast for a given hour is revised as it nears."""
    db = tmp_path / "t.sqlite"
    store(db, [Reading("bmkg", 1787551200, 0.0, 10800, "forecast")])
    store(db, [Reading("bmkg", 1787551200, 4.2, 10800, "forecast")])

    conn = sqlite3.connect(str(db))
    rows = conn.execute("SELECT mm FROM rainfall WHERE source='bmkg'").fetchall()
    conn.close()
    assert rows == [(4.2,)]
