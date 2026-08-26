import { readFile, writeFile, rename, mkdir } from "node:fs/promises";
import path from "node:path";
import { LIVE_DIR } from "@/lib/live";

/**
 * Reads what the inference loop is running, and asks it to switch.
 *
 * THIS HANDLER NEVER STARTS A PROCESS. It writes one small JSON file that the
 * already-running loop polls. Giving an HTTP endpoint the power to spawn
 * programs would be a hole worth attacking, and every dev-server reload would
 * orphan a child still holding the camera. See src/inference/control.py.
 */
export const dynamic = "force-dynamic";
export const revalidate = 0;

type Status = {
  active: string;
  devices: { index: number; width: number; height: number }[];
  error: string | null;
  ts_epoch: number;
};

export async function GET(): Promise<Response> {
  try {
    const raw = await readFile(path.join(LIVE_DIR, "status.json"), "utf-8");
    const status = JSON.parse(raw) as Status;
    return Response.json({ ...status, running: true }, {
      headers: { "Cache-Control": "no-store" },
    });
  } catch {
    // Inference is not running, or is running without preview.enabled.
    return Response.json(
      { active: null, devices: [], error: null, running: false },
      { status: 200, headers: { "Cache-Control": "no-store" } },
    );
  }
}

/**
 * A camera index, and nothing else.
 *
 * VALIDATION IS DELIBERATELY NARROW. This value is handed to cv2.VideoCapture
 * in another process. A single digit covers every webcam on this machine;
 * anything else is refused here rather than trusted, because a free-form string
 * reaching a capture layer is how a file path or a URL turns into something
 * nobody intended to open.
 */
function validSource(v: unknown): string | null {
  if (typeof v !== "string") return null;
  const s = v.trim();
  return /^[0-9]$/.test(s) ? s : null;
}

export async function POST(req: Request): Promise<Response> {
  let body: unknown;
  try {
    body = await req.json();
  } catch {
    return Response.json({ error: "body bukan JSON" }, { status: 400 });
  }

  const source = validSource((body as { source?: unknown })?.source);
  if (source === null) {
    return Response.json({ error: "source harus indeks kamera 0-9" }, { status: 400 });
  }

  try {
    await mkdir(LIVE_DIR, { recursive: true });
    // Atomic, like every other write to this directory: the inference loop
    // polls this file, and a half-written one would read as no request at all.
    const tmp = path.join(LIVE_DIR, ".control.json.tmp");
    await writeFile(tmp, JSON.stringify({ source }, null, 2), "utf-8");
    await rename(tmp, path.join(LIVE_DIR, "control.json"));
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return Response.json({ error: msg }, { status: 500 });
  }

  // Accepted, not applied. The loop picks this up within about half a second
  // and reports through status.json whether the device actually opened.
  return Response.json({ requested: source }, { status: 202 });
}
