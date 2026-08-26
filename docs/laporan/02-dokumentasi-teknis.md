# 2. Dokumentasi Teknis

[← Daftar isi](README.md) · [← Sebelumnya: Repositori](01-repositori.md)

---

Berkas ini menjelaskan **apa tugas tiap modul dan mengapa dibuat begitu**.
Rincian antarmuka (skema tabel, bentuk permintaan/tanggapan API) ada di
[05-database-api.md](05-database-api.md); diagram alirnya di
[03-arsitektur.md](03-arsitektur.md).

---

## 2.1 Empat aturan yang berlaku di seluruh kode

Aturan ini muncul berulang di setiap bahasa yang dipakai proyek. Memahaminya
lebih dulu membuat sisa dokumen ini singkat.

### Aturan 1 — Tidak ada pengukuran ≠ nol

`None` (Python) dan `null` (TypeScript) dipertahankan sampai ke tampilan. Nol
tidak pernah dipakai sebagai pengganti data yang hilang.

Alasannya ada di `src/inference/metrics.py`:

> Kalau penyebutnya nol — tidak ada air dan tidak ada sampah terlihat, misalnya
> ROI tertutup penuh atau model gagal — coverage bernilai None, bukan 0,0. Nilai
> 0,0 yang diam-diam muncul terbaca sebagai "sungai bersih", dan itu justru hal
> paling salah untuk dicatat saat banjir.

Di web, `formatCoverage(null)` mengembalikan `"tidak terukur"`, bukan `"0%"`.

### Aturan 2 — Konfigurasi di berkas, bukan di kode

Tidak ada ambang, ukuran, atau jalur yang ditanam keras di kode Python maupun
TypeScript. Semuanya lewat `configs/`. Firmware adalah pengecualian yang
disengaja: nilai C++ harus konstanta saat kompilasi, jadi seluruhnya
dikumpulkan di satu berkas `firmware/esp32/include/config.h` dan tidak ada
angka tersebar di `main.cpp`.

### Aturan 3 — Implementasi kembar harus diuji dengan angka yang sama

Dua perhitungan sengaja ditulis dua kali, di Python dan di TypeScript:

| Perhitungan | Python | TypeScript | Penguji |
|---|---|---|---|
| Fisika afflux | `src/physics.py` | `web/lib/fisika.ts` | `tests/test_physics.py` + `web/tests/fisika.test.ts` |
| Validasi poligon | `src/inference/control.py` (`valid_polygon`) | `web/lib/polygons.ts` | `tests/test_inference.py` + `web/tests/polygons.test.ts` |

Kenapa tidak satu implementasi saja? Karena berbagi berarti web harus memanggil
Python di tiap permintaan — lebih lambat dan lebih banyak cara gagal. Harganya:
kedua sisi **wajib** diuji dengan angka yang sama. Komentar di `fisika.ts`
menyebutnya eksplisit: *"MIRRORS src/physics.py — change one, change the other."*

Bahaya yang dijaga di sisi poligon lebih tajam lagi: poligon yang lolos di web
tapi ditolak di Python akan diabaikan diam-diam oleh gelung inferensi — operator
menggambar zona pintu, halaman bilang "tersimpan", dan peringatan tetap memakai
poligon lama.

### Aturan 4 — Tulis berkas secara atomik

Setiap berkas kendali di `out/<site>/live/` ditulis ke `.tmp` lalu `rename()`.
Gelung inferensi membaca berkas yang sama; berkas separuh tertulis akan terbaca
sebagai "tidak ada permintaan" dan diam-diam kembali ke konfigurasi lama.

---

## 2.2 Python — `src/`

### `src/data/` — dataset

| Berkas | Tugas |
|---|---|
| `schema.py` | Indeks kelas tunggal (`BACKGROUND=0, WATER=1, DEBRIS=2, CLUMP=3`), pemuat `classes*.yaml`, penerapan aturan `collapse` |
| `base.py` | Antarmuka adapter dataset |
| `adapters/coco_polygon.py` | Poligon COCO → PNG semantik (RIPTSeg, RiSID) |
| `adapters/semantic_png.py` | PNG label yang sudah semantik (IWHR) |
| `adapters/voc_bbox.py` | Kotak VOC → mask lewat SAM |
| `convert.py` | Orkestrasi konversi, menulis `convert_summary.json` |
| `splits.py` | Pembagian latih/validasi/uji, **sadar-grup** |
| `validate.py` | Pemeriksaan sanity setelah konversi |
| `clump.py` | Heuristik komponen terhubung: `debris` luas → `clump` |
| `water_pseudolabel.py` | Label air semu dengan SAM |
| `sam.py` | Pembungkus SAM |
| `review.py` | Alat tinjau anotasi manual (dipakai untuk `review/iwhr/`) |

**Pembagian sadar-grup itu inti, bukan hiasan.** RIPTSeg berisi 300 bingkai dari
6 kamera tetap; bingkai bersebelahan nyaris kembar. Pembagian acak akan menaruh
bingkai `n` di latih dan bingkai `n+1` di uji, dan yang terukur adalah hafalan.
Karena itu pembagiannya **per lokasi**: latih loc2/3/5/6, validasi loc4, uji
loc1. Commit `25bb353` ada justru karena pengelompokan ini pernah rusak diam-diam.

### `src/models/` — arsitektur

`registry.py` memetakan nama di YAML ke kelas model. Empat sumber:

| Berkas | Model | Lisensi |
|---|---|---|
| `torchvision_models.py` | `lraspp_mnv3`, `deeplabv3_mnv3` | Apache-2.0 |
| `smp_models.py` | `unet_mnv3`, `unet_effnet_lite`, `deeplabv3plus_mnv3`, `segformer_b0` | MIT |
| `fast_scnn.py` | `fast_scnn` (disalin ke dalam repo) | MIT |
| `yolo_seg.py` | `yolo11n_seg` | **AGPL-3.0 — sengaja dipisah** |

YOLO ditaruh di `extra` tersendiri di `pyproject.toml` dan dikeluarkan dari
rekomendasi apa pun skornya: AGPL pada layanan jaringan bisa mewajibkan
pelepasan seluruh kode sumber.

### `src/train/` — pelatihan

Gelung latih standar dengan tiga hal yang layak disebut:

1. **Rugi `dice+focal`**, bobot 0,5/0,5. Kelas `debris` hanya ~3% piksel;
   *cross-entropy* biasa akan puas dengan menebak air.
2. **`select_metric: iou_debris`**, bukan mIoU dan **tidak pernah**
   `pixel_acc`. Bukti: pada run 4-kelas `pixel_acc` = **0,93** sementara
   `debris IoU` = **0,10**. Satu pasang angka itu sebabnya akurasi piksel
   dilarang secara struktural dari metrik utama.
3. **`per_dataset_cap`**, membatasi sampel per dataset per epoch. Tanpa itu,
   gabungan 200 RIPTSeg + 2510 IWHR membuat tiap epoch ~93% IWHR, dan
   satu-satunya air beranotasi manusia di proyek ini tenggelam di bawah
   label semu SAM.

### `src/bench/` — tolok ukur

| Berkas | Mengukur |
|---|---|
| `cost.py` | Parameter, ukuran disk, GFLOPs, latensi p50/p90 di tiga resolusi |
| `accuracy.py` | IoU per kelas, presisi/recall debris, di split uji |
| `report.py` | Menggabung keduanya jadi `docs/model_comparison.md` |

GFLOPs diambil dari `torch.utils.flop_counter` bawaan — tanpa fvcore/thop/ptflops.

### `src/inference/` — gelung waktu-nyata

Ini modul yang berjalan di lapangan.

| Berkas | Tugas |
|---|---|
| `run.py` | Gelung utama; membaca konfigurasi, membuka sumber, mengatur tiga laju |
| `metrics.py` | `coverage`, `accumulation_frac`, penghalusan, monitor penyumbatan |
| `geometry.py` | Poligon → mask, homografi, normalisasi 0..1 ↔ piksel |
| `velocity.py` | Aliran optik → kecepatan piksel/detik |
| `sink.py` | Penulis CSV + SQLite (WAL) |
| `preview.py` | Menulis `frame.jpg` / `mask.jpg` untuk halaman web |
| `control.py` | Membaca `control.json` / `polygons.json`, menulis `status.json` |

**Tiga jam yang sengaja dipisah** (dari docstring `run.py`):

| Laju | Untuk apa | Bawaan | Nilai di `site_webcam.yaml` |
|---|---|---|---|
| Laju kamera | Setiap bingkai masuk aliran optik — butuh bingkai berurutan ~33 ms | tiap bingkai | tiap bingkai |
| Laju sampah | Segmentasi debris | 1,0 s | 0,0 s (tanpa throttle) |
| Laju air | Penyegaran mask air | 30 s | 0,5 s |

Dan catatan jujurnya, juga dari docstring: dengan **satu** model 4-kelas, satu
forward pass sudah menghasilkan air dan sampah sekaligus, jadi menyimpan mask
air **tidak menghemat apa pun**. Penghematan baru nyata kalau `models.water`
diisi model terpisah yang lebih murah. Yang tetap berguna: mask air yang
di-cache menstabilkan penyebut coverage terhadap kedip antar-bingkai.

**Definisi `coverage`** — dihitung terhadap **air**, bukan terhadap bingkai:

```
coverage = (debris + clump) / (debris + clump + water)      di dalam ROI
```

Dibagi luas bingkai akan membuat angkanya bergantung pada seberapa banyak
langit dan tanggul yang kebetulan terlihat — berubah begitu dudukan kamera
tersenggol. Dibagi air membuatnya sifat sungai.

`accumulation_frac` memakai definisi yang sama tetapi di dalam poligon
`structure` (zona pintu), bukan ROI penuh. Inilah angka yang masuk ke fisika.

### `src/external/rainfall.py`

Pengambil curah hujan dari Open-Meteo (arsip + prakiraan) dan BMKG, ditulis ke
tabel `rainfall`. **Peringatannya melekat di kode**: petak Open-Meteo 9–25 km
sementara sel hujan konvektif tropis lebarnya 2–5 km. Angkanya sinyal regional,
bukan hujan di bendungan. Tipping bucket di ESP32 tetap satu-satunya curah hujan
yang benar-benar diukur di titik itu.

### `src/physics.py`

Rantai afflux. Rumus, sumber, dan peringatannya diringkas di
[06-model-ai.md §6.7](06-model-ai.md); lengkapnya di
[`../referensi_fisika.md`](../referensi_fisika.md).

Punya `demo()` yang berjalan mandiri:

```powershell
.venv\Scripts\python.exe -m physics
```

Keluarannya `[TERUKUR]` per 2026-08-25:

```
physics ok
  BF 24%  -> head x1.73, naik 59 cm
  jalan tergenang di BF 29%
```

### `src/gui/`

Penguji model interaktif berbasis Gradio (`gui.bat` melompat ke sini). Alat
bantu pengembangan, bukan bagian sistem lapangan. Ada di `extra` `gui` supaya
pemasangan di Raspberry Pi tidak menarik tumpukan web yang tidak akan dijalankan.

---

## 2.3 Web — `web/`

Next.js 15 (App Router), React 19, TypeScript, `better-sqlite3`, Vitest.
Tanpa Tailwind, tanpa pustaka komponen — CSS ditulis langsung di
`app/globals.css`.

### Halaman

| Rute | Berkas | Isi |
|---|---|---|
| `/` | `app/page.tsx` | Halaman operator: putusan, tinggi air, hujan, fisika, rel notifikasi |
| `/demo` | `app/demo/page.tsx` | Kamera langsung + penyunting poligon + pemilih kamera |

### Pustaka — `web/lib/`

| Berkas | Tugas |
|---|---|
| `db.ts` | Membuka SQLite, `CREATE TABLE IF NOT EXISTS`, singleton |
| `esp-csv.ts` | Mengurai satu baris CSV dari firmware (14 kolom, posisional) |
| `ingest.ts` | `INSERT OR IGNORE` satu batch dalam satu transaksi |
| `latest.ts` | Baris terbaru dari tiap sisi (ESP dan kamera) |
| `join.ts` | Menggabung dua deret pada jendela waktu |
| `verdict.ts` | Putusan operator: `clear` / `watch` / `blocked` / `unknown` |
| `fisika.ts` | Afflux untuk tampilan (kembaran `src/physics.py`) |
| `hujan.ts` | Membaca tabel `rainfall`, meringkas per jendela |
| `waktu.ts` | "5 menit lalu" dalam bahasa Indonesia |
| `notifikasi.ts` | Membangun rel notifikasi dari baris yang sama dengan kartu |
| `polygons.ts` | Kontrak poligon (kembaran `control.py`) |
| `live.ts` | Letak `frame.jpg` / `mask.jpg`, **himpunan nama tertutup** |

Empat keputusan yang layak dibaca sebelum menyunting:

**`join.ts` menyimpan baris ESP tanpa pasangan kamera.** Toleransi bawaan 60
detik — ESP mencatat tiap 60 s, kamera tiap 30 s, dan tidak ada jam yang persis.
Baris ESP tanpa padanan tetap disimpan dengan `obs: null`: tinggi air dan curah
hujan tetap pengukuran nyata saat kamera mati, dan membuangnya akan melubangi
deret hujan.

**`live.ts` memakai himpunan nama tertutup, bukan sanitasi jalur.** Nama datang
dari URL. Skema apa pun yang menyusun jalur berkas dari nilai itu — sehati-hati
apa pun lolosnya — berjarak satu bug dari menyajikan berkas sembarang di mesin
ini. Dua kunci tetap (`frame`, `mask`) tidak bisa ditelusuri.

**`notifikasi.ts` tidak pernah mengarang baris.** Desain aslinya memuat tiga
baris contoh yang ditanam keras. Semuanya diganti turunan dari baris yang sama
dengan kartu di atasnya, karena notifikasi karangan lebih buruk daripada rel
kosong — operator tidak punya cara membedakan keduanya.

**`esp-csv.ts` memperlakukan `nan` sama dengan kosong.** `snprintf("%.1f", NAN)`
di firmware mencetak literal `nan`, dan itu memang terjadi setiap kali
ultrasonik gagal. Tanpa penanganan ini `Number("nan")` melempar galat, **seluruh
batch ditolak**, firmware tidak pernah memajukan kursor unggahnya, dan batch
yang sama dikirim ulang selamanya. Baris yang benar-benar rusak tetap ditolak.

### Komponen — `web/components/`

| Berkas | Isi |
|---|---|
| `Shell.tsx` | Kerangka halaman, kepala, navigasi |
| `Clock.tsx` | Jam waktu setempat, dirender di klien |
| `Icon.tsx` | Ikon SVG sebaris (tanpa pustaka ikon) |
| `LiveDemo.tsx` | Penarik `frame.jpg`/`mask.jpg` ~10×/detik + pemilih kamera |
| `PolygonEditor.tsx` | Gambar ROI dan zona pintu di atas bingkai langsung |

---

## 2.4 Firmware — `firmware/esp32/`

PlatformIO, kerangka Arduino, papan `esp32dev`. Satu dependensi:
`adafruit/RTClib@^2.1.4`.

**Pemisahan yang penting:** berkas `logic_*.h` adalah C++ murni tanpa
`#include <Arduino.h>`, sehingga bisa dikompilasi dan diuji di komputer biasa
dengan g++ (lihat [08-protokol-uji.md](08-protokol-uji.md)). Berkas `hw_*.h`
menyentuh perangkat keras dan hanya berjalan di papan.

| Berkas | Jenis | Tugas |
|---|---|---|
| `config.h` | konfigurasi | Semua pin, ambang, dan periode |
| `config_secrets.h` | rahasia | WiFi, `INGEST_URL`, nomor tujuan — **gitignored** |
| `logic_median.h` | logika murni | Median dari N sampel |
| `logic_rain.h` | logika murni | Jendela bergulir 60 bin satu-menit |
| `logic_level.h` | logika murni | FSM level dengan histeresis |
| `logic_csv.h` | logika murni | Perakit baris CSV 14 kolom |
| `hw_time.h` | perangkat keras | DS3231 + NTP |
| `hw_logger.h` | perangkat keras | SD |
| `hw_upload.h` | perangkat keras | WiFi + HTTP POST |
| `src/main.cpp` | orkestrasi | `setup()` / `loop()`, penjadwalan, ISR |

### Empat perbaikan v1.4 → v2.0 yang terekam di kode

**1. Penghitungan tip pindah ke ISR.** v1.4 menyetel boolean lalu memprosesnya
sekali per gelung; dengan `delay(5000)` yang memblokir plus kirim SMS ~4 detik
yang juga memblokir, setiap tip di dalam jendela itu runtuh jadi satu — kurang
hitung paling parah justru saat hujan paling deras. Sekarang dihitung di ISR
dengan debounce `TIP_DEBOUNCE_US` = 250 ms, karena saklar buluh memantul puluhan
milidetik.

**2. Jendela hujan bergulir menggantikan ekstrapolasi.** v1.4 memakai
`tips_this_minute * mm_per_tip * 60`, yang melaporkan **36 mm/jam untuk dua tip**
— cukup untuk melewati ambang 30 mm/jam hanya karena cipratan. Sekarang 60 bin
satu-menit dijumlahkan; itu **memang** hujan satu jam terakhir, tanpa
ekstrapolasi.

**3. Histeresis dan dwell asimetris.** v1.4 memakai satu ambang untuk dua arah,
jadi air yang beriak di sekitar 30 cm membolak-balik status dan mengetak-ngetik
relai pompa. Sekarang masuk dan keluar pakai ambang berbeda
(`WASPADA_ENTER 30` / `WASPADA_EXIT 25`, `BAHAYA_ENTER 60` / `BAHAYA_EXIT 55`),
dan **turun** status harus stabil `DWELL_DOWN_MS` = 60 detik.

Naik segera, turun ditunda — disengaja: keselamatan tidak boleh menunggu, tapi
menyatakan aman harus yakin.

**4. Bacaan gagal bukan bukti aman.** Kalau ultrasonik tidak valid, FSM
**menahan** level saat ini alih-alih turun. Kegagalan sensor tidak boleh
mematikan pompa di tengah banjir. Hujan sendiri tetap boleh menaikkan level.

### Tabrakan pin yang sudah diselesaikan

Tercatat lengkap di `config.h` dan layak diulang di sini karena persis jenis bug
yang menghabiskan satu hari:

SD dipasang di pin SPI matriks-GPIO, **bukan** pin VSPI bawaan ESP32
(SCK=18/MISO=19/MOSI=23). SCK bawaan 18 akan bertabrakan dengan `ECHO_PIN`:
`SD.begin()` yang mengonfigurasi ulang GPIO18 jadi keluaran clock SPI tepat
setelah `setup()` menyetelnya INPUT untuk echo ultrasonik akan membuat
`pulseIn()` timeout di **setiap** pembacaan, apa pun kondisi sensornya. Karena
itu `SD_SCK_PIN 14`.

> **Catatan untuk penelusuran bug ultrasonik yang masih terbuka**
> ([08-protokol-uji.md §8.6](08-protokol-uji.md)): tabrakan ini **sudah**
> dihindari di konfigurasi sekarang, jadi ia bukan penjelasan untuk
> `n_sampel = 0`. Jangan buang waktu ke sana.

---

## 2.5 Alur kerja pengembangan

Terbaca dari riwayat commit dan dokumen rencana:

```
spesifikasi  →  rencana  →  uji dulu  →  implementasi  →  ukur  →  tulis
docs/superpowers/specs/   tests/       src/            bench/   docs/
```

Bukti bahwa urutan ini benar-benar dipakai, bukan klaim: setiap bug di
[`../phase1_results.md`](../phase1_results.md) §6 **punya uji regresi**, dan
keempatnya gagal secara senyap — tidak satu pun tertangkap uji asap sintetis.

Konvensi commit: `tipe(cakupan): kalimat imperatif huruf kecil`
(`feat(web): add the ESP32 ingest endpoint`).

---

[← Daftar isi](README.md) · [Berikutnya: Arsitektur →](03-arsitektur.md)
