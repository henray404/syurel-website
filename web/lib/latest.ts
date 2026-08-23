import type Database from "better-sqlite3";
import { hasObservations } from "./db";
import type { Observation } from "./join";

export type LatestEsp = {
  ts_utc: string;
  tinggi_cm: number | null;
  mm_per_jam: number | null;
  level: string | null;
};

export type LatestObs = Observation & { ts_utc: string };

export type Latest = { esp: LatestEsp | null; obs: LatestObs | null };

/**
 * Newest row from each side.
 *
 * Missing data is null, never an exception: inference may not have run yet, and
 * a dashboard that crashes because one source is quiet is worse than one that
 * says so.
 */
export function readLatest(db: Database.Database): Latest {
  const esp =
    (db
      .prepare(
        "SELECT ts_utc, tinggi_cm, mm_per_jam, level FROM esp_readings ORDER BY ts_epoch DESC LIMIT 1",
      )
      .get() as LatestEsp | undefined) ?? null;

  let obs: LatestObs | null = null;
  if (hasObservations(db)) {
    obs =
      (db
        .prepare(
          `SELECT ts_utc, ts_epoch, coverage, accumulation_frac, growth_per_min, alert, alert_reason
           FROM observations ORDER BY ts_epoch DESC LIMIT 1`,
        )
        .get() as LatestObs | undefined) ?? null;
  }

  return { esp, obs };
}
