import type { Observation } from "./join";

export type Verdict = {
  state: "unknown" | "clear" | "watch" | "blocked";
  headline: string;
  detail: string;
  /** Minutes until accumulation reaches the threshold, when it is climbing. */
  minutesToThreshold: number | null;
};

/** Matches blockage.area_threshold in configs/inference/site_bendungan.yaml. */
export const DEFAULT_AREA_THRESHOLD = 0.18;

/**
 * A fraction as Indonesian percent, or the words for "not measured".
 *
 * Never returns "0%" for null. metrics.py returns None rather than 0.0 on
 * purpose: 0.0 reads as "clean river", which is the wrong thing to show during
 * a flood.
 */
export function formatCoverage(v: number | null): string {
  if (v === null || !Number.isFinite(v)) return "tidak terukur";
  return `${(v * 100).toFixed(1).replace(".", ",")}%`;
}

export function verdict(
  obs: Observation | null,
  areaThreshold: number = DEFAULT_AREA_THRESHOLD,
): Verdict {
  if (obs === null || obs.accumulation_frac === null) {
    return {
      state: "unknown",
      headline: "Belum ada pengukuran",
      detail: "Kamera tidak mengirim data. Periksa kondisi di lokasi secara langsung.",
      minutesToThreshold: null,
    };
  }

  const frac = obs.accumulation_frac;
  const growth = obs.growth_per_min ?? 0;

  if (obs.alert === 1 || frac >= areaThreshold) {
    return {
      state: "blocked",
      headline: "Bersihkan dulu sebelum membuka pintu",
      detail: obs.alert_reason?.trim()
        ? obs.alert_reason
        : `Penumpukan ${formatCoverage(frac)} sudah mencapai ambang ${formatCoverage(areaThreshold)}.`,
      minutesToThreshold: null,
    };
  }

  if (growth > 0) {
    const minutes = (areaThreshold - frac) / growth;
    return {
      state: "watch",
      headline: "Penumpukan sedang bertambah",
      detail: `Sekarang ${formatCoverage(frac)}, naik ${formatCoverage(growth)} per menit.`,
      minutesToThreshold: minutes,
    };
  }

  return {
    state: "clear",
    headline: "Aman membuka pintu",
    detail: `Penumpukan ${formatCoverage(frac)}, di bawah ambang ${formatCoverage(areaThreshold)}.`,
    minutesToThreshold: null,
  };
}
