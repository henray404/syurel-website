# Web monitoring — desain

Tanggal: 2026-08-20

Web yang menyatukan tiga aliran data yang selama ini terpisah: sensor ESP32,
hasil segmentasi kamera, dan metrik turunannya. Satu aplikasi, tiga halaman,
tiga pembaca yang berbeda.

Dokumen terkait:
[`rencana_penelitian.md`](../../rencana_penelitian.md) ·
[`2026-08-15-esp32-logging-design.md`](2026-08-15-esp32-logging-design.md) ·
[`../../../configs/inference/site_bendungan.yaml`](../../../configs/inference/site_bendungan.yaml)

---

## 1. Kenapa ini perlu dibangun sekarang

Bukan sekadar dashboard. **Firmware ESP32 sudah menunggu server ini.**

`firmware/esp32/include/hw_upload.h` mengirim POST ke `INGEST_URL` dan hanya
memajukan kursor SD-nya setelah server membalas 2xx:

```c
// Advance only on an explicit 2xx. Anything else leaves the cursor alone so
// the same rows are retried.
if (code >= 200 && code < 300) { writeCursor(newCursor); return count; }
```

Selama endpoint itu tidak ada, ESP menumpuk baris di SD tanpa pernah
menyelesaikan pengiriman. Jadi web ini **wajib** punya sisi penerima, bukan
hanya penampil. Itu yang menaikkan ini dari "dashboard" jadi subsistem.

---

## 2. Keputusan arsitektur

**Next.js memegang seluruh sisi web. Python tetap hanya mengurus inferensi.**

```
ESP32  --POST /api/ingest-->  Next.js  --tulis-->  esp_readings
                                 |
inferensi Python  --tulis-->  observations  --baca-->  Next.js
                                                          |
                                                     halaman web
```

Akses SQLite dari Node lewat `better-sqlite3`.

### Yang ditolak, dan alasannya

| ditolak | alasan |
|---|---|
| **FastAPI sebagai lapisan data, Next.js frontend saja** | Lebih aman secara teori (satu bahasa yang menulis SQLite), tapi memaksa dua proses berjalan bersamaan plus konfigurasi proxy — selamanya |
| **Basis data terpisah per sumber** | Tidak ada rebutan tulis, tapi penggabungan berdasarkan `ts_utc` jadi lintas-basis-data. Itu justru operasi yang paling sering dipakai |
| **Tambah tab di GUI Gradio** | Paling cepat, tapi tata letaknya terkunci komponen Gradio — rancangan Claude Design tidak bisa diterapkan |

### Soal konkurensi, dengan angka

Kekhawatiran dua penulis pada satu berkas SQLite itu nyata tapi kecil di sini:

- ESP menulis **1 baris/menit**
- Inferensi menulis **1 baris/30 detik** (`trash_interval_s: 30.0`)
- Keduanya menulis **tabel yang berbeda**

Dengan mode WAL, SQLite mengizinkan satu penulis dan banyak pembaca bersamaan.
Pada laju sejarang ini, tumbukan praktis tidak terjadi.

**Perubahan yang dibutuhkan di kode yang sudah jalan:** `src/inference/sink.py`
belum mengaktifkan WAL. Tambahkan satu pernyataan setelah `sqlite3.connect`:

```python
self._conn.execute("PRAGMA journal_mode=WAL")
```

Tanpa itu, pembacaan dari Node dapat memblokir penulisan Python. Ini
satu-satunya sentuhan ke kode Python yang sudah berjalan.

---

## 3. Kontrak ingest ESP32

Diambil langsung dari `hw_upload.h`, bukan dirancang ulang — firmware sudah
mengirim bentuk ini.

**Request:**

```
POST /api/ingest
Content-Type: application/json
```

```json
{
  "device": "esp32-01",
  "rows": [
    { "csv": "2026-08-20T10:30:00Z,1787654321,45.2,154.8,1,12,340,2,4.8,NORMAL,0,ntp,-67,ok" },
    { "csv": "2026-08-20T10:31:00Z,1787654381,45.0,155.0,1,12,341,1,2.4,NORMAL,0,ntp,-65,ok" }
  ]
}
```

Baris dikirim sebagai **string CSV mentah di dalam JSON**, bukan objek
ber-field. Endpoint harus mem-parse-nya memakai urutan kolom dari
`firmware/esp32/include/logic_csv.h`:

```
ts_utc, ts_epoch, jarak_cm, tinggi_cm, valid, n_sampel, tip_total,
tip_menit, mm_per_jam, level, pompa, time_src, rssi, sms_status
```

Firmware juga melewati baris header bila ikut terkirim (`line.startsWith("ts_utc")`),
tetapi endpoint tetap harus menanganinya sendiri — jangan mengandalkan itu.

**Aturan respons yang tidak boleh dilanggar:**

- Balas **2xx hanya jika semua baris benar-benar tersimpan**. Balasan 2xx
  membuat ESP membuang jejaknya — kursor maju dan baris itu tidak akan dikirim
  ulang selamanya.
- Balas **non-2xx pada kegagalan apa pun**. ESP akan mengirim ulang baris yang
  sama. Itu perilaku yang diinginkan, bukan masalah.
- **Idempoten wajib.** Pengiriman ulang adalah kejadian normal (mati listrik
  saat menulis kursor, respons hilang di jaringan). Kunci unik
  `(device, ts_epoch)` dengan `INSERT OR IGNORE` menyelesaikannya.

**Catatan konfigurasi:** `config_secrets.h.example` menulis
`INGEST_URL "http://your-server:8000/ingest"` — port 8000 dan path `/ingest`,
sedangkan Next.js default 3000 dengan konvensi `/api/ingest`. Keduanya harus
diselaraskan: jalankan Next di port 8000 dan sediakan route di `/ingest`, atau
ubah `INGEST_URL` saat menulis `config_secrets.h`.

---

## 4. Model data

Satu berkas SQLite, satu tabel yang sudah ada + satu tabel baru.

### `observations` — sudah ada, ditulis Python

Dibuat oleh `src/inference/sink.py`, 20 kolom:

```
ts_utc, ts_epoch, site, frame_idx,
coverage, coverage_smoothed,
debris_px, water_px, roi_px,
accumulation_px, accumulation_frac,
velocity_px_s, n_flow_vectors,
area_flux, flux_units, is_metric,
growth_per_min, alert, alert_reason,
water_mask_age_s
```

Next.js hanya **membaca** tabel ini. Tidak pernah menulis.

### `esp_readings` — baru, ditulis Next.js

```sql
CREATE TABLE IF NOT EXISTS esp_readings (
  device      TEXT    NOT NULL,
  ts_utc      TEXT    NOT NULL,
  ts_epoch    INTEGER NOT NULL,
  jarak_cm    REAL,
  tinggi_cm   REAL,
  valid       INTEGER,
  n_sampel    INTEGER,
  tip_total   INTEGER,
  tip_menit   INTEGER,
  mm_per_jam  REAL,
  level       TEXT,
  pompa       INTEGER,
  time_src    TEXT,
  rssi        INTEGER,
  sms_status  TEXT,
  PRIMARY KEY (device, ts_epoch)
);
```

Primary key gabungan itulah yang membuat pengiriman ulang aman.

### Penggabungan

Keduanya membawa `ts_utc` dalam **ISO-8601 UTC**, dan itu disengaja.
`sink.py` mencatat alasannya: Asia/Jakarta adalah UTC+7, sehingga waktu lokal
akan menggeser korelasi dengan data hujan **tujuh jam tanpa ketahuan**.

Penggabungan dilakukan pada `ts_epoch` dengan toleransi, bukan kecocokan
persis: ESP mencatat tiap menit, kamera tiap 30 detik, dan jam keduanya tidak
tersinkron sempurna. Ambil observasi kamera terdekat dalam jendela ±60 detik.

---

## 5. Halaman

Fondasinya (ingest, penyimpanan, API) sama untuk ketiganya. Yang bercabang
hanya tampilan.

### `/` — Operator

Kondisi **sekarang**. Dipelototi saat bertugas, dibaca sekilas dari jarak
beberapa meter.

- Status besar: tinggi air, curah hujan, persentase blockage
- Keadaan alarm dan alasannya (`alert`, `alert_reason`)
- Jawaban satu baris: **aman membuka pintu, atau bersihkan dulu**
- Waktu-ke-kritis bila `growth_per_min` positif
- Refresh tiap 30 detik

Angka besar, warna tegas, hampir tanpa grafik.

### `/analisis` — Penelitian

Deret waktu dan hubungan antar-variabel. Ini yang melayani OPSI-nya.

- Grafik bertumpuk pada sumbu waktu yang sama: hujan, tinggi air, blockage
- Rentang waktu dapat dipilih
- Sebar-titik afflux terhadap `1/(1−BF)²` — pengujian `h ∝ 1/A²`
- Korelasi silang hujan → kedatangan sampah (mencari `τ*`)
- Ekspor CSV rentang terpilih

### `/demo` — Presentasi

Dibuka saat sidang atau pameran. Harus meyakinkan dalam 30 detik.

- Alur: foto mentah → mask segmentasi → angka → keputusan
- Kejadian penyumbatan terpilih sebagai studi kasus
- Perbandingan model (0,7313 debris) beserta konteksnya

**Urutan pengerjaan:** `/` dulu (paling sederhana, sekaligus membuktikan alur
data lengkap), lalu `/analisis` (paling bernilai untuk laporan), `/demo`
terakhir (paling bergantung pada data nyata yang belum terkumpul).

---

## 6. Permukaan API

| route | metode | fungsi |
|---|---|---|
| `/api/ingest` | POST | Terima baris ESP. Satu-satunya endpoint tulis |
| `/api/latest` | GET | Baris terbaru dari kedua tabel, untuk halaman operator |
| `/api/series` | GET | Deret waktu tergabung dalam rentang. Parameter `from`, `to`, `bucket` |
| `/api/events` | GET | Kejadian alarm untuk studi kasus |
| `/api/export` | GET | Unduh CSV rentang terpilih |

---

## 7. Penanganan kesalahan

Yang harus benar, dan konsekuensinya bila salah:

| kondisi | perilaku |
|---|---|
| CSV cacat di satu baris | Tolak **seluruh batch** dengan non-2xx. Menerima sebagian lalu membalas 2xx akan membuat ESP membuang baris yang gagal |
| Baris duplikat | `INSERT OR IGNORE`, tetap balas 2xx. Ini bukan kesalahan |
| SQLite terkunci | Coba lagi singkat, lalu non-2xx bila tetap gagal. ESP akan mengirim ulang |
| `out/timeseries.sqlite` belum ada | Halaman tetap tampil; bagian kamera menunjukkan "belum ada data", bukan galat |
| `coverage` bernilai `null` | Tampilkan "tidak terukur", **jangan** tampilkan 0 |

Baris terakhir itu penting. `metrics.py` sengaja mengembalikan `None`, bukan
0,0, dengan alasan yang tertulis di sana: nilai 0,0 terbaca "sungai bersih",
dan itu justru salah fatal saat banjir. Menampilkan 0 di web akan mengulang
persis kesalahan yang sudah dicegah di sisi Python.

---

## 8. Pengujian

- **Parser CSV**: baris nyata dari `logic_csv.h`, termasuk baris cacat dan
  header yang ikut terkirim
- **Idempotensi ingest**: kirim batch yang sama dua kali; jumlah baris tidak
  bertambah dan respons tetap 2xx
- **Kontrak respons**: batch gagal harus non-2xx — ini yang menjaga data ESP
  tidak hilang
- **Penggabungan**: cap waktu yang tidak sejajar harus tergabung dalam jendela
  toleransi, bukan terbuang
- **`coverage` null**: tidak boleh dirender sebagai 0

---

## 9. Yang berada di luar cakupan

Sengaja tidak dikerjakan sekarang:

- **Autentikasi** — jalan di laptop, jaringan lokal
- **Penempatan di Pi** — laptop dulu; keputusan lokasi menunggu jawaban `H2`
  di panduan wawancara (listrik dan internet di lokasi)
- **Peringatan lewat WhatsApp/SMS** — firmware sudah punya jalur SMS sendiri
- **Streaming video langsung** — inferensi menulis metrik, bukan video
- **Multi-lokasi** — satu bendungan
- **Menjalankan model dari web** — GUI Gradio sudah melayani itu

---

## 10. Risiko dan catatan terbuka

| hal | catatan |
|---|---|
| **Model Pi-capable** | Pertanyaan Fase 4, bukan penghalang web. `docs/model_comparison.md` mengukur SegFormer-B0 5,8× lebih lambat dari LR-ASPP di 512, dan menyebut Pi 5 kira-kira sepuluh kali lebih lambat dari mesin uji. Tapi `trash_interval_s: 30.0` memberi kelonggaran besar — ekstrapolasi kasar menempatkan SegFormer@640 di sekitar 10 detik per frame, masih muat. **Itu ekstrapolasi, bukan pengukuran**: dokumen itu sendiri meminta `python -m bench.cost` dijalankan di Pi dengan `is_target_device: true` sebelum mengunci pilihan. Cadangan bila tidak muat: `lraspp_mnv3`, yang paling tahan penurunan resolusi (rugi 7,6% di 416) |
| **Data lokasi belum ada** | Belum ada rekaman dari bendungan. Sampai ada, halaman diisi data uji atau data publik. Halaman `/demo` paling terdampak |
| **Ketidakcocokan port dan path** | `INGEST_URL` contoh memakai port 8000 dan path `/ingest`; Next.js default 3000 dengan `/api/ingest`. Harus diselaraskan saat menulis `config_secrets.h` |
| **Ambang `area_threshold`** | Nilai sekarang `0.18` masih tebakan berdasar penalaran fisik. Web hanya menampilkannya; kalibrasinya menunggu data semusim |
| **Rancangan visual** | Dikerjakan terpisah di Claude Design. Spec ini menetapkan data dan perilaku, bukan tampilan |
