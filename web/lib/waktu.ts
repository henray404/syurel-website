/**
 * How long ago a reading arrived, in Indonesian.
 *
 * The design hardcodes "diperbarui 12 detik lalu". On a real page that line is
 * the only clue that a source has gone quiet, so it has to be computed -- a
 * frozen "12 detik lalu" under a stale number is worse than no line at all.
 */

/** Parses the `ts_utc` written by sink.py (`utc_iso`), e.g. 2026-08-23T08:36:26Z. */
export function parseUtc(ts: string | null | undefined): Date | null {
  if (!ts) return null;
  const d = new Date(ts);
  return Number.isNaN(d.getTime()) ? null : d;
}

/**
 * "baru saja" / "42 detik lalu" / "5 menit lalu" / "2 jam lalu" / "3 hari lalu".
 *
 * Returns null when there is no timestamp, so callers render their own "belum
 * ada data" rather than a bogus duration.
 */
export function formatRelative(
  ts: string | null | undefined,
  now: Date = new Date(),
): string | null {
  const then = parseUtc(ts);
  if (then === null) return null;

  const seconds = Math.floor((now.getTime() - then.getTime()) / 1000);
  // Clock skew between the ESP32 and this laptop can put a reading in the
  // future. "-3 detik lalu" reads as a bug; treat it as just-arrived.
  if (seconds < 10) return "baru saja";
  if (seconds < 60) return `${seconds} detik lalu`;

  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} menit lalu`;

  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} jam lalu`;

  return `${Math.floor(hours / 24)} hari lalu`;
}

/**
 * "dalam 5 jam" -- the forward-looking twin of formatRelative.
 *
 * formatRelative deliberately reports anything in the future as "baru saja",
 * because a sensor timestamp ahead of this laptop's clock is skew, not
 * prophecy. A FORECAST timestamp is legitimately in the future, and running it
 * through that guard rendered "hujan berikutnya: baru saja" for rain due
 * tomorrow -- which reads as if it were already falling.
 */
export function formatUntil(ts: string | null | undefined, now: Date = new Date()): string | null {
  const then = parseUtc(ts);
  if (then === null) return null;

  const seconds = Math.floor((then.getTime() - now.getTime()) / 1000);
  if (seconds <= 0) return "sedang berlangsung";
  if (seconds < 3600) return `dalam ${Math.max(1, Math.round(seconds / 60))} menit`;

  const hours = Math.round(seconds / 3600);
  if (hours < 24) return `dalam ${hours} jam`;

  return `dalam ${Math.round(hours / 24)} hari`;
}

const DAYS = ["Minggu", "Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu"];
const MONTHS = [
  "Januari",
  "Februari",
  "Maret",
  "April",
  "Mei",
  "Juni",
  "Juli",
  "Agustus",
  "September",
  "Oktober",
  "November",
  "Desember",
];

export function formatTanggal(d: Date): string {
  return `${DAYS[d.getDay()]}, ${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}`;
}

export function formatJam(d: Date): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}
