import { describe, it, expect } from "vitest";
import { verdict, formatCoverage } from "../lib/verdict";
import type { Observation } from "../lib/join";

function o(over: Partial<Observation>): Observation {
  return {
    ts_epoch: 1000,
    coverage: 0.05,
    accumulation_frac: 0.05,
    growth_per_min: 0,
    alert: 0,
    alert_reason: "",
    ...over,
  };
}

describe("formatCoverage", () => {
  it("never renders null as zero", () => {
    expect(formatCoverage(null)).toBe("tidak terukur");
  });

  it("renders a fraction as a percentage", () => {
    expect(formatCoverage(0.1246)).toBe("12,5%");
  });
});

describe("verdict", () => {
  it("is unknown when there is no observation at all", () => {
    expect(verdict(null).state).toBe("unknown");
  });

  it("is unknown when accumulation could not be measured", () => {
    expect(verdict(o({ accumulation_frac: null })).state).toBe("unknown");
  });

  it("is clear well below the threshold", () => {
    expect(verdict(o({ accumulation_frac: 0.05 })).state).toBe("clear");
  });

  it("is blocked at or above the threshold", () => {
    expect(verdict(o({ accumulation_frac: 0.18 })).state).toBe("blocked");
    expect(verdict(o({ accumulation_frac: 0.3 })).state).toBe("blocked");
  });

  it("is watch when still below the threshold but climbing", () => {
    const v = verdict(o({ accumulation_frac: 0.1, growth_per_min: 0.01 }));
    expect(v.state).toBe("watch");
    expect(v.minutesToThreshold).toBeCloseTo(8, 0);
  });

  it("gives no time-to-threshold when growth is flat or falling", () => {
    expect(verdict(o({ accumulation_frac: 0.1, growth_per_min: 0 })).minutesToThreshold).toBeNull();
    expect(
      verdict(o({ accumulation_frac: 0.1, growth_per_min: -0.02 })).minutesToThreshold,
    ).toBeNull();
  });

  it("respects the alert flag the inference side already raised", () => {
    expect(verdict(o({ accumulation_frac: 0.05, alert: 1, alert_reason: "growth" })).state).toBe(
      "blocked",
    );
  });
});
