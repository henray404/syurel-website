import { describe, it, expect } from "vitest";
import { nearestObservation, joinSeries, type Observation } from "../lib/join";

function obs(ts: number, coverage: number | null): Observation {
  return {
    ts_epoch: ts,
    coverage,
    accumulation_frac: 0.1,
    growth_per_min: 0,
    alert: 0,
    alert_reason: "",
  };
}

describe("nearestObservation", () => {
  it("picks the closest sample inside the window", () => {
    const list = [obs(1000, 0.1), obs(1040, 0.2), obs(1080, 0.3)];
    expect(nearestObservation(list, 1035)!.ts_epoch).toBe(1040);
  });

  it("returns null when nothing is inside the window", () => {
    expect(nearestObservation([obs(1000, 0.1)], 2000)).toBeNull();
  });

  it("accepts a sample exactly on the tolerance boundary", () => {
    expect(nearestObservation([obs(1000, 0.1)], 1060, 60)!.ts_epoch).toBe(1000);
  });

  it("returns null on an empty list", () => {
    expect(nearestObservation([], 1000)).toBeNull();
  });
});

describe("joinSeries", () => {
  it("keeps ESP rows that have no camera match", () => {
    const esp = [{ ts_epoch: 5000, tinggi_cm: 154.8, mm_per_jam: 0, level: "NORMAL" }];
    const out = joinSeries(esp, [obs(1000, 0.1)]);
    expect(out).toHaveLength(1);
    expect(out[0].obs).toBeNull();
  });

  it("pairs rows whose clocks are close but not equal", () => {
    const esp = [{ ts_epoch: 1000, tinggi_cm: 154.8, mm_per_jam: 0, level: "NORMAL" }];
    const out = joinSeries(esp, [obs(1012, 0.42)]);
    expect(out[0].obs!.coverage).toBeCloseTo(0.42);
  });

  it("carries a null coverage through as null", () => {
    const esp = [{ ts_epoch: 1000, tinggi_cm: 154.8, mm_per_jam: 0, level: "NORMAL" }];
    const out = joinSeries(esp, [obs(1000, null)]);
    expect(out[0].obs!.coverage).toBeNull();
  });
});
