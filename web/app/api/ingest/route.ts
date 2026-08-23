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
