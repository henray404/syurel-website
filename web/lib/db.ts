import Database from "better-sqlite3";
import { resolve } from "node:path";

/**
 * The default must name the same site as LIVE_DIR in lib/live.ts.
 *
 * It used to default to ../out/timeseries.sqlite while LIVE_DIR defaulted to
 * ../out/webcam/live, so a dev server started without SYURELL_DB showed a live
 * camera feed above numbers read from a database file that did not exist:
 * pictures moving, every reading "tidak terukur". run.py writes both under
 * out/<site>/, so the two defaults have to agree on <site>.
 */
export const DB_PATH = resolve(
  process.cwd(),
  process.env.SYURELL_DB ?? "../out/webcam/timeseries.sqlite",
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
  // WAL lets a reader and a writer coexist, but still allows only ONE writer.
  // The inference loop writes a row per frame -- measured at 25/s on the webcam
  // config -- so an ingest POST landing between two of them found the file
  // locked and returned 503 "database is locked" straight away. The ESP32 then
  // retried the same batch forever and no reading was ever stored.
  //
  // Waiting is the right answer, not failing: the writer holds the lock for far
  // under a millisecond, and 5 s is longer than any real contention while still
  // bounded, so a genuinely stuck writer still surfaces as an error the
  // firmware can retry rather than as a hung request.
  db.pragma("busy_timeout = 5000");
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
