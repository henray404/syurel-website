# Web Monitoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the ingest endpoint the ESP32 firmware is already waiting for, store its rows alongside the camera's, and show the operator the current state of the barrage.

**Architecture:** Next.js owns the whole web tier — an `/api/ingest` route receives ESP32 batches and writes `esp_readings`, other routes read both that table and the `observations` table Python already writes. Both live in one SQLite file, opened in WAL mode so Node reads never block Python writes. Pure logic (CSV parsing, time join, operator verdict) sits in `web/lib/` as framework-free functions so it can be unit-tested without rendering anything.

**Tech Stack:** Next.js 15 (App Router) · TypeScript · better-sqlite3 · vitest · Python 3.13 (existing inference side)

**Spec:** [`docs/superpowers/specs/2026-08-20-monitoring-web-design.md`](../specs/2026-08-20-monitoring-web-design.md)

## Global Constraints

- **Reply 2xx from `/api/ingest` only when every row in the batch is stored.** A 2xx makes the ESP32 advance its SD cursor and those rows are never re-sent. Any failure must return non-2xx.
- **Ingest must be idempotent.** Re-delivery is normal. `esp_readings` has `PRIMARY KEY (device, ts_epoch)` and inserts use `INSERT OR IGNORE`.
- **A malformed row rejects the whole batch.** Partial-accept plus 2xx loses the failed rows permanently.
- **`coverage` of `null` renders as "tidak terukur", never `0`.** `src/inference/metrics.py` deliberately returns `None` rather than `0.0` because `0.0` reads as "clean river" — the exact wrong thing during a flood.
- **Next.js never writes `observations`.** That table belongs to Python.
- **All timestamps are ISO-8601 UTC** (`ts_utc`) plus Unix seconds (`ts_epoch`). Asia/Jakarta is UTC+7; local time would silently shift the rainfall correlation by seven hours.
- **The web app lives in `web/`** at the repo root, beside `src/`. The SQLite file it reads is `out/timeseries.sqlite`, i.e. `../out/timeseries.sqlite` relative to `web/`.
- **Server runs on port 8000**, matching the `INGEST_URL` example in `firmware/esp32/include/config_secrets.h.example`.

---

### Task 1: Enable WAL on the Python sink

Node cannot read the SQLite file while Python holds a write lock in the default rollback-journal mode. This one pragma is the only change to already-running Python code.

**Files:**
- Modify: `src/inference/sink.py:75`
- Test: `tests/test_inference.py`

**Interfaces:**
- Consumes: nothing
- Produces: `out/timeseries.sqlite` opened in WAL mode — every later task depends on this to read while inference writes

- [ ] **Step 1: Write the failing test**

Append to `tests/test_inference.py`:

```python
def test_sink_uses_wal_journal_mode(tmp_path):
    """Node reads the same file while Python writes; only WAL allows that."""
    from inference.sink import TimeSeriesSink

    sink = TimeSeriesSink(out_dir=tmp_path, site="test")
    mode = sink._conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal", f"expected wal, got {mode}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=src ./.venv/Scripts/python.exe -m pytest tests/test_inference.py::test_sink_uses_wal_journal_mode -v`

Expected: FAIL — `assert 'delete' == 'wal'`

- [ ] **Step 3: Add the pragma**

In `src/inference/sink.py`, immediately after `self._conn = sqlite3.connect(self._db_path)`:

```python
            self._conn = sqlite3.connect(self._db_path)
            # WAL lets the Next.js dashboard read while inference writes. In the
            # default rollback-journal mode a reader blocks the writer, which
            # would stall the inference loop every time someone opens a page.
            self._conn.execute("PRAGMA journal_mode=WAL")
```

- [ ] **Step 4: Run the whole inference test file**

Run: `PYTHONPATH=src ./.venv/Scripts/python.exe -m pytest tests/test_inference.py -v`

Expected: PASS, including the pre-existing tests — the pragma must not change any recorded behaviour.

- [ ] **Step 5: Commit**

```bash
git add src/inference/sink.py tests/test_inference.py
git commit -m "feat(sink): open the timeseries db in WAL mode

The dashboard reads this file while inference writes it. Rollback-journal
mode makes a reader block the writer, which would stall the inference loop
whenever a page is open."
```

---

### Task 2: Scaffold the Next.js app and the database module

**Files:**
- Create: `web/package.json`
- Create: `web/tsconfig.json`
- Create: `web/next.config.mjs`
- Create: `web/vitest.config.ts`
- Create: `web/.gitignore`
- Create: `web/lib/db.ts`
- Test: `web/tests/db.test.ts`

**Interfaces:**
- Consumes: the WAL-mode database from Task 1
- Produces:
  - `openDb(path: string): Database.Database` — opens a database, sets WAL, creates `esp_readings` if missing
  - `getDb(): Database.Database` — process-wide singleton over `DB_PATH`
  - `hasObservations(db: Database.Database): boolean`
  - `DB_PATH: string` — `process.env.SYURELL_DB ?? '../out/timeseries.sqlite'`, resolved

- [ ] **Step 1: Create the project files**

`web/package.json`:

```json
{
  "name": "syurell-web",
  "private": true,
  "scripts": {
    "dev": "next dev -p 8000",
    "build": "next build",
    "start": "next start -p 8000",
    "test": "vitest run"
  },
  "dependencies": {
    "better-sqlite3": "^11.7.0",
    "next": "^15.1.0",
    "react": "^19.0.0",
    "react-dom": "^19.0.0"
  },
  "devDependencies": {
    "@types/better-sqlite3": "^7.6.12",
    "@types/node": "^22.10.0",
    "@types/react": "^19.0.0",
    "typescript": "^5.7.0",
    "vitest": "^2.1.0"
  }
}
```

`web/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["dom", "dom.iterable", "ES2022"],
    "allowJs": false,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

`web/next.config.mjs`:

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  // better-sqlite3 is a native module; it must stay external to the server
  // bundle or Next tries to trace and rewrite the .node binary and fails.
  serverExternalPackages: ["better-sqlite3"],
};

export default nextConfig;
```

`web/vitest.config.ts`:

```typescript
import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "node",
    include: ["tests/**/*.test.ts"],
  },
});
```

`web/.gitignore`:

```
node_modules/
.next/
next-env.d.ts
*.tsbuildinfo
```

- [ ] **Step 2: Install dependencies**

Run: `cd web && npm install`

Expected: completes, `web/node_modules/` exists. `better-sqlite3` compiles a native binary — on Windows this needs build tools; if it fails, run `npm install --build-from-source` and report the error rather than switching libraries.

- [ ] **Step 3: Write the failing test**

`web/tests/db.test.ts`:

```typescript
import { describe, it, expect, afterEach } from "vitest";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { openDb } from "../lib/db";

let dir: string | null = null;

afterEach(() => {
  if (dir) rmSync(dir, { recursive: true, force: true });
  dir = null;
});

describe("openDb", () => {
  it("creates esp_readings and turns on WAL", () => {
    dir = mkdtempSync(join(tmpdir(), "syurell-"));
    const db = openDb(join(dir, "t.sqlite"));

    const mode = db.pragma("journal_mode", { simple: true });
    expect(String(mode).toLowerCase()).toBe("wal");

    const table = db
      .prepare("SELECT name FROM sqlite_master WHERE type='table' AND name='esp_readings'")
      .get();
    expect(table).toBeTruthy();
  });

  it("rejects a second row with the same (device, ts_epoch)", () => {
    dir = mkdtempSync(join(tmpdir(), "syurell-"));
    const db = openDb(join(dir, "t.sqlite"));
    const sql = "INSERT OR IGNORE INTO esp_readings (device, ts_utc, ts_epoch) VALUES (?, ?, ?)";

    db.prepare(sql).run("esp32-01", "2026-08-20T10:30:00Z", 1787654321);
    db.prepare(sql).run("esp32-01", "2026-08-20T10:30:00Z", 1787654321);

    const { n } = db.prepare("SELECT COUNT(*) AS n FROM esp_readings").get() as { n: number };
    expect(n).toBe(1);
  });
});
```

- [ ] **Step 4: Run test to verify it fails**

Run: `cd web && npm test`

Expected: FAIL — cannot resolve `../lib/db`

- [ ] **Step 5: Write the implementation**

`web/lib/db.ts`:

```typescript
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
```

- [ ] **Step 6: Run test to verify it passes**

Run: `cd web && npm test`

Expected: PASS — 2 tests

- [ ] **Step 7: Commit**

```bash
git add web/package.json web/tsconfig.json web/next.config.mjs web/vitest.config.ts web/.gitignore web/lib/db.ts web/tests/db.test.ts web/package-lock.json
git commit -m "feat(web): scaffold Next.js app and the SQLite module

Opens the same database the inference sink writes, in WAL mode, and creates
esp_readings with the composite primary key that makes ESP re-delivery safe."
```

---

### Task 3: Parse an ESP32 CSV row

The firmware sends raw CSV strings inside JSON. This is the only place that knows the column order, so it is the only place that has to change when the firmware's schema does.

**Files:**
- Create: `web/lib/esp-csv.ts`
- Test: `web/tests/esp-csv.test.ts`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `type EspRow = { ts_utc: string; ts_epoch: number; jarak_cm: number | null; tinggi_cm: number | null; valid: number | null; n_sampel: number | null; tip_total: number | null; tip_menit: number | null; mm_per_jam: number | null; level: string | null; pompa: number | null; time_src: string | null; rssi: number | null; sms_status: string | null }`
  - `parseEspCsv(line: string): EspRow | null` — `null` for a header or blank line (skip, not an error); throws `Error` for a malformed row (reject the batch)
  - `ESP_COLUMNS: readonly string[]`

- [ ] **Step 1: Write the failing test**

`web/tests/esp-csv.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import { parseEspCsv } from "../lib/esp-csv";

const GOOD = "2026-08-20T10:30:00Z,1787654321,45.2,154.8,1,12,340,2,4.8,NORMAL,0,ntp,-67,ok";

describe("parseEspCsv", () => {
  it("parses a real row with the right types", () => {
    const row = parseEspCsv(GOOD);
    expect(row).not.toBeNull();
    expect(row!.ts_utc).toBe("2026-08-20T10:30:00Z");
    expect(row!.ts_epoch).toBe(1787654321);
    expect(row!.jarak_cm).toBeCloseTo(45.2);
    expect(row!.tinggi_cm).toBeCloseTo(154.8);
    expect(row!.valid).toBe(1);
    expect(row!.mm_per_jam).toBeCloseTo(4.8);
    expect(row!.level).toBe("NORMAL");
    expect(row!.rssi).toBe(-67);
    expect(row!.sms_status).toBe("ok");
  });

  it("skips the header line", () => {
    const header =
      "ts_utc,ts_epoch,jarak_cm,tinggi_cm,valid,n_sampel,tip_total,tip_menit,mm_per_jam,level,pompa,time_src,rssi,sms_status";
    expect(parseEspCsv(header)).toBeNull();
  });

  it("skips blank and whitespace-only lines", () => {
    expect(parseEspCsv("")).toBeNull();
    expect(parseEspCsv("   ")).toBeNull();
  });

  it("throws on the wrong number of columns", () => {
    expect(() => parseEspCsv("2026-08-20T10:30:00Z,1787654321,45.2")).toThrow(/14 columns/);
  });

  it("throws when ts_epoch is not a number", () => {
    const bad = GOOD.replace("1787654321", "notanumber");
    expect(() => parseEspCsv(bad)).toThrow(/ts_epoch/);
  });

  it("keeps an empty numeric field as null rather than 0", () => {
    const gap = "2026-08-20T10:30:00Z,1787654321,,154.8,1,12,340,2,4.8,NORMAL,0,ntp,-67,ok";
    expect(parseEspCsv(gap)!.jarak_cm).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npm test`

Expected: FAIL — cannot resolve `../lib/esp-csv`

- [ ] **Step 3: Write the implementation**

`web/lib/esp-csv.ts`:

```typescript
/**
 * Column order from firmware/esp32/include/logic_csv.h. The firmware writes
 * these positionally with snprintf, so order is the contract — not names.
 */
export const ESP_COLUMNS = [
  "ts_utc",
  "ts_epoch",
  "jarak_cm",
  "tinggi_cm",
  "valid",
  "n_sampel",
  "tip_total",
  "tip_menit",
  "mm_per_jam",
  "level",
  "pompa",
  "time_src",
  "rssi",
  "sms_status",
] as const;

export type EspRow = {
  ts_utc: string;
  ts_epoch: number;
  jarak_cm: number | null;
  tinggi_cm: number | null;
  valid: number | null;
  n_sampel: number | null;
  tip_total: number | null;
  tip_menit: number | null;
  mm_per_jam: number | null;
  level: string | null;
  pompa: number | null;
  time_src: string | null;
  rssi: number | null;
  sms_status: string | null;
};

/** Empty stays null. A missing reading is not a reading of zero. */
function num(raw: string, field: string): number | null {
  const s = raw.trim();
  if (s === "") return null;
  const v = Number(s);
  if (!Number.isFinite(v)) throw new Error(`${field}: not a number: ${JSON.stringify(raw)}`);
  return v;
}

function str(raw: string): string | null {
  const s = raw.trim();
  return s === "" ? null : s;
}

/**
 * Parse one CSV line from the ESP32.
 *
 * Returns null for lines to skip (header, blank). Throws for a malformed row —
 * the caller must then reject the whole batch, because replying 2xx would make
 * the firmware drop these rows for good.
 */
export function parseEspCsv(line: string): EspRow | null {
  const trimmed = line.trim();
  if (trimmed === "") return null;
  if (trimmed.startsWith("ts_utc")) return null;

  const parts = trimmed.split(",");
  if (parts.length !== ESP_COLUMNS.length) {
    throw new Error(
      `expected ${ESP_COLUMNS.length} columns, got ${parts.length}: ${JSON.stringify(trimmed)}`,
    );
  }

  const ts_utc = parts[0].trim();
  if (ts_utc === "") throw new Error("ts_utc: empty");

  const ts_epoch = num(parts[1], "ts_epoch");
  if (ts_epoch === null) throw new Error("ts_epoch: empty");

  return {
    ts_utc,
    ts_epoch,
    jarak_cm: num(parts[2], "jarak_cm"),
    tinggi_cm: num(parts[3], "tinggi_cm"),
    valid: num(parts[4], "valid"),
    n_sampel: num(parts[5], "n_sampel"),
    tip_total: num(parts[6], "tip_total"),
    tip_menit: num(parts[7], "tip_menit"),
    mm_per_jam: num(parts[8], "mm_per_jam"),
    level: str(parts[9]),
    pompa: num(parts[10], "pompa"),
    time_src: str(parts[11]),
    rssi: num(parts[12], "rssi"),
    sms_status: str(parts[13]),
  };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npm test`

Expected: PASS — 6 new tests plus the 2 from Task 2

- [ ] **Step 5: Commit**

```bash
git add web/lib/esp-csv.ts web/tests/esp-csv.test.ts
git commit -m "feat(web): parse ESP32 CSV rows

Column order is the contract, taken from logic_csv.h. A blank numeric field
stays null: a missing reading is not a reading of zero."
```

---

### Task 4: The ingest endpoint

**Files:**
- Create: `web/lib/ingest.ts`
- Create: `web/app/api/ingest/route.ts`
- Test: `web/tests/ingest.test.ts`

**Interfaces:**
- Consumes: `openDb`/`getDb` from `web/lib/db.ts`, `parseEspCsv` and `EspRow` from `web/lib/esp-csv.ts`
- Produces:
  - `insertBatch(db: Database.Database, device: string, rows: EspRow[]): number` — rows actually inserted, in one transaction
  - `POST(req: Request): Promise<Response>` at `/api/ingest`

- [ ] **Step 1: Write the failing test**

`web/tests/ingest.test.ts`:

```typescript
import { describe, it, expect, afterEach } from "vitest";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { openDb } from "../lib/db";
import { insertBatch } from "../lib/ingest";
import { parseEspCsv } from "../lib/esp-csv";

const A = "2026-08-20T10:30:00Z,1787654321,45.2,154.8,1,12,340,2,4.8,NORMAL,0,ntp,-67,ok";
const B = "2026-08-20T10:31:00Z,1787654381,45.0,155.0,1,12,341,1,2.4,NORMAL,0,ntp,-65,ok";

let dir: string | null = null;
function db() {
  dir = mkdtempSync(join(tmpdir(), "syurell-"));
  return openDb(join(dir, "t.sqlite"));
}

afterEach(() => {
  if (dir) rmSync(dir, { recursive: true, force: true });
  dir = null;
});

describe("insertBatch", () => {
  it("inserts every row once", () => {
    const d = db();
    const rows = [A, B].map((l) => parseEspCsv(l)!);
    expect(insertBatch(d, "esp32-01", rows)).toBe(2);

    const { n } = d.prepare("SELECT COUNT(*) AS n FROM esp_readings").get() as { n: number };
    expect(n).toBe(2);
  });

  it("is idempotent — re-delivery adds nothing", () => {
    const d = db();
    const rows = [A, B].map((l) => parseEspCsv(l)!);
    insertBatch(d, "esp32-01", rows);
    insertBatch(d, "esp32-01", rows);

    const { n } = d.prepare("SELECT COUNT(*) AS n FROM esp_readings").get() as { n: number };
    expect(n).toBe(2);
  });

  it("keeps rows from different devices apart", () => {
    const d = db();
    const rows = [parseEspCsv(A)!];
    insertBatch(d, "esp32-01", rows);
    insertBatch(d, "esp32-02", rows);

    const { n } = d.prepare("SELECT COUNT(*) AS n FROM esp_readings").get() as { n: number };
    expect(n).toBe(2);
  });

  it("stores a null numeric as NULL, not 0", () => {
    const d = db();
    const gap = "2026-08-20T10:30:00Z,1787654321,,154.8,1,12,340,2,4.8,NORMAL,0,ntp,-67,ok";
    insertBatch(d, "esp32-01", [parseEspCsv(gap)!]);

    const row = d.prepare("SELECT jarak_cm FROM esp_readings").get() as { jarak_cm: number | null };
    expect(row.jarak_cm).toBeNull();
  });

  it("writes nothing when the surrounding transaction fails", () => {
    const d = db();
    // A batch is all-or-nothing: the transaction must roll back.
    expect(() =>
      d.transaction(() => {
        insertBatch(d, "esp32-01", [parseEspCsv(A)!]);
        throw new Error("boom");
      })(),
    ).toThrow();

    const { n } = d.prepare("SELECT COUNT(*) AS n FROM esp_readings").get() as { n: number };
    expect(n).toBe(0);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npm test`

Expected: FAIL — cannot resolve `../lib/ingest`

- [ ] **Step 3: Write the insert helper**

`web/lib/ingest.ts`:

```typescript
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npm test`

Expected: PASS — 5 new tests

- [ ] **Step 5: Write the route handler**

`web/app/api/ingest/route.ts`:

```typescript
import { getDb } from "@/lib/db";
import { parseEspCsv, type EspRow } from "@/lib/esp-csv";
import { insertBatch } from "@/lib/ingest";

export const dynamic = "force-dynamic";

type Body = { device?: unknown; rows?: unknown };

/**
 * Receive a batch from the ESP32.
 *
 * The firmware advances its SD cursor ONLY on a 2xx, so a 2xx here is a promise
 * that every row is durably stored. Anything short of that must return non-2xx
 * and let the firmware re-send.
 */
export async function POST(req: Request): Promise<Response> {
  let body: Body;
  try {
    body = (await req.json()) as Body;
  } catch {
    return Response.json({ error: "body is not valid JSON" }, { status: 400 });
  }

  const device = typeof body.device === "string" ? body.device.trim() : "";
  if (device === "") {
    return Response.json({ error: "device is required" }, { status: 400 });
  }
  if (!Array.isArray(body.rows)) {
    return Response.json({ error: "rows must be an array" }, { status: 400 });
  }

  // Parse everything BEFORE touching the database: one bad row rejects the
  // whole batch, and we must not have written half of it by then.
  const parsed: EspRow[] = [];
  for (const [i, entry] of body.rows.entries()) {
    const csv = (entry as { csv?: unknown })?.csv;
    if (typeof csv !== "string") {
      return Response.json({ error: `rows[${i}].csv must be a string` }, { status: 400 });
    }
    try {
      const row = parseEspCsv(csv);
      if (row !== null) parsed.push(row);
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      return Response.json({ error: `rows[${i}]: ${msg}` }, { status: 400 });
    }
  }

  if (parsed.length === 0) {
    // Header-only or empty batch. Nothing to store, nothing went wrong — 2xx
    // lets the firmware move past those lines.
    return Response.json({ received: 0, inserted: 0 });
  }

  try {
    const inserted = insertBatch(getDb(), device, parsed);
    return Response.json({ received: parsed.length, inserted });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return Response.json({ error: `store failed: ${msg}` }, { status: 503 });
  }
}
```

- [ ] **Step 6: Verify the endpoint end to end**

Run in one terminal: `cd web && npm run dev`

Then in another:

```bash
curl -s -X POST http://127.0.0.1:8000/api/ingest \
  -H "Content-Type: application/json" \
  -d '{"device":"esp32-01","rows":[{"csv":"2026-08-20T10:30:00Z,1787654321,45.2,154.8,1,12,340,2,4.8,NORMAL,0,ntp,-67,ok"}]}' \
  -w "\nHTTP %{http_code}\n"
```

Expected: `{"received":1,"inserted":1}` and `HTTP 200`. Repeat the same command: `{"received":1,"inserted":0}` and `HTTP 200` — idempotent.

Then a malformed batch:

```bash
curl -s -X POST http://127.0.0.1:8000/api/ingest \
  -H "Content-Type: application/json" \
  -d '{"device":"esp32-01","rows":[{"csv":"2026-08-20T10:30:00Z,1787654321,45.2"}]}' \
  -w "\nHTTP %{http_code}\n"
```

Expected: `HTTP 400` — the firmware will re-send.

- [ ] **Step 7: Commit**

```bash
git add web/lib/ingest.ts web/app/api/ingest/route.ts web/tests/ingest.test.ts
git commit -m "feat(web): add the ESP32 ingest endpoint

Parses the whole batch before writing anything, so one bad row rejects the
batch without a partial write. 2xx is a promise the rows are stored: the
firmware drops its copy on 2xx and re-sends on anything else."
```

---

### Task 5: Join the two time series

ESP logs every minute, the camera every 30 seconds, and the two clocks are not in step. Exact timestamp matching would throw away nearly every pair.

**Files:**
- Create: `web/lib/join.ts`
- Test: `web/tests/join.test.ts`

**Interfaces:**
- Consumes: nothing (pure functions over plain objects)
- Produces:
  - `type Observation = { ts_epoch: number; coverage: number | null; accumulation_frac: number | null; growth_per_min: number | null; alert: number | null; alert_reason: string | null }`
  - `type EspSample = { ts_epoch: number; tinggi_cm: number | null; mm_per_jam: number | null; level: string | null }`
  - `type Joined = { ts_epoch: number; esp: EspSample; obs: Observation | null }`
  - `nearestObservation(obs: Observation[], tsEpoch: number, toleranceS?: number): Observation | null`
  - `joinSeries(esp: EspSample[], obs: Observation[], toleranceS?: number): Joined[]`
  - `DEFAULT_TOLERANCE_S = 60`

- [ ] **Step 1: Write the failing test**

`web/tests/join.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import { nearestObservation, joinSeries, type Observation } from "../lib/join";

function obs(ts: number, coverage: number | null): Observation {
  return {
    ts_epoch: ts,
    coverage,
    accumulation_frac: 0.1,
    growth_per_min: 0,
    alert: 0,
    alert_reason: "",
  };
}

describe("nearestObservation", () => {
  it("picks the closest sample inside the window", () => {
    const list = [obs(1000, 0.1), obs(1040, 0.2), obs(1080, 0.3)];
    expect(nearestObservation(list, 1035)!.ts_epoch).toBe(1040);
  });

  it("returns null when nothing is inside the window", () => {
    expect(nearestObservation([obs(1000, 0.1)], 2000)).toBeNull();
  });

  it("accepts a sample exactly on the tolerance boundary", () => {
    expect(nearestObservation([obs(1000, 0.1)], 1060, 60)!.ts_epoch).toBe(1000);
  });

  it("returns null on an empty list", () => {
    expect(nearestObservation([], 1000)).toBeNull();
  });
});

describe("joinSeries", () => {
  it("keeps ESP rows that have no camera match", () => {
    const esp = [{ ts_epoch: 5000, tinggi_cm: 154.8, mm_per_jam: 0, level: "NORMAL" }];
    const out = joinSeries(esp, [obs(1000, 0.1)]);
    expect(out).toHaveLength(1);
    expect(out[0].obs).toBeNull();
  });

  it("pairs rows whose clocks are close but not equal", () => {
    const esp = [{ ts_epoch: 1000, tinggi_cm: 154.8, mm_per_jam: 0, level: "NORMAL" }];
    const out = joinSeries(esp, [obs(1012, 0.42)]);
    expect(out[0].obs!.coverage).toBeCloseTo(0.42);
  });

  it("carries a null coverage through as null", () => {
    const esp = [{ ts_epoch: 1000, tinggi_cm: 154.8, mm_per_jam: 0, level: "NORMAL" }];
    const out = joinSeries(esp, [obs(1000, null)]);
    expect(out[0].obs!.coverage).toBeNull();
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npm test`

Expected: FAIL — cannot resolve `../lib/join`

- [ ] **Step 3: Write the implementation**

`web/lib/join.ts`:

```typescript
export type Observation = {
  ts_epoch: number;
  coverage: number | null;
  accumulation_frac: number | null;
  growth_per_min: number | null;
  alert: number | null;
  alert_reason: string | null;
};

export type EspSample = {
  ts_epoch: number;
  tinggi_cm: number | null;
  mm_per_jam: number | null;
  level: string | null;
};

export type Joined = {
  ts_epoch: number;
  esp: EspSample;
  obs: Observation | null;
};

/** ESP logs every 60 s, the camera every 30 s, and neither clock is exact. */
export const DEFAULT_TOLERANCE_S = 60;

/**
 * Closest observation to `tsEpoch`, or null if the nearest one is further away
 * than the tolerance. Exact matching would discard almost every pair.
 */
export function nearestObservation(
  obs: Observation[],
  tsEpoch: number,
  toleranceS: number = DEFAULT_TOLERANCE_S,
): Observation | null {
  let best: Observation | null = null;
  let bestGap = Number.POSITIVE_INFINITY;

  for (const o of obs) {
    const gap = Math.abs(o.ts_epoch - tsEpoch);
    if (gap <= toleranceS && gap < bestGap) {
      best = o;
      bestGap = gap;
    }
  }
  return best;
}

/**
 * One output row per ESP reading. An ESP row with no camera match is KEPT with
 * `obs: null` — water level and rainfall are still real measurements when the
 * camera is down, and dropping them would put holes in the rainfall series.
 */
export function joinSeries(
  esp: EspSample[],
  obs: Observation[],
  toleranceS: number = DEFAULT_TOLERANCE_S,
): Joined[] {
  return esp.map((e) => ({
    ts_epoch: e.ts_epoch,
    esp: e,
    obs: nearestObservation(obs, e.ts_epoch, toleranceS),
  }));
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npm test`

Expected: PASS — 7 new tests

- [ ] **Step 5: Commit**

```bash
git add web/lib/join.ts web/tests/join.test.ts
git commit -m "feat(web): join ESP and camera series on a time window

Exact timestamp matching would discard nearly every pair: the two devices
sample at different rates on unsynchronised clocks. ESP rows with no camera
match are kept, because level and rainfall are still real when the camera
is down."
```

---

### Task 6: The operator verdict

The one line the operator actually acts on. Pure logic, kept out of the page so it can be tested and so the Claude Design work can restyle the page without changing what is said.

**Files:**
- Create: `web/lib/verdict.ts`
- Test: `web/tests/verdict.test.ts`

**Interfaces:**
- Consumes: `Observation` from `web/lib/join.ts`
- Produces:
  - `type Verdict = { state: "unknown" | "clear" | "watch" | "blocked"; headline: string; detail: string; minutesToThreshold: number | null }`
  - `verdict(obs: Observation | null, areaThreshold?: number): Verdict`
  - `formatCoverage(v: number | null): string`
  - `DEFAULT_AREA_THRESHOLD = 0.18` — matches `configs/inference/site_bendungan.yaml`

- [ ] **Step 1: Write the failing test**

`web/tests/verdict.test.ts`:

```typescript
import { describe, it, expect } from "vitest";
import { verdict, formatCoverage } from "../lib/verdict";
import type { Observation } from "../lib/join";

function o(over: Partial<Observation>): Observation {
  return {
    ts_epoch: 1000,
    coverage: 0.05,
    accumulation_frac: 0.05,
    growth_per_min: 0,
    alert: 0,
    alert_reason: "",
    ...over,
  };
}

describe("formatCoverage", () => {
  it("never renders null as zero", () => {
    expect(formatCoverage(null)).toBe("tidak terukur");
  });

  it("renders a fraction as a percentage", () => {
    expect(formatCoverage(0.1246)).toBe("12,5%");
  });
});

describe("verdict", () => {
  it("is unknown when there is no observation at all", () => {
    expect(verdict(null).state).toBe("unknown");
  });

  it("is unknown when accumulation could not be measured", () => {
    expect(verdict(o({ accumulation_frac: null })).state).toBe("unknown");
  });

  it("is clear well below the threshold", () => {
    expect(verdict(o({ accumulation_frac: 0.05 })).state).toBe("clear");
  });

  it("is blocked at or above the threshold", () => {
    expect(verdict(o({ accumulation_frac: 0.18 })).state).toBe("blocked");
    expect(verdict(o({ accumulation_frac: 0.3 })).state).toBe("blocked");
  });

  it("is watch when still below the threshold but climbing", () => {
    const v = verdict(o({ accumulation_frac: 0.1, growth_per_min: 0.01 }));
    expect(v.state).toBe("watch");
    expect(v.minutesToThreshold).toBeCloseTo(8, 0);
  });

  it("gives no time-to-threshold when growth is flat or falling", () => {
    expect(verdict(o({ accumulation_frac: 0.1, growth_per_min: 0 })).minutesToThreshold).toBeNull();
    expect(verdict(o({ accumulation_frac: 0.1, growth_per_min: -0.02 })).minutesToThreshold).toBeNull();
  });

  it("respects the alert flag the inference side already raised", () => {
    expect(verdict(o({ accumulation_frac: 0.05, alert: 1, alert_reason: "growth" })).state).toBe(
      "blocked",
    );
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npm test`

Expected: FAIL — cannot resolve `../lib/verdict`

- [ ] **Step 3: Write the implementation**

`web/lib/verdict.ts`:

```typescript
import type { Observation } from "./join";

export type Verdict = {
  state: "unknown" | "clear" | "watch" | "blocked";
  headline: string;
  detail: string;
  /** Minutes until accumulation reaches the threshold, when it is climbing. */
  minutesToThreshold: number | null;
};

/** Matches blockage.area_threshold in configs/inference/site_bendungan.yaml. */
export const DEFAULT_AREA_THRESHOLD = 0.18;

/**
 * A fraction as Indonesian percent, or the words for "not measured".
 *
 * Never returns "0%" for null. metrics.py returns None rather than 0.0 on
 * purpose: 0.0 reads as "clean river", which is the wrong thing to show during
 * a flood.
 */
export function formatCoverage(v: number | null): string {
  if (v === null || !Number.isFinite(v)) return "tidak terukur";
  return `${(v * 100).toFixed(1).replace(".", ",")}%`;
}

export function verdict(
  obs: Observation | null,
  areaThreshold: number = DEFAULT_AREA_THRESHOLD,
): Verdict {
  if (obs === null || obs.accumulation_frac === null) {
    return {
      state: "unknown",
      headline: "Belum ada pengukuran",
      detail: "Kamera tidak mengirim data. Periksa kondisi di lokasi secara langsung.",
      minutesToThreshold: null,
    };
  }

  const frac = obs.accumulation_frac;
  const growth = obs.growth_per_min ?? 0;

  if (obs.alert === 1 || frac >= areaThreshold) {
    return {
      state: "blocked",
      headline: "Bersihkan dulu sebelum membuka pintu",
      detail: obs.alert_reason?.trim()
        ? obs.alert_reason
        : `Penumpukan ${formatCoverage(frac)} sudah mencapai ambang ${formatCoverage(areaThreshold)}.`,
      minutesToThreshold: null,
    };
  }

  if (growth > 0) {
    const minutes = (areaThreshold - frac) / growth;
    return {
      state: "watch",
      headline: "Penumpukan sedang bertambah",
      detail: `Sekarang ${formatCoverage(frac)}, naik ${formatCoverage(growth)} per menit.`,
      minutesToThreshold: minutes,
    };
  }

  return {
    state: "clear",
    headline: "Aman membuka pintu",
    detail: `Penumpukan ${formatCoverage(frac)}, di bawah ambang ${formatCoverage(areaThreshold)}.`,
    minutesToThreshold: null,
  };
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npm test`

Expected: PASS — 9 new tests

- [ ] **Step 5: Commit**

```bash
git add web/lib/verdict.ts web/tests/verdict.test.ts
git commit -m "feat(web): derive the operator verdict from the latest observation

Kept out of the page so it is testable and so restyling cannot change what
the operator is told. Null accumulation is 'unknown', never 'clear'."
```

---

### Task 7: The latest-reading API and the operator page

**Files:**
- Create: `web/lib/latest.ts`
- Create: `web/app/api/latest/route.ts`
- Create: `web/app/layout.tsx`
- Create: `web/app/page.tsx`
- Create: `web/app/globals.css`
- Test: `web/tests/latest.test.ts`

**Interfaces:**
- Consumes: `getDb`/`openDb`/`hasObservations` from `web/lib/db.ts`, `Observation` from `web/lib/join.ts`, `verdict`/`formatCoverage` from `web/lib/verdict.ts`
- Produces:
  - `type LatestEsp = { ts_utc: string; tinggi_cm: number | null; mm_per_jam: number | null; level: string | null }`
  - `type LatestObs = Observation & { ts_utc: string }`
  - `type Latest = { esp: LatestEsp | null; obs: LatestObs | null }`
  - `readLatest(db: Database.Database): Latest`
  - `GET(): Promise<Response>` at `/api/latest`

- [ ] **Step 1: Write the failing test**

`web/tests/latest.test.ts`:

```typescript
import { describe, it, expect, afterEach } from "vitest";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { openDb } from "../lib/db";
import { readLatest } from "../lib/latest";

let dir: string | null = null;
function db() {
  dir = mkdtempSync(join(tmpdir(), "syurell-"));
  return openDb(join(dir, "t.sqlite"));
}

afterEach(() => {
  if (dir) rmSync(dir, { recursive: true, force: true });
  dir = null;
});

describe("readLatest", () => {
  it("returns nulls on an empty database instead of throwing", () => {
    const out = readLatest(db());
    expect(out.esp).toBeNull();
    expect(out.obs).toBeNull();
  });

  it("returns the newest ESP row", () => {
    const d = db();
    const sql =
      "INSERT INTO esp_readings (device, ts_utc, ts_epoch, tinggi_cm) VALUES (?, ?, ?, ?)";
    d.prepare(sql).run("esp32-01", "2026-08-20T10:30:00Z", 1787654321, 154.8);
    d.prepare(sql).run("esp32-01", "2026-08-20T10:31:00Z", 1787654381, 155.9);

    expect(readLatest(d).esp!.tinggi_cm).toBeCloseTo(155.9);
  });

  it("survives a database with no observations table", () => {
    // Inference may not have run yet. That is not an error.
    expect(readLatest(db()).obs).toBeNull();
  });

  it("returns the newest observation when the table exists", () => {
    const d = db();
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npm test`

Expected: FAIL — cannot resolve `../lib/latest`

- [ ] **Step 3: Write the reader**

`web/lib/latest.ts`:

```typescript
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npm test`

Expected: PASS — 4 new tests

- [ ] **Step 5: Write the route**

`web/app/api/latest/route.ts`:

```typescript
import { getDb } from "@/lib/db";
import { readLatest } from "@/lib/latest";
import { verdict } from "@/lib/verdict";

export const dynamic = "force-dynamic";

export async function GET(): Promise<Response> {
  try {
    const latest = readLatest(getDb());
    return Response.json({ ...latest, verdict: verdict(latest.obs) });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return Response.json({ error: msg }, { status: 503 });
  }
}
```

- [ ] **Step 6: Write the page**

`web/app/globals.css`:

```css
:root {
  --ground: #f2f4f5;
  --surface: #ffffff;
  --ink: #12212b;
  --soft: #4a5c67;
  --rule: #d3dade;
  --clear: #2e7d5b;
  --watch: #b07d22;
  --blocked: #b04a22;
  --unknown: #7c8c96;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  background: var(--ground);
  color: var(--ink);
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
}
```

`web/app/layout.tsx`:

```tsx
import "./globals.css";
import type { ReactNode } from "react";

export const metadata = {
  title: "Syurell — pemantauan pintu air",
  description: "Tinggi air, curah hujan, dan penumpukan sampah di depan pintu.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="id">
      <body>{children}</body>
    </html>
  );
}
```

`web/app/page.tsx`:

```tsx
import { getDb } from "@/lib/db";
import { readLatest } from "@/lib/latest";
import { verdict, formatCoverage } from "@/lib/verdict";

export const dynamic = "force-dynamic";
export const revalidate = 0;

const STATE_COLOR: Record<string, string> = {
  clear: "var(--clear)",
  watch: "var(--watch)",
  blocked: "var(--blocked)",
  unknown: "var(--unknown)",
};

function num(v: number | null | undefined, unit: string): string {
  return v === null || v === undefined || !Number.isFinite(v)
    ? "tidak terukur"
    : `${v.toFixed(1)} ${unit}`;
}

export default function OperatorPage() {
  const latest = readLatest(getDb());
  const v = verdict(latest.obs);

  const cards = [
    { label: "Tinggi air", value: num(latest.esp?.tinggi_cm, "cm") },
    { label: "Curah hujan", value: num(latest.esp?.mm_per_jam, "mm/jam") },
    { label: "Penumpukan", value: formatCoverage(latest.obs?.accumulation_frac ?? null) },
  ];

  return (
    <main style={{ maxWidth: "60rem", margin: "0 auto", padding: "2rem 1.5rem" }}>
      {/* Plain markup on purpose: the visual design is done separately in
          Claude Design, and lib/verdict.ts owns what is actually said. */}
      <meta httpEquiv="refresh" content="30" />

      <h1 style={{ fontSize: "1.1rem", fontWeight: 600, color: "var(--soft)" }}>
        Pemantauan pintu air
      </h1>

      <section
        style={{
          background: "var(--surface)",
          border: "1px solid var(--rule)",
          borderTop: `4px solid ${STATE_COLOR[v.state]}`,
          padding: "1.5rem",
          marginBottom: "1.5rem",
        }}
      >
        <div style={{ fontSize: "2rem", fontWeight: 700, lineHeight: 1.2 }}>{v.headline}</div>
        <p style={{ color: "var(--soft)", margin: "0.5rem 0 0" }}>{v.detail}</p>
        {v.minutesToThreshold !== null && (
          <p style={{ color: "var(--watch)", fontWeight: 600, margin: "0.5rem 0 0" }}>
            Perkiraan mencapai ambang dalam {Math.round(v.minutesToThreshold)} menit.
          </p>
        )}
      </section>

      <section style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "1rem" }}>
        {cards.map((c) => (
          <div
            key={c.label}
            style={{
              background: "var(--surface)",
              border: "1px solid var(--rule)",
              padding: "1rem",
            }}
          >
            <div style={{ fontSize: "0.8rem", color: "var(--soft)" }}>{c.label}</div>
            <div style={{ fontSize: "1.6rem", fontWeight: 700 }}>{c.value}</div>
          </div>
        ))}
      </section>

      <p style={{ color: "var(--soft)", fontSize: "0.85rem", marginTop: "1.5rem" }}>
        Sensor: {latest.esp?.ts_utc ?? "belum ada data"} · Kamera:{" "}
        {latest.obs?.ts_utc ?? "belum ada data"}
      </p>
    </main>
  );
}
```

- [ ] **Step 7: Verify the page renders**

Run: `cd web && npm run dev`

Open `http://127.0.0.1:8000`.

Expected on an empty database: headline "Belum ada pengukuran", all three cards read "tidak terukur", both timestamps read "belum ada data". Nothing shows `0`.

Then POST the sample row from Task 4 Step 6 and reload: the water-level card shows `154.8 cm`, the camera card still says "tidak terukur".

- [ ] **Step 8: Run the full test suite**

Run: `cd web && npm test`

Expected: PASS — every test from Tasks 2–7.

- [ ] **Step 9: Commit**

```bash
git add web/lib/latest.ts web/app/api/latest/route.ts web/app/layout.tsx web/app/page.tsx web/app/globals.css web/tests/latest.test.ts
git commit -m "feat(web): add the latest-reading API and the operator page

Missing data is reported as missing, never as zero. Markup is deliberately
plain: the visual design is done separately, and verdict.ts owns what the
operator is actually told."
```

---

### Task 8: Point the firmware at the server

**Files:**
- Modify: `firmware/esp32/include/config_secrets.h.example`
- Create: `web/README.md`

**Interfaces:**
- Consumes: the running server from Task 7
- Produces: nothing code-level — this closes the loop the spec opened

- [ ] **Step 1: Fix the example URL**

The spec records the mismatch: the example says port 8000 and path `/ingest`, but the route lives at `/api/ingest`. The server already listens on 8000, so only the path is wrong.

In `firmware/esp32/include/config_secrets.h.example`, replace the `INGEST_URL` and `DEVICE_ID` lines with:

```c
// Path is /api/ingest, not /ingest: the handler is a Next.js App Router route
// at web/app/api/ingest/route.ts. Port 8000 matches `npm run dev` in web/.
// Use the laptop's LAN address, not localhost -- the ESP32 resolves this name
// itself, where localhost means the ESP32.
#define INGEST_URL    "http://192.168.1.10:8000/api/ingest"
#define DEVICE_ID     "esp32-01"
```

- [ ] **Step 2: Write the README**

`web/README.md`:

````markdown
# Web monitoring

Dashboard, and the ingest endpoint the ESP32 firmware posts to.

Design: [`../docs/superpowers/specs/2026-08-20-monitoring-web-design.md`](../docs/superpowers/specs/2026-08-20-monitoring-web-design.md)

## Running

```bash
cd web
npm install
npm run dev        # http://127.0.0.1:8000
```

Reads `../out/timeseries.sqlite`, the same file `src/inference/sink.py` writes.
Override with `SYURELL_DB`.

The camera half of the dashboard stays empty until inference has run:

```bash
PYTHONPATH=src ./.venv/Scripts/python.exe -m inference.run \
    --config configs/inference/site_bendungan.yaml --source <video>
```

## Pointing the ESP32 at it

Set `INGEST_URL` in `firmware/esp32/include/config_secrets.h` to the laptop's
LAN address — `http://<laptop-ip>:8000/api/ingest`. Not `localhost`: the ESP32
resolves that name itself, where it means the ESP32.

Check it end to end:

```bash
curl -s -X POST http://127.0.0.1:8000/api/ingest \
  -H "Content-Type: application/json" \
  -d '{"device":"esp32-01","rows":[{"csv":"2026-08-20T10:30:00Z,1787654321,45.2,154.8,1,12,340,2,4.8,NORMAL,0,ntp,-67,ok"}]}'
```

Send it twice: the second call returns `"inserted":0` and still 200. That is the
idempotency the firmware relies on.

## The one rule

`/api/ingest` replies 2xx **only** when every row is stored. The firmware
advances its SD cursor on 2xx and never re-sends those rows. On any failure it
must return non-2xx so the firmware retries.

## Tests

```bash
npm test
```
````

- [ ] **Step 3: Commit**

```bash
git add firmware/esp32/include/config_secrets.h.example web/README.md
git commit -m "docs(web): align the example ingest URL with the real route

The example pointed at /ingest; the handler is at /api/ingest. Also notes the
ESP32 needs the laptop's LAN address, since localhost there is the ESP32."
```

---

## Out of scope for this plan

Deliberately deferred — each needs its own plan:

- **`/analisis`** — time-series charts, the `h ∝ 1/A²` scatter, rain-to-debris cross-correlation, CSV export. Needs `/api/series` and `/api/export`, and is worth little until a season of real data exists. `lib/join.ts` is built here so that plan starts with the join already tested.
- **`/demo`** — the presentation page. Most dependent on site footage that has not been recorded.
- **Visual design** — done separately in Claude Design. Task 7's markup is plain on purpose; `lib/verdict.ts` owns the wording so restyling cannot change what the operator is told.
- **Auth, Pi deployment, WhatsApp/SMS alerts, live video, multi-site** — listed as out of scope in the spec.
