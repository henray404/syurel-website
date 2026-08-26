import { describe, it, expect, afterEach } from "vitest";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import type BetterSqlite3 from "better-sqlite3";
import { openDb } from "../lib/db";

// Windows refuses to remove a directory while a file in it is still open, so the
// handle has to be closed before the temp dir goes.
let dir: string | null = null;
let db: BetterSqlite3.Database | null = null;

function freshDb(): BetterSqlite3.Database {
  dir = mkdtempSync(join(tmpdir(), "syurell-"));
  db = openDb(join(dir, "t.sqlite"));
  return db;
}

afterEach(() => {
  db?.close();
  db = null;
  if (dir) rmSync(dir, { recursive: true, force: true });
  dir = null;
});

describe("openDb", () => {
  it("creates esp_readings and turns on WAL", () => {
    const d = freshDb();

    const mode = d.pragma("journal_mode", { simple: true });
    expect(String(mode).toLowerCase()).toBe("wal");

    const table = d
      .prepare("SELECT name FROM sqlite_master WHERE type='table' AND name='esp_readings'")
      .get();
    expect(table).toBeTruthy();
  });

  it("waits for a busy writer instead of failing the ingest", () => {
    // Regression: the inference loop writes ~25 rows/s, so an ingest POST that
    // arrived between two of them got "database is locked" and a 503. The
    // firmware retried the same batch forever and nothing was ever stored.
    const d = freshDb();
    const timeout = d.pragma("busy_timeout", { simple: true });
    expect(Number(timeout)).toBeGreaterThanOrEqual(1000);
  });

  it("rejects a second row with the same (device, ts_epoch)", () => {
    const d = freshDb();
    const sql = "INSERT OR IGNORE INTO esp_readings (device, ts_utc, ts_epoch) VALUES (?, ?, ?)";

    d.prepare(sql).run("esp32-01", "2026-08-20T10:30:00Z", 1787654321);
    d.prepare(sql).run("esp32-01", "2026-08-20T10:30:00Z", 1787654321);

    const { n } = d.prepare("SELECT COUNT(*) AS n FROM esp_readings").get() as { n: number };
    expect(n).toBe(1);
  });
});
