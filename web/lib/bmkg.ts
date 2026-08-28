import { readFileSync } from "node:fs";
import { resolve } from "node:path";

/**
 * Prakiraan hujan BMKG untuk halaman operator.
 *
 * REGIONAL, BUKAN DI PINTU AIR. BMKG memberi prakiraan 3-jaman untuk satu
 * desa/kelurahan; sel hujan tropis lebarnya 2-5 km. Hujan bisa turun deras di
 * bendungan sementara prakiraan desa menyebut cerah, dan sebaliknya. Angka di
 * sini hanya untuk bersiap-siap -- yang mengukur hujan di lokasi tetap tipping
 * bucket ESP32, dan yang menentukan status pintu air tetap kamera + ultrasonik.
 *
 * ATRIBUSI WAJIB, bukan sopan santun: BMKG mensyaratkan namanya tampil di
 * aplikasi yang menampilkan datanya. Setiap tampilan yang memakai modul ini
 * harus mencantumkan "Sumber: BMKG".
 */
const ENDPOINT = "https://api.bmkg.go.id/publik/prakiraan-cuaca";

/** Di bawah ini gerimis, bukan hujan yang perlu membangunkan operator. */
export const AMBANG_MM = 0.5;

/** Sedekat apa hujan harus datang sebelum halaman memberi peringatan. */
export const WARN_JAM = 6;

/** Prakiraan direvisi tiap 3 jam; layar operator menyegar tiap 30 detik. */
const CACHE_MS = 15 * 60 * 1000;

const TIMEOUT_MS = 8000;

export type TitikHujan = {
  ts_utc: string;
  mm: number;
  desc: string;
  /** Berapa jam lagi dari sekarang. Negatif = blok 3-jaman sedang berjalan. */
  jam: number;
};

export type Prakiraan =
  | { status: "ok"; hujan: TitikHujan | null; mm24: number | null }
  /** `site.adm4` belum diisi -- lihat configs/site_geometry.json. */
  | { status: "mati" }
  | { status: "gagal"; pesan: string };

type Item = {
  utc_datetime?: string;
  tp?: number | null;
  weather_desc?: string;
};

export function adm4(): string | null {
  const dariEnv = process.env.BMKG_ADM4?.trim();
  if (dariEnv) return dariEnv;
  try {
    const teks = readFileSync(
      resolve(process.cwd(), process.env.SYURELL_SITE ?? "../configs/site_geometry.json"),
      "utf8",
    );
    const kode = JSON.parse(teks)?.site?.adm4;
    return typeof kode === "string" && kode.trim() !== "" ? kode.trim() : null;
  } catch {
    return null;
  }
}

/**
 * Titik berhujan paling awal yang belum lewat, dan total 24 jam ke depan.
 *
 * Murni supaya bisa diuji tanpa jaringan. `mm24 === null` berarti tidak ada satu
 * pun blok terbaca -- berbeda dari 0 mm, yang berarti diprakirakan kering.
 */
export function ringkas(
  items: Item[],
  now: Date,
): { hujan: TitikHujan | null; mm24: number | null } {
  let hujan: TitikHujan | null = null;
  let total = 0;
  let n = 0;

  for (const it of items) {
    const ts = it.utc_datetime;
    if (typeof ts !== "string") continue;
    // BMKG mengirim "2026-08-27 16:00:00" -- spasi, tanpa zona. Itu UTC (field
    // local_datetime yang WIB). Dinormalkan sendiri: menyerahkannya ke Date.parse
    // apa adanya berarti bergantung pada penguraian non-ISO, dan salah tafsir
    // zona di sini menggeser peringatan tujuh jam.
    const t = Date.parse(`${ts.trim().replace(" ", "T").replace(/Z?$/, "")}Z`);
    if (!Number.isFinite(t)) continue;

    const jam = (t - now.getTime()) / 3_600_000;
    // Blok 3-jaman yang sedang berjalan masih relevan sampai habis.
    if (jam < -3 || jam > 24) continue;

    const mm = typeof it.tp === "number" ? it.tp : null;
    if (mm === null) continue;
    n += 1;
    total += mm;

    if (mm >= AMBANG_MM && hujan === null) {
      hujan = { ts_utc: ts, mm, desc: it.weather_desc ?? "Hujan", jam };
    }
  }

  return { hujan, mm24: n === 0 ? null : total };
}

let cache: { saat: number; hasil: Prakiraan } | null = null;

export async function prakiraan(now: Date = new Date()): Promise<Prakiraan> {
  const kode = adm4();
  if (kode === null) return { status: "mati" };
  if (cache !== null && Date.now() - cache.saat < CACHE_MS) return cache.hasil;

  let hasil: Prakiraan;
  try {
    const res = await fetch(`${ENDPOINT}?adm4=${encodeURIComponent(kode)}`, {
      signal: AbortSignal.timeout(TIMEOUT_MS),
      cache: "no-store",
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    // data.data[0].cuaca adalah array berisi array blok cuaca.
    const blocks: Item[][] = data?.data?.[0]?.cuaca ?? [];
    hasil = { status: "ok", ...ringkas(blocks.flat(), now) };
  } catch (err) {
    // Prakiraan tidak boleh menjatuhkan halaman: sensor di lokasi yang menjaga
    // pintu air, ini cuma ancang-ancang.
    hasil = { status: "gagal", pesan: err instanceof Error ? err.message : String(err) };
  }

  cache = { saat: Date.now(), hasil };
  return hasil;
}

/** "2 jam lagi" / "sedang berlangsung". */
export function kapan(jam: number): string {
  if (jam <= 0) return "sedang berlangsung";
  if (jam < 1) return `${Math.max(1, Math.round(jam * 60))} menit lagi`;
  return `${Math.round(jam)} jam lagi`;
}
