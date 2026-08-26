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
