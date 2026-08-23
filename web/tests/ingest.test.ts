import { describe, it, expect, afterEach } from "vitest";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import type BetterSqlite3 from "better-sqlite3";
import { openDb } from "../lib/db";
import { insertBatch } from "../lib/ingest";
import { parseEspCsv } from "../lib/esp-csv";

const A = "2026-08-20T10:30:00Z,1787654321,45.2,154.8,1,12,340,2,4.8,NORMAL,0,ntp,-67,ok";
const B = "2026-08-20T10:31:00Z,1787654381,45.0,155.0,1,12,341,1,2.4,NORMAL,0,ntp,-65,ok";

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

function count(d: BetterSqlite3.Database): number {
  return (d.prepare("SELECT COUNT(*) AS n FROM esp_readings").get() as { n: number }).n;
}

describe("insertBatch", () => {
  it("inserts every row once", () => {
    const d = freshDb();
    const rows = [A, B].map((l) => parseEspCsv(l)!);
    expect(insertBatch(d, "esp32-01", rows)).toBe(2);
    expect(count(d)).toBe(2);
  });

  it("is idempotent — re-delivery adds nothing", () => {
    const d = freshDb();
    const rows = [A, B].map((l) => parseEspCsv(l)!);
    insertBatch(d, "esp32-01", rows);
    insertBatch(d, "esp32-01", rows);
    expect(count(d)).toBe(2);
  });

  it("keeps rows from different devices apart", () => {
    const d = freshDb();
    const rows = [parseEspCsv(A)!];
    insertBatch(d, "esp32-01", rows);
    insertBatch(d, "esp32-02", rows);
    expect(count(d)).toBe(2);
  });

  it("stores a null numeric as NULL, not 0", () => {
    const d = freshDb();
    const gap = "2026-08-20T10:30:00Z,1787654321,,154.8,1,12,340,2,4.8,NORMAL,0,ntp,-67,ok";
    insertBatch(d, "esp32-01", [parseEspCsv(gap)!]);

    const row = d.prepare("SELECT jarak_cm FROM esp_readings").get() as { jarak_cm: number | null };
    expect(row.jarak_cm).toBeNull();
  });

  it("writes nothing when the surrounding transaction fails", () => {
    const d = freshDb();
    // A batch is all-or-nothing: the transaction must roll back.
    expect(() =>
      d.transaction(() => {
        insertBatch(d, "esp32-01", [parseEspCsv(A)!]);
        throw new Error("boom");
      })(),
    ).toThrow();

    expect(count(d)).toBe(0);
  });
});
