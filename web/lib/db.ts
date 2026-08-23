import Database from "better-sqlite3";
import { resolve } from "node:path";

export const DB_PATH = resolve(
  process.cwd(),
  process.env.SYURELL_DB ?? "../out/timeseries.sqlite",
);

const CREATE_ESP_READINGS = `
CREATE TABLE IF NOT EXISTS esp_readings (
  device      TEXT    NOT NULL,
  ts_utc      TEXT    NOT NULL,
  ts_epoch    INTEGER NOT NULL,
  jarak_cm    REAL,
  tinggi_cm   REAL,
  valid       INTEGER,
  n_sampel    INTEGER,
  tip_total   INTEGER,
  tip_menit   INTEGER,
  mm_per_jam  REAL,
  level       TEXT,
  pompa       INTEGER,
  time_src    TEXT,
  rssi        INTEGER,
  sms_status  TEXT,
  PRIMARY KEY (device, ts_epoch)
)`;

/**
 * Open a database and make sure our table exists.
 *
 * Exported separately from getDb so tests can point at a temp file. The
 * inference side owns `observations`; we only ever read that one.
 */
export function openDb(path: string): Database.Database {
  const db = new Database(path);
  db.pragma("journal_mode = WAL");
  db.exec(CREATE_ESP_READINGS);
  db.exec("CREATE INDEX IF NOT EXISTS idx_esp_ts ON esp_readings(ts_epoch)");
  return db;
}

let singleton: Database.Database | null = null;

/** Process-wide handle. Next.js reuses the module across requests. */
export function getDb(): Database.Database {
  if (singleton === null) singleton = openDb(DB_PATH);
  return singleton;
}

/** True when the inference side has created its table. */
export function hasObservations(db: Database.Database): boolean {
  const row = db
    .prepare("SELECT name FROM sqlite_master WHERE type='table' AND name='observations'")
    .get();
  return row !== undefined;
}
