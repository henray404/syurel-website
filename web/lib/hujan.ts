import type Database from "better-sqlite3";

/**
 * Rainfall from the external APIs, as stored by src/external/rainfall.py.
 *
 * READ THIS BEFORE PUTTING A NUMBER FROM HERE NEXT TO A SENSOR NUMBER.
 * Open-Meteo is reanalysis on a 9-25 km grid; tropical convective cells are
 * 2-5 km across. One storm can soak the barrage while the grid cell reports
 * light rain. These are a REGIONAL signal and the UI must always label them as
 * such -- the tipping bucket on the ESP32 is the only rainfall actually
 * measured at the gate.
 */
export type RainSource = "open-meteo-archive" | "open-meteo-forecast" | "bmkg";

export type RainPoint = {
  ts_utc: string;
  ts_epoch: number;
  mm: number | null;
  interval_s: number;
  kind: "observed" | "forecast";
};

export type RainSummary = {
  available: boolean;
  /** Total mm over the last 24 h from the archive (reanalysis, not the sensor). */
  mm24h: number | null;
  /** Total mm forecast for the next 24 h. */
  mmNext24h: number | null;
  /** Which source the forecast came from, so the UI can attribute it. */
  forecastSource: RainSource | null;
  /** Next forecast point carrying rain, for "hujan diperkirakan ...". */
  nextRainTs: string | null;
  nextRainMm: number | null;
  series: RainPoint[];
};

export const EMPTY_RAIN: RainSummary = {
  available: false,
  mm24h: null,
  mmNext24h: null,
  forecastSource: null,
  nextRainTs: null,
  nextRainMm: null,
  series: [],
};

export function hasRainfall(db: Database.Database): boolean {
  const row = db
    .prepare("SELECT name FROM sqlite_master WHERE type='table' AND name='rainfall'")
    .get();
  return row !== undefined;
}

function sumWindow(
  db: Database.Database,
  source: string,
  fromEpoch: number,
  toEpoch: number,
): number | null {
  const row = db
    .prepare(
      `SELECT SUM(mm) AS total, COUNT(mm) AS n FROM rainfall
       WHERE source = ? AND ts_epoch >= ? AND ts_epoch < ?`,
    )
    .get(source, fromEpoch, toEpoch) as { total: number | null; n: number };
  // No rows at all is "not measured", not "no rain". A window with no data and
  // a genuinely dry day must never render as the same 0 mm.
  return row.n === 0 ? null : (row.total ?? 0);
}

export function readRainfall(db: Database.Database, now: Date = new Date()): RainSummary {
  if (!hasRainfall(db)) return EMPTY_RAIN;

  const nowEpoch = Math.floor(now.getTime() / 1000);
  const dayS = 86400;

  const mm24h = sumWindow(db, "open-meteo-archive", nowEpoch - dayS, nowEpoch);

  // BMKG first: the official Indonesian source, far easier to defend in a viva
  // than a foreign service. Open-Meteo is the fallback and is denser (hourly
  // against 3-hourly).
  let forecastSource: RainSource | null = null;
  let mmNext24h: number | null = null;
  for (const src of ["bmkg", "open-meteo-forecast"] as RainSource[]) {
    const total = sumWindow(db, src, nowEpoch, nowEpoch + dayS);
    if (total !== null) {
      forecastSource = src;
      mmNext24h = total;
      break;
    }
  }

  const next = forecastSource
    ? (db
        .prepare(
          `SELECT ts_utc, mm FROM rainfall
           WHERE source = ? AND ts_epoch >= ? AND mm > 0
           ORDER BY ts_epoch ASC LIMIT 1`,
        )
        .get(forecastSource, nowEpoch) as { ts_utc: string; mm: number } | undefined)
    : undefined;

  const series = db
    .prepare(
      `SELECT ts_utc, ts_epoch, mm, interval_s, kind FROM rainfall
       WHERE ts_epoch >= ? AND ts_epoch <= ?
       ORDER BY ts_epoch ASC`,
    )
    .all(nowEpoch - dayS, nowEpoch + dayS) as RainPoint[];

  return {
    available: true,
    mm24h,
    mmNext24h,
    forecastSource,
    nextRainTs: next?.ts_utc ?? null,
    nextRainMm: next?.mm ?? null,
    series,
  };
}

/** Human label for a source, including the attribution BMKG requires. */
export function sourceLabel(source: RainSource | null): string {
  switch (source) {
    case "bmkg":
      return "BMKG";
    case "open-meteo-forecast":
      return "Open-Meteo (prakiraan)";
    case "open-meteo-archive":
      return "Open-Meteo (arsip ERA5)";
    default:
      return "tidak ada";
  }
}
