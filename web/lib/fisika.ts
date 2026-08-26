import { readFileSync } from "node:fs";
import path from "node:path";

/**
 * Afflux, for display. MIRRORS src/physics.py -- change one, change the other.
 *
 * Both sides exist for a reason: Python owns the miniature-experiment analysis
 * (docs/eksperimen_miniatur.md), the web owns what the operator is told. Sharing
 * one implementation would mean shelling out to Python on every request, which
 * is slower and fails in more ways than forty lines of arithmetic.
 * tests/fisika.test.ts and tests/test_physics.py assert the same numbers.
 *
 * THE LAW, from rencana_penelitian.md 5.9:
 *
 *     h_tersumbat / h_bersih = 1 / (1 - BF)^2
 *
 * Dimensionless on both sides, which is why an 80 cm model can validate the same
 * relationship as a real barrage.
 *
 * SOURCES: docs/referensi_fisika.md. Two things that page settles and this
 * comment used to get wrong:
 *
 *   - Floating debris really does block a bottom-opening gate. Mohammed (2022)
 *     measured a 15% rise in upstream depth from driftwood accumulation.
 *   - Shrinking the area is ARR's Reduced Area Method, which ARR says
 *     exaggerates head for blockage at the ENTRANCE (28% high in their worked
 *     50%-blockage example). So what this file computes is an UPPER BOUND, and
 *     the page must label it as one.
 */
export const G = 9.81;

/** Past this the model stops describing water and runs to infinity. */
export const BF_MAX_TRUSTED = 0.85;

export type Gate = {
  b_m: number;
  a_m: number;
  Cd: number;
  h_bersih_m: number;
  z_jalan_m: number;
};

export type SiteGeometry = {
  gate: Gate;
  bias: number;
  skala: number;
  calibrated: boolean;
  lat: number | null;
  lon: number | null;
  adm4: string | null;
};

export type Fisika = {
  bf: number | null;
  beyondModel: boolean;
  affluxRatio: number | null;
  affluxM: number | null;
  headM: number | null;
  headBersihM: number;
  dischargeBersih: number | null;
  dischargeTersumbat: number | null;
  criticalBf: number | null;
  marginToRoadM: number | null;
  zJalanM: number;
  calibrated: boolean;
};

export const SITE_PATH =
  process.env.SYURELL_SITE ?? path.join(process.cwd(), "..", "configs", "site_geometry.json");

export function loadSite(file: string = SITE_PATH): SiteGeometry {
  const cfg = JSON.parse(readFileSync(file, "utf-8"));
  const g = cfg.gate ?? {};
  const k = cfg.kalibrasi_kamera ?? {};
  const s = cfg.site ?? {};
  return {
    gate: {
      b_m: Number(g.b_m),
      a_m: Number(g.a_m),
      Cd: Number(g.Cd),
      h_bersih_m: Number(g.h_bersih_m),
      z_jalan_m: Number(g.z_jalan_m),
    },
    bias: Number(k.bias ?? 0),
    skala: Number(k.skala ?? 1),
    // Anything but an explicit CALIBRATED counts as uncalibrated: defaulting the
    // other way would let a missing field promote guesses to measurements.
    calibrated: String(cfg.status ?? "").toUpperCase() === "CALIBRATED",
    lat: s.lat ?? null,
    lon: s.lon ?? null,
    adm4: s.adm4 ?? null,
  };
}

/** Camera fraction -> blockage factor, with the experiment-E2 calibration. */
export function blockageFactor(frac: number | null, site: SiteGeometry): number | null {
  // null in, null out. A missing measurement must never become 0 here: 0 means
  // "the gate is clear", the most dangerous thing this could invent.
  if (frac === null || frac === undefined || !Number.isFinite(frac)) return null;
  return Math.min(1, Math.max(0, site.skala * frac + site.bias));
}

export function affluxRatio(bf: number | null): number | null {
  if (bf === null || bf >= BF_MAX_TRUSTED) return null;
  return 1 / (1 - bf) ** 2;
}

export function criticalBf(site: SiteGeometry): number | null {
  const { h_bersih_m: h0, z_jalan_m: z } = site.gate;
  if (!(h0 > 0) || !(z > 0) || z <= h0) return null;
  return 1 - Math.sqrt(h0 / z);
}

function discharge(head: number, site: SiteGeometry, bf: number): number | null {
  const area = site.gate.b_m * site.gate.a_m * (1 - bf);
  if (!(area > 0) || !(head > 0)) return null;
  return site.gate.Cd * area * Math.sqrt(2 * G * head);
}

export function fisika(frac: number | null, site: SiteGeometry): Fisika {
  const bf = blockageFactor(frac, site);
  const ratio = affluxRatio(bf);
  const h0 = site.gate.h_bersih_m;
  const head = ratio === null ? null : h0 * ratio;

  return {
    bf,
    beyondModel: bf !== null && bf >= BF_MAX_TRUSTED,
    affluxRatio: ratio,
    affluxM: ratio === null ? null : h0 * (ratio - 1),
    headM: head,
    headBersihM: h0,
    // Capacity at an UNCHANGED level, not at the afflux head: the discharge at
    // the afflux head is algebraically identical to the clear-gate discharge --
    // that is what afflux means -- so showing it would print one number twice.
    dischargeBersih: discharge(h0, site, 0),
    dischargeTersumbat: bf === null ? null : discharge(h0, site, bf),
    criticalBf: criticalBf(site),
    marginToRoadM: head === null ? null : site.gate.z_jalan_m - head,
    zJalanM: site.gate.z_jalan_m,
    calibrated: site.calibrated,
  };
}

/** Metres as cm with an Indonesian decimal comma, or the words for absence. */
export function formatCm(m: number | null): string {
  if (m === null || !Number.isFinite(m)) return "tidak terukur";
  return `${Math.round(m * 100)} cm`;
}
