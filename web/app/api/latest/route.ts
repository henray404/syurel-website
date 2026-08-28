import { getDb } from "@/lib/db";
import { readLatest } from "@/lib/latest";
import { verdict } from "@/lib/verdict";

/**
 * Everything the dashboard needs, in one request.
 *
 * One endpoint rather than three: the demo page polls twice a second, and
 * separate round-trips would multiply that for data always read together. The
 * `esp` / `obs` / `verdict` keys keep their previous shape.
 */
export const dynamic = "force-dynamic";

export async function GET(): Promise<Response> {
  try {
    const db = getDb();
    const latest = readLatest(db);

    return Response.json({
      ...latest,
      verdict: verdict(latest.obs),
    });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return Response.json({ error: msg }, { status: 503 });
  }
}
