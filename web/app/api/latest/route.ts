import { getDb } from "@/lib/db";
import { readLatest } from "@/lib/latest";
import { verdict } from "@/lib/verdict";
import { fisika, loadSite } from "@/lib/fisika";
import { EMPTY_RAIN, readRainfall } from "@/lib/hujan";

/**
 * Everything the dashboard needs, in one request.
 *
 * One endpoint rather than four: the demo page polls twice a second, and four
 * round-trips would quadruple that for data always read together. The
 * `esp` / `obs` / `verdict` keys keep their previous shape, so existing callers
 * are unaffected.
 *
 * The physics and rainfall blocks degrade independently. Missing site geometry
 * or an absent rainfall table must never take down the water level and the
 * blockage verdict, which are the numbers an operator actually acts on.
 */
export const dynamic = "force-dynamic";

export async function GET(): Promise<Response> {
  try {
    const db = getDb();
    const latest = readLatest(db);

    let physics = null;
    try {
      physics = fisika(latest.obs?.accumulation_frac ?? null, loadSite());
    } catch {
      // configs/site_geometry.json missing or malformed. The page shows the
      // physics card as unavailable rather than the dashboard failing.
    }

    let rain = EMPTY_RAIN;
    try {
      rain = readRainfall(db);
    } catch {
      // No rainfall table yet: external.rainfall has never been run here.
    }

    return Response.json({
      ...latest,
      verdict: verdict(latest.obs),
      fisika: physics,
      hujan: rain,
    });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return Response.json({ error: msg }, { status: 503 });
  }
}
