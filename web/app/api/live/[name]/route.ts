import { readFile, stat } from "node:fs/promises";
import { MAX_UPLOAD_BYTES, previewPath, savePreview } from "@/lib/live";

/**
 * Serves the two preview JPEGs written by src/inference/preview.py -- and, on
 * POST, accepts them from an inference loop running on another machine.
 *
 * They cannot live in web/public: that directory is part of the repo, and these
 * files are rewritten every second by a separate process.
 */
export const dynamic = "force-dynamic";
export const revalidate = 0;

export async function GET(_req: Request, ctx: { params: Promise<{ name: string }> }) {
  const { name } = await ctx.params;
  const full = previewPath(name);
  if (full === null) {
    return new Response("unknown preview", { status: 404 });
  }

  try {
    const [data, info] = await Promise.all([readFile(full), stat(full)]);
    // Buffer IS a Uint8Array, so hand it over rather than copying it. The demo
    // page pulls frame+mask at 10 fps; copying every one churned megabytes a
    // second through the young generation and killed the dev server with
    // "NewSpace::EnsureCurrentCapacity Allocation failed" after ~95 seconds.
    return new Response(data, {
      headers: {
        "Content-Type": "image/jpeg",
        // Never cache. The whole point is that this file changes every second,
        // and a cached frame under a live timestamp is the exact failure this
        // dashboard exists to avoid.
        "Cache-Control": "no-store, must-revalidate",
        "Last-Modified": info.mtime.toUTCString(),
      },
    });
  } catch {
    // Inference not running, or running without preview.enabled. Not an error:
    // the page renders its own "belum ada" state from this 404.
    return new Response("preview not available", { status: 404 });
  }
}

/**
 * Accept one preview JPEG from a remote inference host (the Raspberry Pi).
 *
 * Raw body, not multipart: the sender is a script, not a browser form, and
 * `requests.post(url, data=jpeg_bytes)` is the whole client. Multipart would buy
 * field names nobody needs and a parser nobody should maintain.
 *
 * A 2xx means the bytes are on disk under their final name. The Pi may treat
 * anything else as "not delivered" and simply send the next frame -- these are
 * previews, so a dropped one costs nothing and retrying a stale frame is worse
 * than skipping it.
 */
export async function POST(req: Request, ctx: { params: Promise<{ name: string }> }) {
  const { name } = await ctx.params;

  // Check the declared length before reading, so an oversized upload is refused
  // at the header rather than after it has already been pulled into memory.
  const declared = Number(req.headers.get("content-length") ?? NaN);
  if (Number.isFinite(declared) && declared > MAX_UPLOAD_BYTES) {
    return Response.json({ error: `body over ${MAX_UPLOAD_BYTES} bytes` }, { status: 413 });
  }

  let bytes: Uint8Array;
  try {
    bytes = new Uint8Array(await req.arrayBuffer());
  } catch {
    return Response.json({ error: "could not read body" }, { status: 400 });
  }

  const saved = await savePreview(name, bytes);
  if (!saved.ok) {
    return Response.json({ error: saved.error }, { status: saved.status });
  }
  return Response.json({ name, bytes: saved.bytes });
}
