import { describe, expect, it } from "vitest";
import { polygonArea, validatePolygon, validatePolygons } from "../lib/polygons";

/**
 * These cases are duplicated in tests/test_inference.py
 * (test_polygon_validation_matches_the_web_contract). If you change one, change
 * the other: a rule that holds on only one side is exactly the silent failure
 * this contract exists to prevent.
 */
const SQUARE = [
  [0, 0],
  [1, 0],
  [1, 1],
  [0, 1],
];

describe("validatePolygon", () => {
  it("accepts a square covering the whole frame", () => {
    expect(validatePolygon(SQUARE).ok).toBe(true);
  });

  it("needs at least three points", () => {
    expect(
      validatePolygon([
        [0, 0],
        [1, 0],
      ]),
    ).toEqual({ ok: false, error: "minimal 3 titik" });
  });

  it("refuses coordinates outside the frame instead of clamping them", () => {
    // Clamping would hide a coordinate-system mismatch between the two sides.
    expect(
      validatePolygon([
        [0, 0],
        [1.5, 0],
        [1, 1],
      ]),
    ).toEqual({ ok: false, error: "koordinat harus di antara 0 dan 1" });
  });

  it("refuses pixel coordinates, which are the likely mistake", () => {
    // These are the real placeholder values from site_bendungan.yaml. Posting
    // them unconverted must fail loudly rather than build a mask off-screen.
    expect(
      validatePolygon([
        [120, 260],
        [1180, 260],
        [1240, 700],
      ]).ok,
    ).toBe(false);
  });

  it("refuses collinear points that would rasterise to an empty mask", () => {
    expect(
      validatePolygon([
        [0.1, 0.1],
        [0.5, 0.5],
        [0.9, 0.9],
      ]),
    ).toEqual({ ok: false, error: "luas nyaris nol -- titik segaris?" });
  });

  it("refuses non-numeric coordinates", () => {
    expect(validatePolygon([[0, 0], [1, 0], ["a", 1]]).ok).toBe(false);
    expect(validatePolygon([[0, 0], [1, 0], [NaN, 1]]).ok).toBe(false);
    expect(validatePolygon("bukan larik").ok).toBe(false);
  });

  it("refuses more than 64 points", () => {
    const many = Array.from({ length: 65 }, (_, i) => [i / 65, 0.5]);
    expect(validatePolygon(many)).toEqual({ ok: false, error: "maksimal 64 titik" });
  });
});

describe("validatePolygons", () => {
  it("names which polygon failed", () => {
    const r = validatePolygons({ roi: SQUARE, structure: [[0, 0]] });
    expect(r.ok).toBe(false);
    if (!r.ok) expect(r.error).toMatch(/^structure: /);
  });

  it("requires both polygons", () => {
    expect(validatePolygons({ roi: SQUARE }).ok).toBe(false);
    expect(validatePolygons(null).ok).toBe(false);
  });
});

describe("polygonArea", () => {
  it("gives 1 for the unit square regardless of winding", () => {
    expect(polygonArea(SQUARE as [number, number][])).toBeCloseTo(1);
    expect(polygonArea([...SQUARE].reverse() as [number, number][])).toBeCloseTo(1);
  });
});
