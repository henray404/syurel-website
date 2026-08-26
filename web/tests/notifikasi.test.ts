import { describe, expect, it } from "vitest";
import { buildNotifications } from "../lib/notifikasi";
import type { Latest } from "../lib/latest";
import { verdict } from "../lib/verdict";

const NOW = new Date("2026-08-23T12:00:00Z");

const esp = {
  ts_utc: "2026-08-23T11:58:00Z",
  tinggi_cm: 154.8,
  mm_per_jam: 4.8,
  level: "NORMAL",
};

function obs(frac: number | null, extra: Record<string, unknown> = {}) {
  return {
    ts_utc: "2026-08-23T11:59:00Z",
    ts_epoch: 1787486340,
    coverage: frac,
    accumulation_frac: frac,
    growth_per_min: 0,
    alert: 0,
    alert_reason: "",
    ...extra,
  } as Latest["obs"];
}

describe("buildNotifications", () => {
  it("leads with the alarm when the gate is blocked", () => {
    const latest: Latest = { esp, obs: obs(0.24, { alert: 1, alert_reason: "ambang penumpukan" }) };
    const out = buildNotifications(latest, verdict(latest.obs), NOW);
    expect(out[0].color).toBe("blocked");
    expect(out[0].text).toBe("ambang penumpukan");
  });

  it("says the camera is silent rather than inventing a reading", () => {
    const latest: Latest = { esp, obs: null };
    const out = buildNotifications(latest, verdict(null), NOW);
    const camera = out.find((n) => n.text.includes("Kamera"));
    expect(camera?.color).toBe("unknown");
    // Never a number here: an absent camera must not look like a measurement.
    expect(camera?.text).not.toMatch(/\d+%/);
  });

  it("flags a source that has gone quiet past the stale window", () => {
    const stale: Latest = { esp: { ...esp, ts_utc: "2026-08-23T11:00:00Z" }, obs: obs(0.05) };
    const out = buildNotifications(stale, verdict(stale.obs), NOW);
    expect(out.some((n) => n.text === "ESP32 berhenti mengirim data")).toBe(true);
  });

  it("reports a healthy sensor with its real height", () => {
    const latest: Latest = { esp, obs: obs(0.05) };
    const out = buildNotifications(latest, verdict(latest.obs), NOW);
    expect(out.some((n) => n.color === "clear" && n.text.includes("154.8 cm"))).toBe(true);
  });

  it("never returns an empty rail, even with nothing stored", () => {
    const out = buildNotifications({ esp: null, obs: null }, verdict(null), NOW);
    expect(out.length).toBeGreaterThan(0);
  });
});
