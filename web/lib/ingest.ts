import type Database from "better-sqlite3";
import type { EspRow } from "./esp-csv";

const INSERT = `
INSERT OR IGNORE INTO esp_readings (
  device, ts_utc, ts_epoch, jarak_cm, tinggi_cm, valid, n_sampel,
  tip_total, tip_menit, mm_per_jam, level, pompa, time_src, rssi, sms_status
) VALUES (
  @device, @ts_utc, @ts_epoch, @jarak_cm, @tinggi_cm, @valid, @n_sampel,
  @tip_total, @tip_menit, @mm_per_jam, @level, @pompa, @time_src, @rssi, @sms_status
)`;

/**
 * Insert a batch in one transaction.
 *
 * OR IGNORE plus the composite primary key makes re-delivery a no-op, which
 * matters because the firmware re-sends whenever a response goes missing.
 * Returns the number of rows that were new.
 */
export function insertBatch(
  db: Database.Database,
  device: string,
  rows: EspRow[],
): number {
  const stmt = db.prepare(INSERT);
  const run = db.transaction((batch: EspRow[]) => {
    let inserted = 0;
    for (const row of batch) {
      inserted += stmt.run({ device, ...row }).changes;
    }
    return inserted;
  });
  return run(rows);
}
