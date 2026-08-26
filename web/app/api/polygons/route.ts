import { readFile, writeFile, rename, mkdir } from "node:fs/promises";
import path from "node:path";
import { LIVE_DIR } from "@/lib/live";
import { validatePolygons } from "@/lib/polygons";

/**
 * The ROI and gate-zone polygons the operator draws on /demo.
 *
 * Like /api/camera, this writes a file the running inference loop polls -- it
 * never touches the process. The loop rebuilds its masks within about half a
 * second and keeps measuring; nothing restarts.
 *
 * Validation is `validatePolygons`, the same module the editor calls before it
 * posts, mirroring `valid_polygon` in src/inference/control.py. Three copies of
 * one rule sounds like duplication, but the alternative is an editor that
 * cheerfully reports "tersimpan" for a polygon the loop then ignores.
 */
export const dynamic = "force-dynamic";
export const revalidate = 0;

const FILE = "polygons.json";

export async function GET(): Promise<Response> {
  try {
    const raw = await readFile(path.join(LIVE_DIR, FILE), "utf-8");
    const check = validatePolygons(JSON.parse(raw));
    if (!check.ok) {
      // On disk but invalid: report it rather than returning it. The loop is
      // ignoring this file too, and the editor must be able to show that.
      return Response.json(
        { saved: false, error: check.error },
        { headers: { "Cache-Control": "no-store" } },
      );
    }
    return Response.json(
      { saved: true, ...check.polygons },
      { headers: { "Cache-Control": "no-store" } },
    );
  } catch {
    // Nothing drawn yet. Not an error: the loop falls back to the config file.
    return Response.json(
      { saved: false, error: null },
      { headers: { "Cache-Control": "no-store" } },
    );
  }
}

export async function POST(req: Request): Promise<Response> {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return Response.json({ error: "body bukan JSON" }, { status: 400 });
  }

  const check = validatePolygons(body);
  if (!check.ok) {
    return Response.json({ error: check.error }, { status: 400 });
  }

  try {
    await mkdir(LIVE_DIR, { recursive: true });
    // Atomic: the loop polls this file, and a half-written one parses as
    // "nothing drawn", which would silently revert to the config polygons.
    const tmp = path.join(LIVE_DIR, `.${FILE}.tmp`);
    await writeFile(tmp, JSON.stringify({ ...check.polygons, normalized: true }, null, 2), "utf-8");
    await rename(tmp, path.join(LIVE_DIR, FILE));
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return Response.json({ error: msg }, { status: 500 });
  }

  return Response.json({ saved: true, ...check.polygons }, { status: 202 });
}
