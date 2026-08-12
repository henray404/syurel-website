"""Time-series output, structured for joining against rainfall.

Rainfall data arrives as hourly or 10-minute totals keyed by UTC timestamp. To
join against it without pain later, every row carries:

  * `ts_utc`   ISO-8601 with an explicit Z. Not local time -- Asia/Jakarta is
                UTC+7 with no DST, which makes local timestamps look harmless
                right up until they are joined against a UTC rainfall series and
                every correlation is silently shifted seven hours.
  * `ts_epoch` float seconds, for resampling without re-parsing strings.
  * `site`     so several units can write into one database later.

Both sinks can run at once. CSV is for eyeballing and for pandas; SQLite is for
the resampling and joins the rainfall analysis will actually want.
"""

from __future__ import annotations

import csv
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Order matters: it is the CSV column order and the SQLite column order.
COLUMNS: list[tuple[str, str]] = [
    ("ts_utc", "TEXT"),
    ("ts_epoch", "REAL"),
    ("site", "TEXT"),
    ("frame_idx", "INTEGER"),
    ("coverage", "REAL"),
    ("coverage_smoothed", "REAL"),
    ("debris_px", "INTEGER"),
    ("water_px", "INTEGER"),
    ("roi_px", "INTEGER"),
    ("accumulation_px", "INTEGER"),
    ("accumulation_frac", "REAL"),
    ("velocity_px_s", "REAL"),
    ("n_flow_vectors", "INTEGER"),
    ("area_flux", "REAL"),
    ("flux_units", "TEXT"),
    ("is_metric", "INTEGER"),
    ("growth_per_min", "REAL"),
    ("alert", "INTEGER"),
    ("alert_reason", "TEXT"),
    ("water_mask_age_s", "REAL"),
]
FIELDS = [c for c, _ in COLUMNS]


def utc_iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class TimeSeriesSink:
    out_dir: Path
    site: str
    csv_enabled: bool = True
    sqlite_enabled: bool = True

    def __post_init__(self) -> None:
        self.out_dir = Path(self.out_dir)
        self.out_dir.mkdir(parents=True, exist_ok=True)
        self._csv_path = self.out_dir / "timeseries.csv"
        self._db_path = self.out_dir / "timeseries.sqlite"
        self._conn: sqlite3.Connection | None = None

        if self.csv_enabled and not self._csv_path.exists():
            with self._csv_path.open("w", encoding="utf-8", newline="") as fh:
                csv.writer(fh).writerow(FIELDS)

        if self.sqlite_enabled:
            self._conn = sqlite3.connect(self._db_path)
            cols = ", ".join(f"{name} {typ}" for name, typ in COLUMNS)
            self._conn.execute(f"CREATE TABLE IF NOT EXISTS observations ({cols})")
            # The rainfall join is by time, and a dashboard reads recent rows per
            # site. Both are index scans, and both are slow without this.
            self._conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_obs_site_ts ON observations(site, ts_epoch)"
            )
            self._conn.commit()

    def write(self, row: dict[str, Any]) -> None:
        record = {k: row.get(k) for k in FIELDS}
        record["site"] = self.site
        if record.get("ts_epoch") is not None and not record.get("ts_utc"):
            record["ts_utc"] = utc_iso(float(record["ts_epoch"]))
        for key in ("alert", "is_metric"):
            if record.get(key) is not None:
                record[key] = int(bool(record[key]))

        if self.csv_enabled:
            with self._csv_path.open("a", encoding="utf-8", newline="") as fh:
                csv.DictWriter(fh, fieldnames=FIELDS, extrasaction="ignore").writerow(record)

        if self._conn is not None:
            placeholders = ", ".join("?" for _ in FIELDS)
            self._conn.execute(
                f"INSERT INTO observations ({', '.join(FIELDS)}) VALUES ({placeholders})",
                [record[k] for k in FIELDS],
            )

    def flush(self) -> None:
        if self._conn is not None:
            self._conn.commit()

    def close(self) -> None:
        self.flush()
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> "TimeSeriesSink":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def demo() -> None:
    """Self-check: python -m inference.sink"""
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "site1"
        with TimeSeriesSink(out, site="bridge_a") as sink:
            sink.write(
                {
                    "ts_epoch": 1_786_000_000.0,
                    "frame_idx": 0,
                    "coverage": 0.21,
                    "coverage_smoothed": 0.19,
                    "debris_px": 210,
                    "water_px": 790,
                    "alert": False,
                    "is_metric": False,
                    "flux_units": "relative_index",
                }
            )
            sink.write({"ts_epoch": 1_786_000_060.0, "frame_idx": 1, "coverage": None})
            sink.flush()

            conn = sqlite3.connect(out / "timeseries.sqlite")
            rows = conn.execute(
                "SELECT ts_utc, site, coverage, alert FROM observations ORDER BY ts_epoch"
            ).fetchall()
            conn.close()

        assert len(rows) == 2, rows
        assert rows[0][1] == "bridge_a"
        assert rows[0][0].endswith("Z"), f"timestamp must be explicit UTC: {rows[0][0]}"
        assert rows[0][2] == 0.21
        assert rows[0][3] == 0  # bool -> int
        # A missing coverage must land as NULL, never as 0.0.
        assert rows[1][2] is None, rows[1]

        text = (out / "timeseries.csv").read_text(encoding="utf-8").splitlines()
        assert text[0].split(",")[0] == "ts_utc"
        assert len(text) == 3  # header + 2 rows

    print("sink self-check OK")


if __name__ == "__main__":
    demo()
