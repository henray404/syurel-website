import { describe, expect, it } from "vitest";
import {
  affluxRatio,
  blockageFactor,
  criticalBf,
  fisika,
  formatCm,
  type SiteGeometry,
} from "../lib/fisika";

/**
 * Mirrors tests/test_physics.py. Same site, same numbers, both languages.
 *
 * The two implementations exist because Python analyses the miniature
 * experiments while the web tells the operator; a formula that drifted between
 * them would show one afflux on the dashboard and another in the report, with
 * nothing to reveal which is right.
 */
const SITE: SiteGeometry = {
  gate: { b_m: 2.0, a_m: 1.0, Cd: 0.61, h_bersih_m: 0.8, z_jalan_m: 1.6 },
  bias: 0,
  skala: 1,
  calibrated: false,
  lat: null,
  lon: null,
  adm4: null,
};

describe("affluxRatio", () => {
  it("leaves a clear gate at its clear level", () => {
    expect(affluxRatio(0)).toBe(1);
  });

  it("quadruples the head at half blockage", () => {
    // 1/(1-0.5)^2 = 4. The square is the point: half the opening lost is four
    // times the head, not twice.
    expect(affluxRatio(0.5)).toBeCloseTo(4, 10);
  });

  it("refuses to answer beyond the trusted range", () => {
    // The model runs to infinity as BF -> 1, while real water goes over the top
    // or around the sides. A number here would be fiction.
    expect(affluxRatio(0.9)).toBeNull();
    expect(affluxRatio(0.85)).toBeNull();
  });
});

describe("blockageFactor", () => {
  it("never turns a missing measurement into a clear gate", () => {
    expect(blockageFactor(null, SITE)).toBeNull();
    expect(blockageFactor(NaN, SITE)).toBeNull();
  });

  it("applies the experiment-E2 calibration", () => {
    const biased: SiteGeometry = { ...SITE, skala: 1.3, bias: 0.02 };
    expect(blockageFactor(0.24, biased)).toBeCloseTo(0.332, 10);
  });
});

describe("criticalBf", () => {
  it("predicts the blockage that floods the road", () => {
    // Road at twice the clear head: 1 - sqrt(1/2) = 0.29289...
    expect(criticalBf(SITE)).toBeCloseTo(1 - Math.sqrt(0.5), 10);
  });

  it("puts the head exactly on the road at that blockage", () => {
    const bfc = criticalBf(SITE)!;
    expect(fisika(bfc, SITE).headM).toBeCloseTo(SITE.gate.z_jalan_m, 10);
  });

  it("returns null when the road is at or below the clear level", () => {
    expect(criticalBf({ ...SITE, gate: { ...SITE.gate, z_jalan_m: 0.8 } })).toBeNull();
  });
});

describe("fisika", () => {
  it("reports the capacity lost at an unchanged water level", () => {
    // NOT the discharge at the afflux head: that is algebraically equal to the
    // clear-gate discharge, so it would print one number in two columns.
    const f = fisika(0.5, SITE);
    expect(f.dischargeTersumbat!).toBeLessThan(f.dischargeBersih!);
    expect(f.dischargeTersumbat! / f.dischargeBersih!).toBeCloseTo(0.5, 10);
  });

  it("keeps everything null when nothing was measured", () => {
    const f = fisika(null, SITE);
    expect(f.bf).toBeNull();
    expect(f.affluxM).toBeNull();
    expect(f.headM).toBeNull();
    expect(f.marginToRoadM).toBeNull();
    // The site geometry is still known, so these stay populated.
    expect(f.criticalBf).not.toBeNull();
    expect(f.zJalanM).toBe(1.6);
  });

  it("carries the uncalibrated flag through", () => {
    expect(fisika(0.24, SITE).calibrated).toBe(false);
    expect(fisika(0.24, { ...SITE, calibrated: true }).calibrated).toBe(true);
  });
});

describe("formatCm", () => {
  it("says the words rather than showing a zero", () => {
    expect(formatCm(null)).toBe("tidak terukur");
    expect(formatCm(0.59)).toBe("59 cm");
  });
});
