/**
 * The polygon contract, shared by the editor and the API.
 *
 * THIS FILE MIRRORS `valid_polygon` in src/inference/control.py. The two sides
 * must agree exactly: a polygon that passes here and fails there is silently
 * ignored by the inference loop -- the operator draws a gate zone, the page says
 * saved, and the alerts keep using the old config. Any change to these rules
 * belongs in that function too, and the tests on both sides assert the same
 * cases.
 *
 * COORDINATES ARE FRACTIONS OF THE FRAME, 0..1 -- never pixels. Three things
 * rescale the picture between the camera and the click that places a point:
 * preview.py downscales to max_width, the browser fits the <img> to its column,
 * and switching camera changes the capture resolution. Pixels are wrong after
 * any of them; a fraction survives all three.
 */
export type Point = [number, number];
export type Polygon = Point[];
export type Polygons = { roi: Polygon; structure: Polygon };

/** Matches MIN_POINTS / MAX_POINTS in src/inference/control.py. */
export const MIN_POINTS = 3;
export const MAX_POINTS = 64;

/** Smallest area worth keeping, as a fraction of the frame. */
export const MIN_AREA = 0.0001;

type PolygonResult = { ok: true; polygon: Polygon } | { ok: false; error: string };

/** Returns the polygon, or a reason it is not one. Never clamps. */
export function validatePolygon(value: unknown): PolygonResult {
  if (!Array.isArray(value)) return { ok: false, error: "bukan larik" };
  if (value.length < MIN_POINTS) return { ok: false, error: `minimal ${MIN_POINTS} titik` };
  if (value.length > MAX_POINTS) return { ok: false, error: `maksimal ${MAX_POINTS} titik` };

  const polygon: Polygon = [];
  for (const pt of value) {
    if (!Array.isArray(pt) || pt.length !== 2) return { ok: false, error: "titik harus [x, y]" };
    const [x, y] = pt;
    if (
      typeof x !== "number" ||
      typeof y !== "number" ||
      !Number.isFinite(x) ||
      !Number.isFinite(y)
    ) {
      return { ok: false, error: "koordinat harus angka" };
    }
    // Rejected, not clamped: a point outside the frame means the two sides
    // disagree about the coordinate system, and pulling it to the edge would
    // hide the very bug this format exists to prevent.
    if (x < 0 || x > 1 || y < 0 || y > 1) {
      return { ok: false, error: "koordinat harus di antara 0 dan 1" };
    }
    polygon.push([x, y]);
  }

  if (polygonArea(polygon) < MIN_AREA) {
    // Collinear points pass every check above and still rasterise to an empty
    // mask. An empty structure polygon disables blockage alerts with no error
    // at all, which is the worst failure this endpoint could wave through.
    return { ok: false, error: "luas nyaris nol -- titik segaris?" };
  }

  return { ok: true, polygon };
}

export function validatePolygons(
  value: unknown,
): { ok: true; polygons: Polygons } | { ok: false; error: string } {
  if (typeof value !== "object" || value === null) return { ok: false, error: "body bukan objek" };
  const body = value as { roi?: unknown; structure?: unknown };

  const roi = validatePolygon(body.roi);
  if (!roi.ok) return { ok: false, error: `roi: ${roi.error}` };

  const structure = validatePolygon(body.structure);
  if (!structure.ok) return { ok: false, error: `structure: ${structure.error}` };

  return { ok: true, polygons: { roi: roi.polygon, structure: structure.polygon } };
}

/** Shoelace area, used only to reject degenerate shapes. */
export function polygonArea(polygon: Polygon): number {
  let sum = 0;
  for (let i = 0; i < polygon.length; i++) {
    const [x1, y1] = polygon[i];
    const [x2, y2] = polygon[(i + 1) % polygon.length];
    sum += x1 * y2 - x2 * y1;
  }
  return Math.abs(sum) / 2;
}
