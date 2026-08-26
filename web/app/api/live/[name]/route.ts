import { readFile, stat } from "node:fs/promises";
import { previewPath } from "@/lib/live";

/**
 * Serves the two preview JPEGs written by src/inference/preview.py.
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
