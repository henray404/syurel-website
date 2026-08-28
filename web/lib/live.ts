import { mkdir, rename, writeFile } from "node:fs/promises";
import path from "node:path";

/**
 * Where src/inference/preview.py writes its two JPEGs.
 *
 * This lives in lib/, not in the route handler, because both the route and the
 * /demo page need it. Importing it *from* the route handler made Next resolve
 * /demo as not-found on some requests and fine on others -- a route handler is
 * a special module in the App Router graph, not an ordinary one to import from.
 */
export const LIVE_DIR = process.env.SYURELL_LIVE_DIR ?? "../out/webcam/live";

/**
 * A closed set, not a sanitised path.
 *
 * The name comes from the URL. Any scheme that builds a filesystem path out of
 * it -- however carefully escaped -- is one bug away from serving arbitrary
 * files off this machine. Two fixed keys cannot be traversed.
 */
const FILES: Record<string, string> = {
  frame: "frame.jpg",
  mask: "mask.jpg",
};

/** Path for a known preview name, or null if the name is not one of them. */
export function previewPath(name: string): string | null {
  const file = FILES[name];
  return file === undefined ? null : path.join(LIVE_DIR, file);
}

/**
 * Upload ceiling. A 1280x720 JPEG off the Pi lands around 100-200 KB, so 5 MB
 * is far above any real frame while still bounding what one request can make
 * this process hold in memory.
 */
export const MAX_UPLOAD_BYTES = 5 * 1024 * 1024;

/** SOI + the first marker byte. Enough to reject anything that is not a JPEG. */
function isJpeg(bytes: Uint8Array): boolean {
  return bytes.length > 3 && bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff;
}

export type SaveResult = { ok: true; bytes: number } | { ok: false; status: number; error: string };

/**
 * Store one uploaded preview JPEG, for a Raspberry Pi running the inference on
 * another machine.
 *
 * Three things this refuses to do, each for a reason that has already bitten
 * something in this repo:
 *
 * 1. **The name never reaches the filesystem.** `previewPath` maps it through a
 *    closed set, so "../../etc/passwd" is a 404, not a traversal.
 * 2. **The bytes must look like a JPEG.** The demo page renders whatever is
 *    here as an <img>; a truncated POST that stored 40 bytes of nothing would
 *    show a broken frame under a live timestamp, which is the one failure this
 *    dashboard exists to avoid.
 * 3. **Writes are atomic.** preview.py writes tmp-then-replace because the web
 *    server reads frame.jpg on every poll; an upload that wrote in place would
 *    hand a reader half a frame. Same reason, same fix.
 */
export async function savePreview(name: string, bytes: Uint8Array): Promise<SaveResult> {
  const full = previewPath(name);
  if (full === null) {
    return { ok: false, status: 404, error: `unknown preview: ${name}` };
  }
  if (bytes.length === 0) {
    return { ok: false, status: 400, error: "empty body" };
  }
  if (bytes.length > MAX_UPLOAD_BYTES) {
    return { ok: false, status: 413, error: `body over ${MAX_UPLOAD_BYTES} bytes` };
  }
  if (!isJpeg(bytes)) {
    return { ok: false, status: 415, error: "body is not a JPEG (expected FF D8 FF)" };
  }

  const dir = path.dirname(full);
  await mkdir(dir, { recursive: true });
  const tmp = path.join(dir, `.${path.basename(full)}.upload.tmp`);
  await writeFile(tmp, bytes);
  await rename(tmp, full);
  return { ok: true, bytes: bytes.length };
}
