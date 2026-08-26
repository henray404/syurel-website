import type { Latest } from "./latest";
import type { Verdict } from "./verdict";
import { formatCoverage } from "./verdict";
import { formatRelative, parseUtc } from "./waktu";

/**
 * The notification rail.
 *
 * The design ships three hardcoded lines ("Batch ESP32 tersimpan — 60 baris").
 * Everything here is derived from the same rows the cards are drawn from: an
 * invented notification is worse than an empty rail, because the operator has
 * no way to tell the two apart.
 */
export type Notif = {
  /** Matches the banner palette in globals.css. */
  color: "blocked" | "watch" | "clear" | "unknown";
  text: string;
  time: string;
};

/** Past this, a source counts as quiet rather than merely between samples. */
export const STALE_AFTER_MINUTES = 20;

function ageMinutes(ts: string | null | undefined, now: Date): number | null {
  const then = parseUtc(ts);
  if (then === null) return null;
  return (now.getTime() - then.getTime()) / 60000;
}

export function buildNotifications(
  latest: Latest,
  v: Verdict,
  now: Date = new Date(),
): Notif[] {
  const out: Notif[] = [];

  if (v.state === "blocked") {
    out.push({
      color: "blocked",
      text: v.detail,
      time: formatRelative(latest.obs?.ts_utc, now) ?? "waktu tidak diketahui",
    });
  } else if (v.state === "watch") {
    out.push({
      color: "watch",
      text: `Penumpukan naik ke ${formatCoverage(latest.obs?.accumulation_frac ?? null)}`,
      time: formatRelative(latest.obs?.ts_utc, now) ?? "waktu tidak diketahui",
    });
  }

  const espAge = ageMinutes(latest.esp?.ts_utc, now);
  if (latest.esp === null) {
    out.push({ color: "watch", text: "Belum ada data dari ESP32", time: "—" });
  } else if (espAge !== null && espAge > STALE_AFTER_MINUTES) {
    out.push({
      color: "watch",
      text: "ESP32 berhenti mengirim data",
      time: formatRelative(latest.esp.ts_utc, now) ?? "—",
    });
  } else {
    out.push({
      color: "clear",
      text: `Data sensor masuk — tinggi air ${latest.esp.tinggi_cm ?? "?"} cm`,
      time: formatRelative(latest.esp.ts_utc, now) ?? "—",
    });
  }

  const obsAge = ageMinutes(latest.obs?.ts_utc, now);
  if (latest.obs === null) {
    out.push({
      color: "unknown",
      text: "Kamera belum mengirim data. Jalankan inference.run.",
      time: "—",
    });
  } else if (obsAge !== null && obsAge > STALE_AFTER_MINUTES) {
    out.push({
      color: "watch",
      text: "Kamera berhenti mengirim data",
      time: formatRelative(latest.obs.ts_utc, now) ?? "—",
    });
  }

  return out;
}
