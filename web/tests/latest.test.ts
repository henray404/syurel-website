import { describe, it, expect, afterEach } from "vitest";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import type BetterSqlite3 from "better-sqlite3";
import { openDb } from "../lib/db";
import { readLatest } from "../lib/latest";

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

describe("readLatest", () => {
  it("returns nulls on an empty database instead of throwing", () => {
    const out = readLatest(freshDb());
    expect(out.esp).toBeNull();
    expect(out.obs).toBeNull();
  });

  it("returns the newest ESP row", () => {
    const d = freshDb();
    const sql =
      "INSERT INTO esp_readings (device, ts_utc, ts_epoch, tinggi_cm) VALUES (?, ?, ?, ?)";
    d.prepare(sql).run("esp32-01", "2026-08-20T10:30:00Z", 1787654321, 154.8);
    d.prepare(sql).run("esp32-01", "2026-08-20T10:31:00Z", 1787654381, 155.9);

    expect(readLatest(d).esp!.tinggi_cm).toBeCloseTo(155.9);
  });

  it("survives a database with no observations table", () => {
    // Inference may not have run yet. That is not an error.
    expect(readLatest(freshDb()).obs).toBeNull();
  });

  it("returns the newest observation when the table exists", () => {
    const d = freshDb();
    d.exec(
      "CREATE TABLE observations (ts_utc TEXT, ts_epoch INTEGER, coverage REAL, accumulation_frac REAL, growth_per_min REAL, alert INTEGER, alert_reason TEXT)",
    );
    const sql =
      "INSERT INTO observations (ts_utc, ts_epoch, coverage, accumulation_frac, growth_per_min, alert, alert_reason) VALUES (?, ?, ?, ?, ?, ?, ?)";
    d.prepare(sql).run("2026-08-20T10:30:00Z", 1787654321, 0.12, 0.05, 0, 0, "");
    d.prepare(sql).run("2026-08-20T10:30:30Z", 1787654351, null, 0.07, 0.01, 0, "");

    const out = readLatest(d);
    expect(out.obs!.ts_epoch).toBe(1787654351);
    expect(out.obs!.coverage).toBeNull();
  });
});
