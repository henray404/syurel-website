# 4. Spesifikasi Teknologi dan Komponen

[← Daftar isi](README.md) · [← Sebelumnya: Arsitektur](03-arsitektur.md)

---

## 4.1 Perangkat keras — daftar komponen

| # | Komponen | Fungsi dalam sistem | Antarmuka | Status |
|---|---|---|---|---|
| 1 | ESP32 DevKit 38-pin | Pengendali sensor lapangan | — | Terpasang, berjalan |
| 2 | JSN-SR04T | Jarak sensor→muka air (ultrasonik tahan air) | TRIG/ECHO digital | **Terpasang, belum menghasilkan bacaan valid** |
| 3 | Tipping bucket + saklar buluh | Curah hujan di titik ukur | Digital + interupsi | Terpasang, **terbukti berfungsi** |
| 4 | Sensor hujan (papan DO) | Indikator hujan/tidak | Digital | Terpasang |
| 5 | DS3231 | Jam waktu-nyata dengan baterai | I²C (21/22) | Terpasang, **terbukti berfungsi** |
| 6 | Modul kartu microSD | Penyimpanan lokal (sumber kebenaran) | SPI matriks-GPIO | Terpasang |
| 7 | SIM800L | SMS ke operator | UART2 | Terpasang |
| 8 | Modul relai | Kendali pompa | Digital | Terpasang |
| 9 | Insta360 Link | Kamera pengamatan (uji) | USB UVC, 1280×720 | **Terbukti berfungsi** |
| 10 | Webcam ASUS FHD | Kamera cadangan (uji) | USB UVC, 640×480 | **Terbukti berfungsi** |

Kolom status hanya menyatakan apa yang **terbukti dari data**, bukan apa yang
seharusnya. Bukti untuk tiap baris ada di
[07-data-pengujian.md](07-data-pengujian.md).

---

## 4.2 Peta pin ESP32

`[TERUKUR]` — nilai persis dari `firmware/esp32/include/config.h`.

| Konstanta | GPIO | Perangkat | Arah |
|---|---|---|---|
| `TRIG_PIN` | 5 | JSN-SR04T trigger | keluaran |
| `ECHO_PIN` | 18 | JSN-SR04T echo | masukan |
| `RAIN_SENSOR_PIN` | 34 | Sensor hujan DO | masukan |
| `RAIN_GAUGE_PIN` | 13 | Saklar buluh tipping bucket | masukan, interupsi |
| `RELAY_PIN` | 26 | Relai pompa | keluaran |
| `SD_CS_PIN` | 33 | SD chip select | keluaran |
| `SD_SCK_PIN` | **14** | SD clock | keluaran |
| `SD_MISO_PIN` | 19 | SD MISO | masukan |
| `SD_MOSI_PIN` | 23 | SD MOSI | keluaran |
| (bawaan Wire) | 21 / 22 | DS3231 SDA / SCL | I²C |
| `HardwareSerial(2)` | — | SIM800L | UART2 |

### Dua catatan pemasangan yang menyelamatkan waktu

**`SD_SCK_PIN` sengaja 14, bukan 18.** Pin VSPI bawaan ESP32 adalah
SCK=18/MISO=19/MOSI=23. SCK bawaan 18 bertabrakan dengan `ECHO_PIN`:
`SD.begin()` yang mengonfigurasi ulang GPIO18 jadi keluaran clock SPI tepat
setelah `setup()` menyetelnya INPUT untuk echo akan membuat `pulseIn()` timeout
di **setiap** pembacaan, apa pun kondisi sensornya. Tabel pemasangan sudah
memakai SCK=14 sehingga tabrakan itu terhindar.

**`RAIN_GAUGE_PIN` adalah 13, bukan 27.** Foto tabel pemasangan menyebut GPIO27;
kabel sebenarnya di GPIO13. Yang berlaku adalah kabelnya, dan `config.h` sudah
menyesuaikan — komentar di berkas itu mencatat selisihnya supaya tidak
"diperbaiki" kembali ke nilai yang salah.

---

## 4.3 Kalibrasi dan ambang firmware

`[TERUKUR]` sebagai isi berkas; sebagian besar `[ASUMSI]` sebagai nilai fisik.

| Konstanta | Nilai | Satuan | Status | Catatan |
|---|---|---|---|---|
| `JARAK_DASAR` | 100,0 | cm | **`[ASUMSI]`** | Jarak muka sensor ke dasar. **Nilai sementara.** Salah di sini membuat semua tinggi salah |
| `SENSOR_BLIND_CM` | 25,0 | cm | literatur | JSN-SR04T tidak bisa mengukur lebih dekat dari ~25 cm |
| `WASPADA_ENTER` | 30,0 | cm | `[ASUMSI]` | Ambang naik ke WASPADA |
| `WASPADA_EXIT` | 25,0 | cm | `[ASUMSI]` | Ambang turun dari WASPADA |
| `BAHAYA_ENTER` | 60,0 | cm | `[ASUMSI]` | Ambang naik ke BAHAYA |
| `BAHAYA_EXIT` | 55,0 | cm | `[ASUMSI]` | Ambang turun dari BAHAYA |
| `DWELL_DOWN_MS` | 60.000 | ms | desain | Lama stabil sebelum boleh turun status |
| `MM_PER_TIP` | 0,30 | mm | **`[ASUMSI]`** | **Harus dikalibrasi dengan gelas ukur** |
| `TIP_DEBOUNCE_US` | 250.000 | µs | desain | Saklar buluh memantul puluhan ms |
| `RAIN_WASPADA` | 10,0 | mm/jam | literatur | Ambang hujan sedang |
| `RAIN_BAHAYA` | 30,0 | mm/jam | literatur | Ambang hujan lebat |
| `ULTRA_SAMPLES` | 5 | — | desain | Median dari 5 ping per bacaan |
| `MAX_MIN_SAMPLES` | 16 | — | desain | Bacaan yang disangga per menit tercatat |

| Periode | Nilai | Konstanta |
|---|---|---|
| Baca sensor | 5 detik | `SENSOR_PERIOD_MS` |
| Catat ke SD | 60 detik | `LOG_PERIOD_MS` |
| Unggah batch | 5 menit | `UPLOAD_PERIOD_MS` |
| Sinkron NTP | 6 jam | `NTP_PERIOD_MS` |
| Ulang SMS | 5 menit | `SMS_REPEAT_MS` |

> **Peringatan yang tidak boleh dilewat.** `SENSOR_BLIND_CM` bukan angka hiasan:
> `JARAK_DASAR` harus dipilih supaya ambang BAHAYA terlampaui **sebelum** air
> masuk zona buta itu. Kalau tidak, sensor jadi buta tepat saat banjir
> berlangsung — kegagalan paling buruk yang bisa dimiliki sistem ini.

---

## 4.4 Parameter geometri lokasi

`configs/site_geometry.json`, status `UNCALIBRATED`. **Setiap angka di bawah
masih tebakan.**

| Kunci | Nilai | Satuan | Arti | Sumber tercatat |
|---|---|---|---|---|
| `b_m` | 2,0 | m | Lebar bukaan pintu | tebak — ukur dengan meteran |
| `a_m` | 1,0 | m | Tinggi bukaan | tebak — tanya operator bukaan normalnya |
| `Cd` | 0,61 | — | Koefisien debit | **literatur** (USBR); lebih baik dikalibrasi lewat miniatur |
| `h_bersih_m` | 0,8 | m | Muka air hulu saat pintu bersih | tebak — **garis dasar; salah di sini menggeser semua hasil** |
| `z_jalan_m` | 1,6 | m | Muka air saat jalan mulai tergenang | tebak |
| `kalibrasi_kamera.bias` | 0,0 | — | `BF = skala·frac + bias` | identitas sampai eksperimen E2 |
| `kalibrasi_kamera.skala` | 1,0 | — | idem | identitas sampai eksperimen E2 |
| `site.lat` / `lon` | `null` | — | Untuk Open-Meteo | **wajib diisi saat survei** |
| `site.adm4` | `null` | — | Kode wilayah desa untuk BMKG | mis. `35.15.09.2003` |

**Selama `status` masih `UNCALIBRATED`,** setiap hasil fisika diperlakukan
sebagai perkiraan kasar, bukan peringatan. Kode memastikan itu: `load_site()`
menganggap apa pun selain `"CALIBRATED"` eksplisit sebagai belum terkalibrasi,
karena arah sebaliknya akan membiarkan satu kolom yang hilang diam-diam
menaikkan tebakan jadi pengukuran.

Berkas ini **JSON, bukan YAML**, karena dulu dibaca dua sisi — Python
(`src/physics.py`) dan web (`web/lib/fisika.ts`), yang tidak punya pengurai YAML
tanpa menambah dependensi. Sejak kartu "Perkiraan kenaikan muka air" dihapus,
pembacanya tinggal Python. Formatnya tetap JSON: menggantinya sekarang hanya
mengaduk berkas yang sudah bekerja, tanpa ada yang diuntungkan.

---

## 4.5 Perangkat lunak — versi yang benar-benar terpasang

`[TERUKUR]` 2026-08-25 di mesin pengembangan.

### Python

| Komponen | Versi |
|---|---|
| Python | 3.13.14 |
| PyTorch | 2.12.0.dev20260408+cu128 |
| CUDA tersedia | **Ya** |
| GPU | NVIDIA GeForce RTX 5050 Laptop |
| OpenCV | 5.0.0 |
| NumPy | 2.5.2 |
| Manajer paket | uv (`uv.lock` terkunci) |

Dependensi inti dari `pyproject.toml`: `numpy>=1.24`, `pillow>=10.0`,
`pyyaml>=6.0`, `opencv-python-headless>=4.8`, `tqdm>=4.66`.

**Kelompok opsional** (`extras`), sengaja dipisah supaya pemasangan dasar tetap
ringan dan bebas torch:

| Extra | Isi | Kapan dipakai |
|---|---|---|
| `sam` | torch, torchvision, timm | Label air semu, konversi bbox→mask |
| `train` | torch, torchvision, albumentations, tensorboard | Pelatihan |
| `bench` | segmentation-models-pytorch ≥0.5.0 | Tolok ukur — satu paket membawa U-Net, DeepLabV3+, **dan** SegFormer sekaligus, jadi `transformers` tidak diperlukan |
| `yolo` | ultralytics ≥8.3 | **AGPL-3.0 — jangan dipasang tanpa sengaja** |
| `gui` | gradio ≥4.44 | Penguji model interaktif |
| `roboflow` | roboflow ≥1.1 | Unduh dataset |
| `dev` | pytest ≥8.0 | Pengujian |

### Peringatan CUDA yang tercatat di `pyproject.toml`

Dua hal yang akan membuang waktu kalau tidak dibaca:

1. **`uv sync` AKAN MENCOPOT torch CUDA yang dipasang lokal.** Roda CUDA
   dipasang dari berkas lokal sehingga tidak ada di `uv.lock`, dan `sync`
   "memperbaiki" lingkungan kembali ke build CPU dari PyPI. Setiap habis
   `uv sync`, pasang ulang dan periksa `torch.cuda.is_available()`.

2. **Tidak ada pin CUDA di `pyproject.toml`, dan itu disengaja.**
   `[tool.uv.sources]` berlaku di semua platform, sementara indeks CUDA PyTorch
   tidak punya roda aarch64 — memasang pin di sana akan membuat `uv sync` gagal
   total di Raspberry Pi, satu-satunya mesin yang **harus** bisa memasang proyek
   ini. Pasang eksplisit:

   ```powershell
   uv pip install --index-url https://download.pytorch.org/whl/cu130 --upgrade torch torchvision
   ```

   Pakai cu130, bukan cu128: untuk cp313 indeks cu128 berhenti di torch 2.11
   sementara cu130 membawa 2.13.0. RTX 5050 adalah Blackwell (sm_120) dan butuh
   cu128 ke atas.

### Web

| Komponen | Versi |
|---|---|
| Node.js | v24.15.0 |
| npm | 11.12.1 |
| Next.js | ^15.1.0 |
| React / React DOM | ^19.0.0 |
| better-sqlite3 | **^13.0.3** |
| TypeScript | ^5.7.0 |
| Vitest | ^2.1.0 |

**`better-sqlite3` v13, bukan v11**, dan alasannya tercatat di `package.json`:
v13 adalah versi pertama yang punya biner siap-pakai untuk Node 24 (ABI 137).
v11 jatuh ke kompilasi dari sumber, yang butuh Visual Studio build tools yang
tidak ada di mesin ini.

Tidak ada Tailwind, tidak ada pustaka komponen, tidak ada pustaka ikon — CSS
ditulis langsung di `app/globals.css`, ikon adalah SVG sebaris.

### Firmware

| Komponen | Nilai |
|---|---|
| Platform | `espressif32` (PlatformIO) |
| Papan | `esp32dev` |
| Kerangka | `arduino` |
| Laju monitor | 115200 |
| Dependensi | `adafruit/RTClib@^2.1.4` |

Satu dependensi saja. `WiFi`, `HTTPClient`, `SD`, `Wire`, `HardwareSerial`
semuanya bawaan kerangka Arduino-ESP32.

---

## 4.6 Model AI yang dipakai di produksi

| | |
|---|---|
| Arsitektur | SegFormer-B0 (encoder `mit_b0`, dekoder native smp) |
| Bobot awal | Pra-latih ImageNet |
| Resolusi masukan | 640×640 |
| Kelas keluaran | 4 (`background`, `water`, `debris`, `clump`) |
| Checkpoint | `runs/combined_segformer_b0_640/best.pt` |
| Metrik pemilihan | `iou_debris` pada set validasi |
| Nilai terbaik | **val debris IoU 0,7313** `[TERUKUR]` |
| Latensi terukur | **28 ms/bingkai** di RTX 5050 (≈35 fps) `[TERUKUR]` |
| Ukuran | 3,72 juta parameter, 14,9 MB |
| Lisensi | MIT (smp) |

Rinciannya, termasuk enam kandidat lain yang diukur dan mengapa yang ini
dipilih, ada di [06-model-ai.md](06-model-ai.md).

---

## 4.7 Kebutuhan perangkat keras untuk menjalankan

| Peran | Yang dipakai sekarang | Kebutuhan minimum | Status |
|---|---|---|---|
| Pelatihan | RTX 5050 Laptop 8 GB, Ryzen 9 270 | GPU ≥8 GB VRAM | `[TERUKUR]` |
| Inferensi | Mesin yang sama | GPU apa pun, atau CPU dengan laju rendah | `[TERUKUR]` |
| Unit kamera lapangan | Raspberry Pi 5, RAM 16 GB | Pi mana pun yang sanggup MJPEG 640×360 | `[TERUKUR]` |
| Kamera | Insta360 Link (USB) | Webcam UVC apa pun | `[TERUKUR]` |
| Web | Mesin yang sama, port 8000 | Node 24 | `[TERUKUR]` |
| Sensor lapangan | ESP32 + MiFi | — | `[TERUKUR]` untuk unggah |

**Pi tidak menjalankan model, dan itu disengaja.** Pembagiannya: Pi adalah mata,
server adalah otak. Pi hanya membuka kamera dan mengalirkan MJPEG; seluruh
segmentasi, fisika, basis data, dan halaman web berjalan di mesin bergpu.
Alasannya, sebuah Pi murah dan hemat daya sehingga boleh berada di tepi sungai,
sedangkan GPU tidak — dan menaruh model di Pi berarti membayar satu akselerator
per titik pantau.

Konsekuensinya harus disebut: **server wajib hidup.** Pi yang kehilangan server
tidak menyimpan apa pun sendiri, berbeda dari ESP32 yang tetap mencatat ke
microSD dan mengunggah menyusul. Lihat tabel mode kegagalan di
[03 §3.7](03-arsitektur.md).

**Yang wajib diakui:** seluruh angka latensi di `docs/model_comparison.md`
diukur di x86. `is_target_device` bernilai `false` di `configs/bench.yaml`.
Selama inferensi tetap di server, angka itu sahih untuk sistem ini; ia baru
menjadi tidak sahih bila model dipindahkan ke Pi — yang **bukan** rancangan
sekarang.

### Kinerja unit kamera `[TERUKUR]` 2026-08-27

| Butir | Nilai |
|---|---|
| Aliran video | `http://TBCare.local:81/stream`, MJPEG 640×360 |
| Citra diam | `http://TBCare.local/capture`, JPEG 1280×720, ±190 KB |
| Server di Pi | `BaseHTTP/0.6 Python/3.13.5` |
| Ketahanan | 5.402 bingkai dalam 180 detik, **30,0 fps**, jeda terburuk **0,18 detik** |
| Penemuan alamat | mDNS `TBCare.local`, diverifikasi bisa dibuka OpenCV |

**Pakai nama mDNS, bukan alamat IP.** Kedua perangkat memakai DHCP, dan alamat
server sempat berpindah dua kali dalam satu jam pada 27 Agustus — setiap
perpindahan membuat ESP32 senyap sampai `INGEST_URL` disunting dan firmware
di-flash ulang. `TBCare.local` tidak punya masalah itu. Untuk sisi server,
reservasi DHCP di router adalah perbaikan yang lebih tahan lama.

---

## 4.8 Jaringan

| Butir | Nilai |
|---|---|
| Port server web | 8000 (`next dev -p 8000` / `next start -p 8000`) |
| Endpoint unggah | `http://<IP-LAN>:8000/api/ingest` |
| Protokol | HTTP, `Content-Type: application/json` |
| Autentikasi | **Tidak ada** `[BELUM]` |
| Konektivitas ESP32 | WiFi STA ke MiFi |
| RSSI terukur | −61 s/d −78 dBm `[TERUKUR]`, 25 sampel |

**`INGEST_URL` harus memakai alamat LAN mesin, bukan `localhost`.** ESP32
menerjemahkan nama itu sendiri; `localhost` berarti ESP32 itu sendiri. Catatan
ini ditulis langsung di `config_secrets.h.example` supaya tidak terulang.

Firewall Windows harus mengizinkan TCP 8000 masuk di profil jaringan privat.

---

## 4.9 Berkas rahasia

Satu berkas, dan **tidak boleh** masuk git:

```
firmware/esp32/include/config_secrets.h
```

Isinya: `WIFI_SSID`, `WIFI_PASS`, `NOMOR_TUJUAN` (nomor HP operator),
`INGEST_URL`, `DEVICE_ID`. Yang di-commit hanya `config_secrets.h.example`
dengan nilai contoh.

Di sisi Python, `ROBOFLOW_API_KEY` dibaca dari `.env` (lihat `.env.example`).
`.env` juga gitignored.

---

[← Daftar isi](README.md) · [Berikutnya: Basis data & API →](05-database-api.md)
