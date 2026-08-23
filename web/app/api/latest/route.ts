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
