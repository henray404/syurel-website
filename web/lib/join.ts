export type Observation = {
  ts_epoch: number;
  coverage: number | null;
  accumulation_frac: number | null;
  growth_per_min: number | null;
  alert: number | null;
  alert_reason: string | null;
};

export type EspSample = {
  ts_epoch: number;
  tinggi_cm: number | null;
  mm_per_jam: number | null;
  level: string | null;
};

export type Joined = {
  ts_epoch: number;
  esp: EspSample;
  obs: Observation | null;
};

/** ESP logs every 60 s, the camera every 30 s, and neither clock is exact. */
export const DEFAULT_TOLERANCE_S = 60;

/**
 * Closest observation to `tsEpoch`, or null if the nearest one is further away
 * than the tolerance. Exact matching would discard almost every pair.
 */
export function nearestObservation(
  obs: Observation[],
  tsEpoch: number,
  toleranceS: number = DEFAULT_TOLERANCE_S,
): Observation | null {
  let best: Observation | null = null;
  let bestGap = Number.POSITIVE_INFINITY;

  for (const o of obs) {
    const gap = Math.abs(o.ts_epoch - tsEpoch);
    if (gap <= toleranceS && gap < bestGap) {
      best = o;
      bestGap = gap;
    }
  }
  return best;
}

/**
 * One output row per ESP reading. An ESP row with no camera match is KEPT with
 * `obs: null` — water level and rainfall are still real measurements when the
 * camera is down, and dropping them would put holes in the rainfall series.
 */
export function joinSeries(
  esp: EspSample[],
  obs: Observation[],
  toleranceS: number = DEFAULT_TOLERANCE_S,
): Joined[] {
  return esp.map((e) => ({
    ts_epoch: e.ts_epoch,
    esp: e,
    obs: nearestObservation(obs, e.ts_epoch, toleranceS),
  }));
}
