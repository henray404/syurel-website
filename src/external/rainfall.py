"""Rainfall from public weather APIs, into the same SQLite the dashboard reads.

    python -m external.rainfall --db out/webcam/timeseries.sqlite --days 7

THREE SOURCES, THREE DIFFERENT JOBS. Verified live on 2026-08-23; every claim
below came from an actual HTTP call, not from documentation:

    open-meteo-archive   hourly, mm, 1990 -> yesterday, ~1 day lag, no key
                         -> fills gaps when the tipping bucket is down, and is
                            the independent cross-check that it reads sanely
    open-meteo-forecast  hourly, mm, 7 days ahead, no key
                         -> the denser forecast
    bmkg                 3-hourly, mm, ~3 days ahead, no key, needs an adm4 code
                         -> the official Indonesian source; far easier to defend
                            in a viva than a foreign service

WHAT THIS IS NOT. Open-Meteo is reanalysis on a 9-25 km grid (ERA5 0.25 deg,
ERA5-Land 0.1 deg, ECMWF IFS 9 km). Tropical convective cells are 2-5 km across,
so one storm can soak the barrage while the grid cell reports light rain. These
numbers are a REGIONAL SIGNAL, never "the rainfall at the gate" -- that is what
the tipping bucket is for, and why rencana_penelitian.md section 8 rejects
building a rain model at all.

Consequence for the analysis: tau* (the rain-to-debris lag, section 5.14) must
be computed from the tipping bucket, not from here. Coverage only exists from
the day the camera went up, so a longer external history buys nothing anyway.

ATTRIBUTION IS A CONDITION OF USE, not a courtesy: BMKG requires their name to
be displayed in any application showing their data.

No `requests` dependency on purpose -- urllib does this fine, and the base
install stays as small as it is.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

DEFAULT_SITE_JSON = Path(__file__).resolve().parents[2] / "configs" / "site_geometry.json"

OPEN_METEO_ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
OPEN_METEO_FORECAST = "https://api.open-meteo.com/v1/forecast"
BMKG_FORECAST = "https://api.bmkg.go.id/publik/prakiraan-cuaca"

# Short: this whole module is optional data, and nothing should wait on it.
TIMEOUT_S = 20

CREATE_RAINFALL = """
CREATE TABLE IF NOT EXISTS rainfall (
  source        TEXT    NOT NULL,
  ts_utc        TEXT    NOT NULL,
  ts_epoch      INTEGER NOT NULL,
  mm            REAL,
  interval_s    INTEGER NOT NULL,
  kind          TEXT    NOT NULL,
  fetched_epoch REAL    NOT NULL,
  PRIMARY KEY (source, ts_epoch)
)"""


@dataclass
class Reading:
    source: str
    ts_epoch: int
    mm: float | None
    interval_s: int
    kind: str  # "observed" | "forecast"

    @property
    def ts_utc(self) -> str:
        return datetime.fromtimestamp(self.ts_epoch, tz=timezone.utc).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )


def _get_json(url: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
    full = f"{url}?{urllib.parse.urlencode(params)}" if params else url
    req = urllib.request.Request(full, headers={"User-Agent": "syurell/1.0"})
    with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _parse_iso(text: str, tz_offset_s: int = 0) -> int:
    """'2026-08-22T14:00' (or with a Z / offset) -> epoch seconds."""
    dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone(timedelta(seconds=tz_offset_s)))
    return int(dt.timestamp())


def fetch_open_meteo(lat: float, lon: float, *, days_back: int = 7, forecast: bool = False) -> list[Reading]:
    """Hourly precipitation in mm. Archive is reanalysis; forecast is a model."""
    if forecast:
        data = _get_json(
            OPEN_METEO_FORECAST,
            {
                "latitude": lat,
                "longitude": lon,
                "hourly": "precipitation",
                "forecast_days": 7,
                "timezone": "UTC",
            },
        )
        source, kind = "open-meteo-forecast", "forecast"
    else:
        # The archive lags about a day, so asking up to today returns a tail of
        # nulls rather than an error. end_date is yesterday to keep it clean.
        today = datetime.now(timezone.utc).date()
        data = _get_json(
            OPEN_METEO_ARCHIVE,
            {
                "latitude": lat,
                "longitude": lon,
                "start_date": (today - timedelta(days=days_back)).isoformat(),
                "end_date": (today - timedelta(days=1)).isoformat(),
                "hourly": "precipitation",
                "timezone": "UTC",
            },
        )
        source, kind = "open-meteo-archive", "observed"

    hourly = data.get("hourly") or {}
    times = hourly.get("time") or []
    mms = hourly.get("precipitation") or []

    return [
        Reading(source, _parse_iso(t), None if mm is None else float(mm), 3600, kind)
        for t, mm in zip(times, mms)
    ]


def fetch_bmkg(adm4: str) -> list[Reading]:
    """3-hourly forecast for one kelurahan/desa. `tp` is total precipitation, mm."""
    data = _get_json(BMKG_FORECAST, {"adm4": adm4})
    blocks = (data.get("data") or [{}])[0].get("cuaca") or []

    out: list[Reading] = []
    for block in blocks:
        for item in block:
            ts = item.get("utc_datetime") or item.get("datetime")
            if not ts:
                continue
            tp = item.get("tp")
            out.append(
                Reading(
                    source="bmkg",
                    ts_epoch=_parse_iso(str(ts)),
                    mm=None if tp is None else float(tp),
                    interval_s=10800,
                    kind="forecast",
                )
            )
    return out


def store(db_path: Path | str, readings: list[Reading]) -> int:
    """Upsert. Returns rows written.

    REPLACE, not IGNORE, unlike the ESP32 ingest. A forecast for a given hour is
    revised as that hour approaches and the newest one is the one worth keeping,
    whereas a sensor reading for a past instant is a fact that must never be
    overwritten.
    """
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        # The inference loop may be writing observations to this same file.
        conn.execute("PRAGMA busy_timeout=5000")
        conn.execute(CREATE_RAINFALL)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_rain_ts ON rainfall(ts_epoch)")
        now = time.time()
        conn.executemany(
            """INSERT OR REPLACE INTO rainfall
               (source, ts_utc, ts_epoch, mm, interval_s, kind, fetched_epoch)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [(r.source, r.ts_utc, r.ts_epoch, r.mm, r.interval_s, r.kind, now) for r in readings],
        )
        conn.commit()
        return len(readings)
    finally:
        conn.close()


def load_site_coords(
    path: Path | str = DEFAULT_SITE_JSON,
) -> tuple[float | None, float | None, str | None]:
    cfg = json.loads(Path(path).read_text(encoding="utf-8"))
    s = cfg.get("site") or {}
    return s.get("lat"), s.get("lon"), s.get("adm4")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Ambil curah hujan dari API publik.")
    ap.add_argument("--db", required=True, type=Path, help="timeseries.sqlite tujuan")
    ap.add_argument("--lat", type=float, default=None)
    ap.add_argument("--lon", type=float, default=None)
    ap.add_argument("--adm4", default=None, help="kode kelurahan BMKG, mis. 35.15.09.2003")
    ap.add_argument("--days", type=int, default=7, help="seberapa jauh arsip ditarik")
    ap.add_argument("--site", type=Path, default=DEFAULT_SITE_JSON)
    args = ap.parse_args(argv)

    lat, lon, adm4 = load_site_coords(args.site)
    lat = args.lat if args.lat is not None else lat
    lon = args.lon if args.lon is not None else lon
    adm4 = args.adm4 or adm4

    if lat is None or lon is None:
        print(
            "Koordinat lokasi belum diisi.\n"
            f"  Isi site.lat dan site.lon di {args.site}, atau beri --lat/--lon.\n"
            "  Ambil dengan GPS HP saat survei lokasi."
        )
        if not adm4:
            return 2

    total = 0
    jobs: list[tuple[str, Any]] = []
    if lat is not None and lon is not None:
        jobs.append(("open-meteo archive ", lambda: fetch_open_meteo(lat, lon, days_back=args.days)))
        jobs.append(("open-meteo forecast", lambda: fetch_open_meteo(lat, lon, forecast=True)))
    if adm4:
        jobs.append(("bmkg forecast      ", lambda: fetch_bmkg(adm4)))
    else:
        print("bmkg forecast      : dilewati (site.adm4 belum diisi)")

    for label, fn in jobs:
        try:
            rows = fn()
            n = store(args.db, rows)
            print(f"{label}: {n:4d} titik disimpan ({sum(1 for r in rows if r.mm)} berhujan)")
            total += n
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as err:
            # Never fatal. The tipping bucket is the primary source; a dashboard
            # that dies without internet is worse than one missing a comparison.
            print(f"{label}: GAGAL ({err}) -- dilewati")
        except (KeyError, ValueError, json.JSONDecodeError) as err:
            print(f"{label}: bentuk balasan tak dikenali ({err}) -- dilewati")

    print(f"total {total} titik di {args.db}")
    return 0


def demo() -> None:
    """Self-check, offline: python -c 'from external.rainfall import demo; demo()'"""
    import tempfile

    rs = [
        Reading("open-meteo-archive", 1787407200, 2.5, 3600, "observed"),
        Reading("bmkg", 1787551200, 0.0, 10800, "forecast"),
    ]
    assert rs[0].ts_utc == "2026-08-22T14:00:00Z", rs[0].ts_utc
    assert _parse_iso("2026-08-22T14:00") == 1787407200
    assert _parse_iso("2026-08-22T14:00:00Z") == 1787407200

    with tempfile.TemporaryDirectory() as td:
        db = Path(td) / "t.sqlite"
        assert store(db, rs) == 2
        # A revised forecast for the same hour must replace, not duplicate.
        store(db, [Reading("bmkg", 1787551200, 4.2, 10800, "forecast")])
        conn = sqlite3.connect(str(db))
        n = conn.execute("SELECT COUNT(*) FROM rainfall").fetchone()[0]
        mm = conn.execute("SELECT mm FROM rainfall WHERE source='bmkg'").fetchone()[0]
        conn.close()
        assert n == 2, n
        assert mm == 4.2, mm

    print("rainfall ok")


if __name__ == "__main__":
    raise SystemExit(main())
