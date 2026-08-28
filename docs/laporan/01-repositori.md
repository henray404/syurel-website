# 1. Repositori dan Kode Sumber

[← Daftar isi](README.md)

---

## 1.1 Identitas repositori

| | |
|---|---|
| Nama | `syurell` |
| Cabang kerja | `feature/gui` |
| Cabang utama | `main` |
| Jumlah commit | **28** `[TERUKUR]` — `git rev-list --count HEAD` |
| Commit terakhir | `b5f9b16` — *docs(web): add the web README and unblock the firmware config template* |

---

## 1.2 Peta direktori

```
syurell/
├── configs/                    Konfigurasi berbasis berkas — tidak ada nilai keras di kode
│   ├── classes.yaml            4 kelas: background, water, debris, clump
│   ├── classes_collapsed.yaml  3 kelas: clump dilebur ke debris (dipakai produksi)
│   ├── splits.yaml             Definisi pembagian latih/validasi/uji
│   ├── bench*.yaml             Konfigurasi tolok ukur biaya dan akurasi
│   ├── site_geometry.json      Dimensi pintu air — SEMUA MASIH [ASUMSI]
│   ├── datasets/               7 berkas: iwhr, lars, opsi, riptseg, risid,
│   │                           roboflow_river_trash, usvinland
│   ├── train/                  7 konfigurasi pelatihan
│   └── inference/              5 konfigurasi inferensi
│
├── src/                        Python — 39 berkas terlacak git
│   ├── data/                   Pemuatan, konversi, validasi, pembagian dataset
│   │   └── adapters/           coco_polygon, semantic_png, voc_bbox
│   ├── models/                 Registri arsitektur: fast_scnn, smp, torchvision, yolo_seg
│   ├── train/                  Gelung latih, fungsi rugi, metrik, dataset
│   ├── bench/                  Pengukuran biaya dan akurasi antar-arsitektur
│   ├── inference/              Gelung inferensi langsung
│   │   ├── run.py              Gelung utama
│   │   ├── metrics.py          coverage, accumulation_frac, penghalusan, alarm
│   │   ├── geometry.py         Poligon, homografi, normalisasi
│   │   ├── velocity.py         Aliran optik
│   │   ├── sink.py             Penulis CSV + SQLite
│   │   ├── preview.py          Penulis frame.jpg / mask.jpg untuk web
│   │   └── control.py          Ganti kamera + poligon lewat berkas
│   ├── external/rainfall.py    Pengambil API BMKG dan Open-Meteo
│   ├── physics.py              Perhitungan afflux
│   └── gui/                    Penguji model interaktif (Gradio)
│
├── web/                        Next.js 15 — 24 berkas terlacak git
│   ├── app/
│   │   ├── page.tsx            Halaman operator
│   │   ├── demo/               Halaman demo kamera langsung
│   │   └── api/                5 endpoint (lihat berkas 05)
│   ├── components/             LiveDemo, PolygonEditor, Shell, Icon
│   ├── lib/                    db, latest, join, verdict, polygons, waktu,
│   │                           esp-csv, ingest, live, notifikasi, bmkg
│   └── tests/                  11 berkas uji
│
├── firmware/esp32/             PlatformIO — ESP32
│   ├── include/
│   │   ├── config.h            Pin dan ambang
│   │   ├── config_secrets.h    RAHASIA — gitignored
│   │   ├── config_secrets.h.example  Templat yang boleh di-commit
│   │   ├── logic_*.h           Logika murni: csv, level, median, rain
│   │   └── hw_*.h              Perangkat keras: logger, time, upload
│   └── src/main.cpp
│
├── tests/                      93 uji Python + uji firmware
│   └── firmware/test_logic.cpp Uji logika firmware di host
│
├── docs/                       Dokumentasi
│   └── laporan/                ← folder ini
│
├── runs/                       Keluaran pelatihan (tidak dilacak git)
├── out/                        Keluaran inferensi (tidak dilacak git)
├── pyproject.toml
└── uv.lock
```

**Sebaran berkas terlacak git** `[TERUKUR]` — `git ls-files | awk -F/ '{print $1}' | sort | uniq -c`:

| Direktori | Berkas |
|---|---|
| `src/` | 39 |
| `web/` | 24 |
| `configs/` | 21 |
| `docs/` | 6 |
| `tests/` | 4 |
| `bench/` | 2 |
| lain-lain | 4 |

---

## 1.3 Riwayat commit

`[TERUKUR]` — `git log --oneline`

| Commit | Pesan |
|---|---|
| `b5f9b16` | docs(web): add the web README and unblock the firmware config template |
| `d27b26b` | feat(web): add the latest-reading API and the operator page |
| `263e0ca` | feat(web): derive the operator verdict from the latest observation |
| `157a082` | feat(web): join ESP and camera series on a time window |
| `bbd64d4` | feat(web): add the ESP32 ingest endpoint |
| `319f812` | feat(web): parse ESP32 CSV rows |
| `11cf5b0` | feat(web): scaffold Next.js app and the SQLite module |
| `ba42b1a` | feat(sink): open the timeseries db in WAL mode |
| `7c0b06d` | Add a Camera tab with real exposure control |
| `5779ee7` | Call the venv interpreter by path, not `python` from PATH |
| `144f077` | Add a double-click launcher for the GUI |
| `8c03651` | Interactive model tester (Gradio) |
| `6d890fe` | Add high-end model candidates |
| `b942d79` | EDA on RiSID annotations |
| `25bb353` | Fix RiSID grouping: splitting was a no-op, and .stem ate the filename |
| `7551297` | Ignore inference time-series output |
| `716ea72` | Trained models and measured accuracy on RIPTSeg |
| `21460af` | Set num_workers 0 for the sweep runs |
| `c63a33a` | Fix: an absent structure polygon meant whole-frame, not no-structure |
| `a5d4f40` | Add architecture sweep and loc1 inference configs |

Tiga fase terbaca dari riwayat ini: **data dan model** (`a5d4f40` → `b942d79`),
**alat bantu** (`6d890fe` → `7c0b06d`), lalu **web dan integrasi**
(`ba42b1a` → `b5f9b16`).

---

## 1.4 Pekerjaan yang belum di-commit

`[TERUKUR]` — `git status --porcelain`. **Ini catatan penting dan jujur:**
sebagian besar pekerjaan mutakhir belum masuk riwayat git.

**Berkas termodifikasi (17):** `configs/classes.yaml`, `configs/datasets/iwhr.yaml`,
`configs/datasets/risid.yaml`, `docs/datasets.md`, `pyproject.toml`,
`scripts/download.py`, `src/inference/geometry.py`, `src/inference/run.py`,
`tests/test_inference.py`, `web/.gitignore`, `web/app/api/latest/route.ts`,
`web/app/globals.css`, `web/app/layout.tsx`, `web/app/page.tsx`, `web/lib/db.ts`,
`web/lib/esp-csv.ts`, `web/tests/db.test.ts`

**Berkas baru belum dilacak (yang penting):**

| Berkas/folder | Isi |
|---|---|
| `firmware/` | **Seluruh firmware ESP32** |
| `src/physics.py` | Perhitungan afflux |
| `src/external/` | Pengambil API curah hujan |
| `src/inference/control.py` | Ganti kamera + poligon |
| `src/inference/preview.py` | Penulis pratinjau langsung |
| `web/components/` | LiveDemo, PolygonEditor, Shell, Icon |
| `web/app/api/camera/`, `live/`, `polygons/` | Tiga endpoint baru |
| `web/app/demo/` | Halaman demo kamera |
| `configs/site_geometry.json` | Parameter pintu air |
| `configs/inference/site_webcam.yaml`, `site_video.yaml`, `site_bendungan.yaml` | Konfigurasi inferensi |
| `configs/train/combined_segformer_b0_640.yaml` | **Konfigurasi model produksi** |
| `tests/test_physics.py`, `tests/firmware/` | Uji fisika dan firmware |
| `docs/rencana_penelitian.md`, `pipeline_perhitungan.md`, `referensi_fisika.md`, `data_eksternal.md`, `wawancara_operator.md`, `prd_web_monitoring.md` | Dokumentasi |

> **Tindakan sebelum penyerahan:** commit semuanya. Repositori yang diserahkan
> saat ini **tidak memuat firmware, fisika, maupun tampilan web mutakhir**.
> Riwayat git berhenti di `b5f9b16`, sementara sistem yang berjalan jauh
> melampauinya.
>
> **Jangan sekali pun meng-commit `firmware/esp32/include/config_secrets.h`** —
> berisi kata sandi WiFi dan nomor telepon operator. Yang boleh di-commit hanya
> `config_secrets.h.example`.

---

## 1.5 Menyiapkan lingkungan

### Python

Manajer paket: **uv**. Lingkungan virtual di `.venv/`.

```powershell
uv sync
```

Menjalankan apa pun memerlukan `PYTHONPATH=src`:

```powershell
$env:PYTHONPATH = "src"
.venv\Scripts\python.exe -m inference.run --help
```

> Panggil `.venv\Scripts\python.exe` lewat jalurnya, **bukan** `python` dari
> PATH. Commit `5779ee7` ada justru karena kesalahan ini: `python` dari PATH
> pada mesin ini menunjuk conda base yang tidak punya torch CUDA.

### Web

```powershell
cd web
npm install
npm run dev        # http://localhost:8000
```

### Firmware

PlatformIO. Salin templat rahasia lebih dulu:

```powershell
copy firmware\esp32\include\config_secrets.h.example firmware\esp32\include\config_secrets.h
# lalu sunting: WIFI_SSID, WIFI_PASS, INGEST_URL, NOMOR_TUJUAN, DEVICE_ID
pio run -t upload -d firmware/esp32
pio device monitor -d firmware/esp32
```

---

## 1.6 Perintah yang sering dipakai

### Pelatihan model

```powershell
$env:PYTHONPATH = "src"
.venv\Scripts\python.exe -m train.train --config configs/train/combined_segformer_b0_640.yaml
```

### Tolok ukur arsitektur

```powershell
.venv\Scripts\python.exe -m bench.cost         # biaya: parameter, GFLOPs, latensi
.venv\Scripts\python.exe -m bench.accuracy     # akurasi: IoU per kelas
.venv\Scripts\python.exe -m bench.report       # menghasilkan docs/model_comparison.md
```

### Inferensi

```powershell
# Webcam laptop (index 0)
.venv\Scripts\python.exe -u -m inference.run --config configs/inference/site_webcam.yaml --source 0

# Insta360 Link (index 1)
.venv\Scripts\python.exe -u -m inference.run --config configs/inference/site_webcam.yaml --source 1

# Berkas video
.venv\Scripts\python.exe -u -m inference.run --config configs/inference/site_video.yaml --source video.mp4
```

> Bendera `-u` bukan hiasan. Tanpa itu keluaran Python di-buffer saat dialihkan
> ke berkas, dan log tampak kosong padahal proses berjalan normal.

### Curah hujan eksternal

```powershell
.venv\Scripts\python.exe -m external.rainfall --db out/webcam/timeseries.sqlite --days 7
```

### Pengujian

```powershell
$env:PYTHONPATH = "src"; .venv\Scripts\python.exe -m pytest tests/ -q    # 93 uji
cd web; npx vitest run                                                    # 70 uji
.venv\Scripts\python.exe -m physics                                       # periksa mandiri fisika
.venv\Scripts\python.exe -m inference.control                             # periksa mandiri kontrol
powershell tests\firmware\run_tests.ps1                                   # logika firmware
```

---

## 1.7 Berkas yang sengaja tidak dilacak

Diatur di `.gitignore`:

| Pola | Alasan |
|---|---|
| `.venv/` | Lingkungan virtual, dibangun ulang dari `uv.lock` |
| `runs/` | Bobot model, ratusan MB |
| `out/` | Keluaran inferensi: SQLite, CSV, JPEG pratinjau |
| `data/` | Dataset mentah, diunduh dengan `scripts/download.py` |
| `firmware/esp32/include/config_secrets.h` | **Kata sandi WiFi dan nomor telepon** |
| `firmware/esp32/.pio/` | Cache dependensi PlatformIO |
| `/.env` | Variabel lingkungan |

---

[← Daftar isi](README.md) · [Berikutnya: Dokumentasi teknis →](02-dokumentasi-teknis.md)
