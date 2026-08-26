# 5. Skema Basis Data dan Dokumentasi API

[← Daftar isi](README.md) · [← Sebelumnya: Spesifikasi](04-spesifikasi.md)

---

## 5.1 Berkas basis data

| | |
|---|---|
| Mesin | SQLite 3, mode **WAL** |
| Berkas produksi | `out/<site>/timeseries.sqlite` |
| Berkas yang dibaca web | `../out/webcam/timeseries.sqlite` (bawaan) |
| Peubah lingkungan | `SYURELL_DB` untuk menimpa |
| Penulis | `src/inference/sink.py`, `web/lib/ingest.ts`, `src/external/rainfall.py` |
| Pembaca | `web/lib/*.ts` |

Satu berkas per **site**. Nama site datang dari konfigurasi inferensi
(`site: webcam`), sehingga data uji meja tidak pernah bisa tercampur dengan data
bendungan.

> **Ketidakcocokan yang masih ada di dokumen lain:** `web/README.md` menyebut
> `../out/timeseries.sqlite`. Yang benar adalah `web/lib/db.ts:15`,
> `../out/webcam/timeseries.sqlite`. READMEnya yang salah. Ini pernah
> menyebabkan halaman menampilkan kamera hidup di atas angka yang dibaca dari
> berkas yang tidak ada: gambar bergerak, tiap bacaan "tidak terukur".

---

## 5.2 Tabel `esp_readings`

Satu baris per menit tercatat dari satu perangkat ESP32.

```sql
CREATE TABLE esp_readings (
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
CREATE INDEX idx_esp_ts ON esp_readings(ts_epoch);
```

| Kolom | Tipe | Satuan | Arti | Boleh NULL |
|---|---|---|---|---|
| `device` | TEXT | — | `DEVICE_ID` dari `config_secrets.h`, mis. `esp32-XX` | tidak |
| `ts_utc` | TEXT | — | ISO 8601 UTC, `2026-01-01T00:00:00Z` | tidak |
| `ts_epoch` | INTEGER | detik | Waktu Unix, dasar semua penggabungan | tidak |
| `jarak_cm` | REAL | cm | Jarak muka sensor → muka air (median 5 ping) | **ya** |
| `tinggi_cm` | REAL | cm | `JARAK_DASAR − jarak_cm` | **ya** |
| `valid` | INTEGER | 0/1 | Apakah bacaan ultrasonik sah | ya |
| `n_sampel` | INTEGER | — | Jumlah bacaan sah di balik `tinggi_cm` — **kualitas data di dalam rekaman** | ya |
| `tip_total` | INTEGER | — | Penghitung tip kumulatif sejak boot | ya |
| `tip_menit` | INTEGER | — | Tip pada menit itu | ya |
| `mm_per_jam` | REAL | mm/jam | Hujan 60 menit terakhir (jumlah 60 bin, **bukan** ekstrapolasi) | ya |
| `level` | TEXT | — | `AMAN` \| `WASPADA` \| `BAHAYA` | ya |
| `pompa` | INTEGER | 0/1 | Keadaan relai | ya |
| `time_src` | TEXT | — | `ntp` \| `rtc` \| `none` — asal jam untuk baris ini | ya |
| `rssi` | INTEGER | dBm | Kekuatan sinyal WiFi | ya |
| `sms_status` | TEXT | — | Hasil kirim SMS terakhir | ya |

### Tiga keputusan skema yang layak dijelaskan

**Kunci utama `(device, ts_epoch)`, bukan `id` otomatis.** Inilah yang membuat
pengiriman ulang aman: `INSERT OR IGNORE` pada baris yang sudah ada tidak
melakukan apa pun. Firmware mengirim ulang setiap kali tanggapan hilang, dan
tanggapan hilang tidak bisa dibedakan dari permintaan yang tidak pernah sampai.

**`n_sampel` disimpan, bukan dibuang.** Ia bukan angka pengukuran, melainkan
kualitas pengukuran. Justru kolom inilah yang mengungkap bug ultrasonik yang
masih terbuka: `n_sampel = 0` di seluruh 25 baris berarti tidak ada satu pun
sampel sah di balik `tinggi_cm`. Tanpa kolom ini, `tinggi_cm = 0.0` akan terbaca
sebagai "air setinggi nol", bukan "tidak ada pengukuran".

**Laju perubahan tidak disimpan.** Komentar di `logic_csv.h` menyatakannya:
laju naik, percepatan, dan jarak-ke-ambang semuanya bisa dihitung ulang dari
deret ini. Menyimpannya akan merusak keterbandingan dengan data yang sudah
terkumpul begitu pilihan jendela atau penghalusan berubah.

---

## 5.3 Tabel `observations`

Satu baris per bingkai yang disegmentasi.

```sql
CREATE TABLE observations (
  ts_utc TEXT, ts_epoch REAL, site TEXT, frame_idx INTEGER,
  coverage REAL, coverage_smoothed REAL,
  debris_px INTEGER, water_px INTEGER, roi_px INTEGER,
  accumulation_px INTEGER, accumulation_frac REAL,
  velocity_px_s REAL, n_flow_vectors INTEGER,
  area_flux REAL, flux_units TEXT, is_metric INTEGER,
  growth_per_min REAL, alert INTEGER, alert_reason TEXT,
  water_mask_age_s REAL
);
CREATE INDEX idx_obs_site_ts ON observations(site, ts_epoch);
```

| Kolom | Satuan | Arti |
|---|---|---|
| `site` | — | Nama lokasi dari konfigurasi. Memisahkan uji meja dari data lapangan |
| `frame_idx` | — | Nomor bingkai sejak proses mulai |
| `coverage` | 0..1 | `(debris+clump) / (debris+clump+water)` di dalam ROI |
| `coverage_smoothed` | 0..1 | Median bergulir atas `coverage` |
| `debris_px`, `water_px`, `roi_px` | piksel | Hitungan mentah — memungkinkan hitung ulang tanpa bingkai aslinya |
| `accumulation_px` | piksel | Piksel sampah di dalam poligon **zona pintu** |
| `accumulation_frac` | 0..1 | Fraksi zona pintu yang tertutup. **Ini masukan ke fisika** |
| `velocity_px_s` | px/detik | Kecepatan permukaan dari aliran optik |
| `n_flow_vectors` | — | Jumlah vektor aliran; nol berarti kecepatan tidak terukur |
| `area_flux` | lihat `flux_units` | Fluks luas sampah |
| `flux_units` | — | `m2_per_s` bila homografi terkalibrasi, `relative_index` bila tidak |
| `is_metric` | 0/1 | **0 berarti angka fluks bukan besaran fisik** |
| `growth_per_min` | 1/menit | Laju pertumbuhan `accumulation_frac` |
| `alert` | 0/1 | Peringatan penyumbatan aktif |
| `alert_reason` | — | Alasan yang bisa dibaca manusia |
| `water_mask_age_s` | detik | Umur mask air yang di-cache saat bingkai ini diukur |

`is_metric` dan `flux_units` ada supaya tidak ada angka yang berpura-pura jadi
m²/detik saat homografi belum dikalibrasi. Pada seluruh data yang ada sekarang
`is_metric = 0`.

---

## 5.4 Tabel `rainfall`

Curah hujan dari API luar. **Bukan** dari tipping bucket — yang itu ada di
`esp_readings.mm_per_jam`.

```sql
CREATE TABLE rainfall (
  source        TEXT    NOT NULL,
  ts_utc        TEXT    NOT NULL,
  ts_epoch      INTEGER NOT NULL,
  mm            REAL,
  interval_s    INTEGER NOT NULL,
  kind          TEXT    NOT NULL,
  fetched_epoch REAL    NOT NULL,
  PRIMARY KEY (source, ts_epoch)
);
CREATE INDEX idx_rain_ts ON rainfall(ts_epoch);
```

| Kolom | Arti |
|---|---|
| `source` | `open-meteo-archive` \| `open-meteo-forecast` \| `bmkg` |
| `mm` | Curah hujan pada selang itu |
| `interval_s` | Panjang selang dalam detik — 3600 dan 10800 punya arti berbeda |
| `kind` | `observed` \| `forecast` — **prakiraan tidak boleh dijumlahkan dengan pengamatan** |
| `fetched_epoch` | Kapan baris ini diambil; membedakan revisi prakiraan |

**Peringatan yang wajib menempel pada setiap angka dari tabel ini:** Open-Meteo
adalah reanalisis pada petak 9–25 km, sementara sel hujan konvektif tropis
lebarnya 2–5 km. Satu badai bisa mengguyur bendungan sementara petaknya
melaporkan hujan ringan. Ini **sinyal regional**, dan antarmuka wajib selalu
melabelinya begitu. Tipping bucket di ESP32 adalah satu-satunya curah hujan yang
benar-benar terukur di pintu air.

---

## 5.5 Ringkasan endpoint

| Metode | Rute | Guna | Kode sukses |
|---|---|---|---|
| POST | `/api/ingest` | Terima batch dari ESP32 | 200 |
| GET | `/api/latest` | Semua yang dibutuhkan dasbor, satu permintaan | 200 |
| GET | `/api/camera` | Kamera yang sedang dipakai + daftar perangkat | 200 |
| POST | `/api/camera` | Minta ganti kamera | **202** |
| GET | `/api/polygons` | Poligon tersimpan | 200 |
| POST | `/api/polygons` | Simpan poligon | **202** |
| GET | `/api/live/frame` | JPEG bingkai terakhir | 200 |
| GET | `/api/live/mask` | JPEG mask terakhir | 200 |

Seluruh endpoint memakai `dynamic = "force-dynamic"`; tidak ada yang di-cache.

---

## 5.6 `POST /api/ingest`

Penerima batch dari firmware.

**Permintaan** (nilai sintetis)

```json
{
  "device": "esp32-XX",
  "rows": [
    { "csv": "2026-01-01T00:00:00Z,1767225600,42.0,58.0,1,5,0,0,0.0,AMAN,0,ntp,-60," },
    { "csv": "2026-01-01T00:01:00Z,1767225660,41.8,58.2,1,5,0,0,0.0,AMAN,0,ntp,-61," }
  ]
}
```

Field `csv` adalah **satu baris utuh** dari kartu SD, urutan kolom persis seperti
`CSV_HEADER` di `logic_csv.h`:

```
ts_utc,ts_epoch,jarak_cm,tinggi_cm,valid,n_sampel,tip_total,tip_menit,
mm_per_jam,level,pompa,time_src,rssi,sms_status
```

**Tanggapan sukses**

```json
{ "received": 2, "inserted": 2 }
```

`received` = baris yang berhasil diurai, `inserted` = baris yang **baru**.
Selisih keduanya adalah baris yang sudah pernah masuk — normal saat pengiriman
ulang, bukan galat.

**Tanggapan galat**

| Kode | Badan | Penyebab |
|---|---|---|
| 400 | `{"error":"body is not valid JSON"}` | Badan bukan JSON |
| 400 | `{"error":"device is required"}` | `device` kosong / bukan string |
| 400 | `{"error":"rows must be an array"}` | `rows` bukan larik |
| 400 | `{"error":"rows[i].csv must be a string"}` | Elemen tanpa `csv` string |
| 400 | `{"error":"rows[i]: expected 14 columns, got N"}` | Jumlah kolom salah |
| 503 | `{"error":"store failed: ..."}` | Penulisan basis data gagal |

**Empat perilaku yang merupakan bagian dari kontrak, bukan detail implementasi:**

1. **Urai dulu, tulis kemudian.** Seluruh batch diurai sebelum basis data
   disentuh. Satu baris rusak menolak seluruh batch — dan kita tidak boleh sudah
   menulis separuhnya saat itu ketahuan.
2. **2xx adalah janji ketahanan.** Firmware memajukan kursor SD **hanya** pada
   2xx. Membalas 200 tanpa benar-benar menyimpan berarti baris itu hilang
   selamanya.
3. **Batch kosong atau hanya header membalas 200** dengan `received: 0`. Tidak
   ada yang perlu disimpan, tidak ada yang salah — 2xx membuat firmware
   melewati baris-baris itu.
4. **`nan` diperlakukan sebagai kosong.** `snprintf("%.1f", NAN)` mencetak
   literal `nan`, dan itu **memang** terjadi setiap kali ultrasonik gagal. Tanpa
   penanganan ini seluruh batch ditolak karena satu baris tidak-valid yang
   diharapkan, firmware tidak pernah memajukan kursornya, dan batch yang sama
   dikirim ulang selamanya.

---

## 5.7 `GET /api/latest`

Satu endpoint, bukan empat. Halaman demo menariknya dua kali per detik; empat
perjalanan bolak-balik akan melipatempatkan beban untuk data yang selalu dibaca
bersama.

**Tanggapan** (nilai sintetis)

```json
{
  "esp": {
    "ts_utc": "2026-01-01T00:00:00Z",
    "tinggi_cm": 58.0,
    "mm_per_jam": 0.0,
    "level": "AMAN"
  },
  "obs": {
    "ts_utc": "2026-01-01T00:00:12Z",
    "ts_epoch": 1767225612,
    "coverage": 0.11,
    "accumulation_frac": 0.24,
    "growth_per_min": 0.004,
    "alert": 0,
    "alert_reason": null
  },
  "verdict": {
    "state": "watch",
    "headline": "Penumpukan sedang bertambah",
    "detail": "Sekarang 24,0%, naik 0,4% per menit.",
    "minutesToThreshold": 15.0
  },
  "fisika": {
    "bf": 0.24,
    "beyond_model": false,
    "afflux_ratio": 1.73,
    "afflux_m": 0.59,
    "head_m": 1.39,
    "critical_bf": 0.29,
    "margin_to_road_m": 0.21,
    "calibrated": false
  },
  "hujan": { "...": "ringkasan per jendela" }
}
```

**Aturan degradasi.** Blok `fisika` dan `hujan` gagal secara mandiri, dan itu
disengaja: geometri lokasi yang hilang atau tabel hujan yang belum ada tidak
boleh menjatuhkan tinggi air dan putusan penyumbatan — dua angka yang
benar-benar ditindaklanjuti operator. Keduanya menjadi `null` / kosong, dan
kartunya menampilkan "tidak tersedia".

**`esp` dan `obs` bernilai `null` bila belum ada datanya**, tidak pernah nol.
`verdict.state` menjadi `"unknown"` dan halaman menampilkan "Belum ada
pengukuran".

### Nilai `verdict.state`

| State | Kapan | Judul yang tampil |
|---|---|---|
| `unknown` | Tidak ada observasi, atau `accumulation_frac` null | "Belum ada pengukuran" |
| `blocked` | `alert = 1` **atau** `frac ≥ 0,18` | "Bersihkan dulu sebelum membuka pintu" |
| `watch` | `growth_per_min > 0` | "Penumpukan sedang bertambah" |
| `clear` | Sisanya | "Aman membuka pintu" |

Ambang 0,18 sama dengan `blockage.area_threshold` di konfigurasi inferensi.
Pada state `watch`, `minutesToThreshold = (0,18 − frac) / growth` — perkiraan
linear, dan halaman tidak menyajikannya sebagai janji.

---

## 5.8 `/api/camera` dan `/api/polygons`

Keduanya menulis berkas yang dipantau gelung inferensi. **Tidak satu pun
menjalankan proses.**

### `GET /api/camera`

```json
{
  "active": "1",
  "devices": [
    { "index": 0, "width": 640, "height": 480 },
    { "index": 1, "width": 1280, "height": 720 }
  ],
  "error": null,
  "ts_epoch": 1767225600.0,
  "running": true
}
```

`running: false` dengan larik kosong berarti inferensi tidak berjalan, atau
berjalan tanpa `preview.enabled`. Itu bukan galat, jadi kodenya tetap 200.

### `POST /api/camera`

```json
{ "source": "1" }
```

→ `202 { "requested": "1" }`

**202, bukan 200.** Permintaan **diterima**, bukan **diterapkan**. Gelung
mengambilnya dalam ~0,5 detik dan melaporkan lewat `status.json` apakah
perangkatnya benar-benar terbuka.

Validasi: `/^[0-9]$/` — satu digit, titik. Galat
`400 {"error":"source harus indeks kamera 0-9"}`. Sempit dengan sengaja: nilai
ini diserahkan ke `cv2.VideoCapture` di proses lain.

### `GET /api/polygons`

```json
{
  "saved": true,
  "roi": [[0.02,0.02],[0.98,0.02],[0.98,0.98],[0.02,0.98]],
  "structure": [[0.3,0.2],[0.7,0.2],[0.7,0.8],[0.3,0.8]]
}
```

`{"saved": false, "error": null}` berarti belum ada yang digambar — gelung
kembali ke poligon di berkas konfigurasi. `{"saved": false, "error": "..."}`
berarti ada berkas di disk tapi tidak valid; gelung juga mengabaikannya, dan
penyunting harus bisa menampilkan keadaan itu.

### `POST /api/polygons`

Badan sama seperti keluaran GET. Aturan validasi:

| Aturan | Nilai |
|---|---|
| Titik minimum | 3 (`MIN_POINTS`) |
| Titik maksimum | 64 (`MAX_POINTS`) |
| Koordinat | **Pecahan 0..1**, bukan piksel |
| Luas minimum | 0,0001 (`MIN_AREA`) |

**Koordinat adalah pecahan bingkai, tidak pernah piksel.** Tiga hal mengubah
skala gambar antara kamera dan klik yang menempatkan titik: `preview.py`
mengecilkan ke `max_width`, peramban memuat `<img>` ke lebar kolomnya, dan
ganti kamera mengubah resolusi tangkapan. Piksel salah setelah salah satu dari
tiga itu; pecahan selamat dari ketiganya.

Aturan ini **kembaran** `valid_polygon` di `src/inference/control.py`. Kedua
sisi wajib sepakat persis: poligon yang lolos di satu sisi dan ditolak di sisi
lain akan diabaikan diam-diam — operator menggambar zona pintu, halaman bilang
"tersimpan", peringatan tetap memakai poligon lama.

---

## 5.9 `GET /api/live/{frame|mask}`

Menyajikan dua JPEG yang ditulis `src/inference/preview.py`. Berkas ini tidak
bisa tinggal di `web/public`: direktori itu bagian dari repo, sementara berkas
ini ditulis ulang tiap detik oleh proses lain.

| Header | Nilai | Alasan |
|---|---|---|
| `Content-Type` | `image/jpeg` | |
| `Cache-Control` | `no-store, must-revalidate` | Berkasnya berubah tiap detik. Bingkai ter-cache di bawah cap waktu terbaru adalah persis kegagalan yang ingin dihindari dasbor ini |
| `Last-Modified` | mtime berkas | |

Nama di URL bukan jalur yang disanitasi melainkan **himpunan tertutup** dua
kunci (`frame`, `mask`). Skema apa pun yang menyusun jalur berkas dari nilai URL
— sehati-hati apa pun lolosnya — berjarak satu bug dari menyajikan berkas
sembarang di mesin ini.

404 `"preview not available"` berarti inferensi tidak berjalan. Halaman
menggambar keadaan "belum ada" dari 404 itu.

> **Catatan kinerja yang tercatat di kode.** `Buffer` **adalah** `Uint8Array`,
> jadi diserahkan langsung, bukan disalin. Halaman demo menarik frame+mask 10
> kali per detik; menyalin setiap satunya mengaduk megabita per detik lewat
> generasi muda dan mematikan server pengembangan dengan
> `NewSpace::EnsureCurrentCapacity Allocation failed` setelah ~95 detik.

---

## 5.10 Keamanan — keadaan sekarang

| Aspek | Keadaan |
|---|---|
| Autentikasi | **Tidak ada** `[BELUM]` |
| Otorisasi | **Tidak ada** `[BELUM]` |
| HTTPS | Tidak; HTTP polos di LAN |
| Pembatasan laju | **Tidak ada** `[BELUM]` |
| Penelusuran jalur | Dicegah — himpunan nama tertutup di `live.ts` |
| Injeksi SQL | Dicegah — semua kueri memakai parameter terikat |
| Injeksi perintah | Dicegah — tidak ada endpoint yang memanggil program |
| Validasi masukan | Ada di seluruh endpoint POST |

**Yang harus dikerjakan sebelum sistem ini menghadap internet:**

1. Token per-perangkat di `/api/ingest`. Sekarang siapa pun yang bisa mencapai
   port 8000 dapat menyuntikkan bacaan palsu ke dalam sistem peringatan banjir.
2. HTTPS, atau terowongan (WireGuard/Tailscale).
3. Pembatasan laju di `/api/ingest`.

Di LAN terisolasi bersama satu MiFi, keadaan sekarang dapat diterima untuk
pengujian. Ia **tidak** dapat diterima untuk pemasangan permanen.

---

[← Daftar isi](README.md) · [Berikutnya: Model AI →](06-model-ai.md)
