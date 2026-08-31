// Uji 4.4 (2) akurasi/kesesuaian + (3) kecepatan/konsistensi pembaruan.
// Runs against a live `next start` on 127.0.0.1:8000 pointed at a scratch DB.
import { createRequire } from "node:module";
import { writeFileSync } from "node:fs";

// Resolve deps from the web/ install, not from this scratch file's folder.
const require = createRequire(`${process.cwd().replace(/\\/g, "/")}/package.json`);
const Database = require("better-sqlite3");

const BASE = "http://127.0.0.1:8000";
const db = new Database(process.env.SYURELL_DB, { readonly: true });

const COLS = ["ts_utc", "ts_epoch", "jarak_cm", "tinggi_cm", "valid", "n_sampel", "tip_total",
  "tip_menit", "mm_per_jam", "level", "pompa", "time_src", "rssi", "sms_status"];

const results = { akurasi: [], kecepatan: {} };
const ok = (nama, lulus, bukti) => {
  results.akurasi.push({ nama, lulus, bukti });
  console.log(`${lulus ? "LULUS" : "GAGAL"}  ${nama}\n        ${bukti}`);
};

const csv = (r) => COLS.map((c) => (r[c] === null ? "" : r[c])).join(",");
const post = (device, rows) =>
  fetch(`${BASE}/api/ingest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ device, rows: rows.map((c) => ({ csv: c })) }),
  });
const latest = () => fetch(`${BASE}/api/latest`, { cache: "no-store" }).then((r) => r.json());
const count = () => db.prepare("SELECT COUNT(*) n FROM esp_readings").get().n;
const now = () => Math.floor(Date.now() / 1000);
const iso = (epoch) => new Date(epoch * 1000).toISOString().replace(/\.\d+Z$/, "Z");

// ---------------------------------------------------------------- A. AKURASI
const t0 = now();
const kirim = [];
for (let i = 0; i < 5; i++) {
  kirim.push({
    ts_utc: iso(t0 + i), ts_epoch: t0 + i,
    jarak_cm: 118.4 + i, tinggi_cm: 41.6 - i, valid: 1, n_sampel: 9,
    tip_total: 130 + i, tip_menit: i, mm_per_jam: 2.4 * i,
    level: ["AMAN", "SIAGA", "AWAS"][i % 3],
    pompa: i % 2, time_src: "NTP", rssi: -61 - i, sms_status: "OK",
  });
}
const rA1 = await post("UJI44", kirim.map(csv));
const bodyA1 = await rA1.json();

// A1 -- 14 kolom masuk basis data persis seperti dikirim
const beda = [];
for (const k of kirim) {
  const row = db.prepare("SELECT * FROM esp_readings WHERE device=? AND ts_epoch=?")
    .get("UJI44", k.ts_epoch);
  if (!row) { beda.push(`baris ${k.ts_epoch} tidak ada`); continue; }
  for (const c of COLS) {
    const a = row[c], b = k[c];
    const sama = typeof b === "number" ? Math.abs(a - b) < 1e-9 : a === b;
    if (!sama) beda.push(`${k.ts_epoch}.${c}: db=${JSON.stringify(a)} kirim=${JSON.stringify(b)}`);
  }
}
ok("A1 14 kolom CSV tersimpan identik (5 baris x 14 kolom = 70 nilai)",
  beda.length === 0 && bodyA1.inserted === 5,
  `HTTP ${rA1.status}, diterima=${bodyA1.received} disimpan=${bodyA1.inserted}, selisih nilai=${beda.length}${beda.length ? " -> " + beda.slice(0, 3).join("; ") : ""}`);

// A2 -- nilai yang tampil = nilai baris terbaru di basis data
const L = await latest();
const terbaru = db.prepare("SELECT * FROM esp_readings ORDER BY ts_epoch DESC LIMIT 1").get();
const cocok = !!L.esp && L.esp.ts_utc === terbaru.ts_utc &&
  L.esp.tinggi_cm === terbaru.tinggi_cm && L.esp.mm_per_jam === terbaru.mm_per_jam &&
  L.esp.level === terbaru.level;
ok("A2 /api/latest = baris terbaru basis data (ts, tinggi, mm/jam, level)", cocok,
  `API {ts:${L.esp?.ts_utc}, tinggi:${L.esp?.tinggi_cm}, mm/jam:${L.esp?.mm_per_jam}, level:${L.esp?.level}} vs DB {ts:${terbaru.ts_utc}, tinggi:${terbaru.tinggi_cm}, mm/jam:${terbaru.mm_per_jam}, level:${terbaru.level}}`);

// A3 -- "nan" jadi null, bukan 0
const tNan = t0 + 10;
const nanRow = { ...kirim[0], ts_utc: iso(tNan), ts_epoch: tNan,
  jarak_cm: "nan", tinggi_cm: "nan", valid: 0, mm_per_jam: "nan", level: "" };
const rNan = await post("UJI44", [csv(nanRow)]);
const Lnan = await latest();
const html = await fetch(`${BASE}/`, { cache: "no-store" }).then((r) => r.text());
const nolTampil = /0,0\s*cm/.test(html);
ok('A3 pembacaan gagal (nan) -> null di API dan "Tidak terukur" di layar, tidak pernah 0',
  rNan.status === 200 && Lnan.esp.tinggi_cm === null && Lnan.esp.mm_per_jam === null &&
  html.includes("Tidak terukur") && !nolTampil,
  `HTTP ${rNan.status}, API tinggi_cm=${JSON.stringify(Lnan.esp.tinggi_cm)} mm_per_jam=${JSON.stringify(Lnan.esp.mm_per_jam)}, HTML memuat "Tidak terukur"=${html.includes("Tidak terukur")}, memuat "0,0 cm"=${nolTampil}`);

// A4 -- angka di HTML = angka di API (format Indonesia, 1 desimal)
const tFmt = t0 + 20;
const fmtRow = { ...kirim[0], ts_utc: iso(tFmt), ts_epoch: tFmt,
  tinggi_cm: 37.25, mm_per_jam: 12.34, level: "SIAGA" };
await post("UJI44", [csv(fmtRow)]);
const Lf = await latest();
const html2 = await fetch(`${BASE}/`, { cache: "no-store" }).then((r) => r.text());
const harap = { cm: "37,3 cm", mm: "12,3 mm/jam" };
ok("A4 angka di layar = angka di API, format Indonesia 1 desimal",
  Lf.esp.tinggi_cm === 37.25 && html2.includes(harap.cm) && html2.includes(harap.mm),
  `API tinggi=${Lf.esp.tinggi_cm} mm/jam=${Lf.esp.mm_per_jam}; HTML memuat "${harap.cm}"=${html2.includes(harap.cm)}, "${harap.mm}"=${html2.includes(harap.mm)}`);

// A5 -- putusan operator = hitung ulang mandiri dari baris observasi
const obs = db.prepare("SELECT * FROM observations ORDER BY ts_epoch DESC LIMIT 1").get();
const TH = 0.18;
const f = obs.accumulation_frac, g = obs.growth_per_min ?? 0;
const duga = f === null ? "unknown" : (obs.alert === 1 || f >= TH) ? "blocked" : g > 0 ? "watch" : "clear";
const pct = (x) => `${(x * 100).toFixed(1).replace(".", ",")}%`;
ok("A5 putusan + persentase di layar = hitung ulang mandiri dari baris observasi",
  Lf.verdict.state === duga && Lf.verdict.detail.includes(pct(f)) && html2.includes(Lf.verdict.headline),
  `DB accumulation_frac=${f} growth=${g} alert=${obs.alert} -> dugaan "${duga}"; API "${Lf.verdict.state}" (${Lf.verdict.headline}); detail memuat ${pct(f)}=${Lf.verdict.detail.includes(pct(f))}`);

// A6 -- kiriman ulang tidak menggandakan data
const nSebelum = count();
const rUlang = await post("UJI44", kirim.map(csv));
const bUlang = await rUlang.json();
const nSesudah = count();
const Lu = await latest();
ok("A6 kiriman ulang idempoten: tidak ada baris ganda, tampilan tidak berubah",
  rUlang.status === 200 && bUlang.inserted === 0 && nSebelum === nSesudah && Lu.esp.ts_utc === Lf.esp.ts_utc,
  `HTTP ${rUlang.status}, diterima=${bUlang.received} disimpan=${bUlang.inserted}, jumlah baris ${nSebelum} -> ${nSesudah}`);

// A7 -- satu baris rusak menolak seluruh batch, basis data tidak tersentuh
const nPre = count();
const rusak = [csv({ ...kirim[0], ts_utc: iso(t0 + 30), ts_epoch: t0 + 30 }), "2026-08-30T00:00:00Z,1,2,3"];
const rRusak = await post("UJI44", rusak);
const bRusak = await rRusak.json();
const nPost = count();
ok("A7 satu baris rusak -> HTTP 400, tidak ada baris separuh tersimpan",
  rRusak.status === 400 && nPre === nPost,
  `HTTP ${rRusak.status} "${bRusak.error}", jumlah baris ${nPre} -> ${nPost}`);

// A8 -- zona waktu: ts_utc mengandung Z dan cocok dengan ts_epoch
const semua = db.prepare("SELECT ts_utc, ts_epoch FROM esp_readings WHERE device='UJI44'").all();
const salahZona = semua.filter((r) => !r.ts_utc.endsWith("Z") ||
  Math.abs(Date.parse(r.ts_utc) / 1000 - r.ts_epoch) > 1);
ok("A8 seluruh cap waktu UTC eksplisit (akhiran Z) dan konsisten dengan ts_epoch",
  salahZona.length === 0, `${semua.length} baris diperiksa, tidak konsisten=${salahZona.length}`);

// ------------------------------------------------- B. KECEPATAN & KONSISTENSI
const stat = (a) => {
  const s = [...a].sort((x, y) => x - y);
  const q = (p) => s[Math.min(s.length - 1, Math.floor(p * s.length))];
  return {
    n: s.length, min: +s[0].toFixed(1), p50: +q(0.5).toFixed(1),
    p95: +q(0.95).toFixed(1), max: +s[s.length - 1].toFixed(1),
    rata: +(s.reduce((x, y) => x + y, 0) / s.length).toFixed(1),
  };
};

// B1 -- latensi ujung-ke-ujung: kirim ESP32 -> nilai baru terbaca di /api/latest
const e2e = [];
for (let i = 0; i < 30; i++) {
  const ts = now() + 100 + i;
  const row = { ...kirim[0], ts_utc: iso(ts), ts_epoch: ts, tinggi_cm: 50 + i * 0.1 };
  const start = performance.now();
  await post("UJI44", [csv(row)]);
  for (;;) {
    const L2 = await latest();
    if (L2.esp && L2.esp.ts_utc === row.ts_utc) break;
  }
  e2e.push(performance.now() - start);
}
results.kecepatan.e2e_ms = stat(e2e);
console.log("\nB1 latensi ujung-ke-ujung POST /api/ingest -> terbaca di /api/latest (ms)", results.kecepatan.e2e_ms);

// B2 -- waktu tanggap /api/latest pada irama nyata 500 ms, 200 polling
const lat = [], jarak = [];
let gagal = 0, mundur = 0, prevTs = -Infinity, prevWall = null;
for (let i = 0; i < 200; i++) {
  const w = performance.now();
  if (prevWall !== null) jarak.push(w - prevWall);
  prevWall = w;
  try {
    const r = await fetch(`${BASE}/api/latest`, { cache: "no-store" });
    const j = await r.json();
    lat.push(performance.now() - w);
    if (!r.ok) gagal++;
    const ts = j.esp ? Date.parse(j.esp.ts_utc) : prevTs;
    if (ts < prevTs) mundur++;
    prevTs = ts;
  } catch { gagal++; }
  const sisa = 500 - (performance.now() - w);
  if (sisa > 0) await new Promise((r) => setTimeout(r, sisa));
}
results.kecepatan.latest_ms = stat(lat);
results.kecepatan.jeda_polling_ms = stat(jarak);
results.kecepatan.latest_gagal = gagal;
results.kecepatan.latest_mundur = mundur;
console.log("B2 waktu tanggap /api/latest (ms)", results.kecepatan.latest_ms, `gagal=${gagal} cap-waktu-mundur=${mundur}`);
console.log("   jeda antar polling terukur (ms, target 500)", results.kecepatan.jeda_polling_ms);

// B3 -- /api/live/frame pada irama 100 ms, 100 polling
const fr = [];
let frGagal = 0;
for (let i = 0; i < 100; i++) {
  const w = performance.now();
  try {
    const r = await fetch(`${BASE}/api/live/frame`, { cache: "no-store" });
    const b = await r.arrayBuffer();
    if (!r.ok || b.byteLength === 0) frGagal++;
    fr.push(performance.now() - w);
  } catch { frGagal++; }
  const sisa = 100 - (performance.now() - w);
  if (sisa > 0) await new Promise((r) => setTimeout(r, sisa));
}
results.kecepatan.frame_ms = stat(fr);
results.kecepatan.frame_gagal = frGagal;
console.log("B3 waktu tanggap /api/live/frame (ms)", results.kecepatan.frame_ms, `gagal=${frGagal}`);

// B4 -- muat penuh halaman operator (render sisi server), 20 kali
const pg = [];
for (let i = 0; i < 20; i++) {
  const s = performance.now();
  const r = await fetch(`${BASE}/`, { cache: "no-store" });
  await r.text();
  pg.push(performance.now() - s);
}
results.kecepatan.halaman_ms = stat(pg);
console.log("B4 muat halaman operator / (ms)", results.kecepatan.halaman_ms);

results.ringkas = {
  akurasi_lulus: results.akurasi.filter((r) => r.lulus).length,
  akurasi_total: results.akurasi.length,
};
writeFileSync(process.env.OUT_JSON ?? "uji44.json", JSON.stringify(results, null, 2));
console.log(`\n${results.ringkas.akurasi_lulus}/${results.ringkas.akurasi_total} uji akurasi lulus`);
