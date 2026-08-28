# 11. Ringkasan untuk Laporan

[← Daftar isi](README.md) · [← Sebelumnya: Referensi, batasan, penggunaan AI](10-referensi-batasan-ai.md)

---

Dokumen ini merangkum seluruh paket (bab 1–10) menjadi satu bacaan utuh yang bisa
langsung dipakai sebagai bahan laporan. Setiap angka berasal dari berkas di
repositori — `bench/accuracy.json`, `bench/cost.json`, `runs/*/summary.json`,
tabel `observations` dan `esp_readings`, serta keluaran rangkaian uji — dan setiap
perintah yang dicantumkan bisa dijalankan ulang oleh pembaca.

---

## 1. Ringkasan singkat

Syurell adalah sistem peringatan dini penyumbatan sampah di pintu air bendung
gerak. Sebuah unit kamera mengawasi permukaan air di depan pintu, model segmentasi
memisahkan sampah dari air, dan luas sampah di dalam zona pintu diubah menjadi
**satu putusan tindakan** untuk operator. Sensor ESP32 mengukur tinggi muka air
dan curah hujan sebagai jalur kedua yang tidak bergantung pada kamera.

**Yang membedakan pendekatan ini:** sistem tidak menampilkan persentase lalu
membiarkan operator menafsirkannya. Ia menjawab pertanyaan yang memang dihadapi
operator setiap kali — *boleh dibuka sekarang, atau harus dibersihkan dulu?* — dan
bila penumpukan sedang bertambah, ia menyertakan hitungan mundur menuju ambang.
Rinciannya di bagian 3.

| Aspek | Isi |
|---|---|
| Lokasi penerapan | Pintu air bendung gerak, kamera diam |
| Model | SegFormer-B0, 4 kelas, inferensi 640 px |
| Putusan | Empat keadaan: aman · bertambah · bersihkan dulu · belum ada pengukuran |
| Ambang tindakan | 18% luas zona pintu, dapat disetel per lokasi |
| Antarmuka | Dasbor web (Next.js, port 8000), zona pintu digambar operator |
| Sensor lapangan | ESP32: ultrasonik JSN-SR04T + tipping bucket + SMS SIM800L |
| Unit kamera | Raspberry Pi 5 (16 GB) + Insta360 Link, aliran MJPEG |
| Uji perangkat lunak | 214 uji otomatis: 95 Python, 72 web, 47 firmware |
| Bahasa/lingkungan | Python 3.13, Node 24, C++11 |

---

## 2. Masalah dan sasaran

Sampah kiriman hulu menumpuk di depan pintu air, mempersempit luas bukaan, dan
menaikkan muka air di sisi hulu. Operator mengetahuinya hanya dengan melihat
langsung, dan tidak ada catatan tertulis apa pun tentang kejadian sebelumnya.

Dasar masalah ini bukan asumsi penulis. Dalam wawancara, ditanya penyebab banjir
terakhir dua tahun lalu, operator menjawab **sampah kiriman hulu yang menyumbat**
— tanpa dipancing, sebelum pewawancara menyebut kata sampah sama sekali. Ia juga
menyatakan tidak ada buku catatan harian, sehingga kejadian sebesar itu tidak
meninggalkan satu pun angka.

**Sasaran sistem**, keduanya dirumuskan dari jawaban wawancara:

1. **Mengubah pengamatan mata menjadi angka yang tercatat.** Sistem menulis satu
   baris terukur untuk setiap bingkai, sehingga kejadian berikutnya punya riwayat
   — bukan sekadar ingatan.
2. **Melihat kondisi hulu tanpa harus berada di sana.** Operator selalu datang ke
   pintu air, dan pintu dijaga penuh semalaman; yang tidak bisa dilihat dari pintu
   adalah apa yang sedang dikirim hulu. Sistem ini melengkapi kehadiran operator,
   bukan menggantikannya.

**Lingkup yang ditetapkan sejak awal:** satu unit kamera, satu pintu air, dan
seluruh pemrosesan di perangkat lokal tanpa mengirim video ke layanan luar.

---

## 3. Metode: dari luas sampah ke tindakan

Persentase tutupan saja tidak bisa ditindaklanjuti — 20% tidak memberi tahu
operator apakah ia harus turun tangan sekarang atau nanti. Karena itu keluaran
akhir sistem bukan angka, melainkan **putusan**, dengan angkanya menyertai sebagai
alasan.

```
mask segmentasi → luas sampah di zona pintu → bandingkan ambang → PUTUSAN
                                            ↘ laju tumbuh → hitungan mundur
```

Empat keadaan yang mungkin, seluruhnya ditentukan `web/lib/verdict.ts`:

| Keadaan | Judul di layar | Kapan muncul |
|---|---|---|
| `clear` | **Aman membuka pintu** | Tutupan di bawah ambang, tidak bertambah |
| `watch` | **Penumpukan sedang bertambah** | Masih di bawah ambang tetapi laju tumbuh positif — disertai *"perkiraan mencapai ambang dalam N menit"* |
| `blocked` | **Bersihkan dulu sebelum membuka pintu** | Tutupan ≥ 18%, atau monitor penyumbatan menyalakan alarm |
| `unknown` | **Belum ada pengukuran** | Kamera tidak mengirim data — operator diminta memeriksa langsung |

**Hitungan mundur adalah yang membuat keadaan `watch` berguna.** Selisih menuju
ambang dibagi laju tumbuh per menit menghasilkan perkiraan waktu, sehingga
operator tahu apakah ia punya lima menit atau lima puluh.

**Zona pintu digambar operator, bukan ditetapkan program.** Poligon digambar di
atas bingkai nyata lewat dasbor, disimpan sebagai koordinat pecahan 0–1 sehingga
tetap benar ketika resolusi kamera berubah, dan dibaca ulang gelung inferensi
dalam waktu sekitar setengah detik tanpa menghentikan proses.

**Dua jalur pengukuran yang saling bebas.** Kamera memberi luas tutupan; ESP32
memberi tinggi muka air dan curah hujan. Salah satu berhenti, yang lain tetap
mengukur dan tetap tampil, masing-masing membawa cap waktunya sendiri sehingga
sumber yang diam terlihat sebagai diam.

**Aturan yang berlaku di seluruh kode:** nilai yang tidak terukur tidak pernah
menjadi nol. `None` dan `null` dipertahankan sampai ke tampilan, dan halaman
menulis "tidak terukur". Nol akan terbaca sebagai "sungai bersih" — hal paling
salah yang bisa ditampilkan saat banjir.

---

## 4. Arsitektur sistem

```
Di tepi sungai                      Di ruang kendali
┌───────────────────────┐           ┌────────────────────────────┐
│ Insta360 Link         │           │ inference.run              │
│   └→ Raspberry Pi 5   │──MJPEG───▶│   → SegFormer-B0           │
│      TBCare.local:81  │           │   → metrik → monitor       │
│                       │           │   → SQLite + pratinjau     │
│ ESP32                 │           │                            │
│   ultrasonik, hujan   │──POST────▶│ Next.js :8000              │
│   └→ microSD          │ /api/     │   → verdict() → dasbor     │
│   └→ SIM800L ── SMS ──┼───────────────────────▶ Operator       │
└───────────────────────┘  ingest   └────────────────────────────┘
```

**Empat proses yang berdiri sendiri.** Tidak satu pun memanggil yang lain secara
langsung — perpindahan hanya lewat HTTP atau berkas di disk. Karena itu tiap
bagian bisa dimatikan dan dinyalakan ulang tanpa menyentuh yang lain.

**Pi adalah mata, server adalah otak.** Perangkat di tepi sungai harus murah,
hemat daya, dan tahan cuaca; GPU tidak memenuhi ketiganya. Pi membuka kamera dan
mengalirkan video, seluruh segmentasi berjalan di server — sehingga menambah titik
pantau berarti menambah satu Pi, bukan satu akselerator.

**Jalur SMS tidak melewati server sama sekali.** ESP32 mengirimnya langsung lewat
SIM800L. Peringatan tingkat BAHAYA tetap sampai ke operator meski seluruh sisi
komputer padam — sifat yang penting untuk sistem peringatan banjir.

**Unit sensor menyimpan datanya sendiri.** Tiap baris ditulis ke microSD lebih
dulu, dan kursor unggah maju **hanya** setelah server menjawab 2xx. Server yang
mati berarti pengiriman tertunda, bukan data hilang.

Seluruh sistem bertemu di **satu berkas SQLite** mode WAL — satu penulis, banyak
pembaca, tanpa server basis data yang harus dijaga hidup.

Delapan diagram lengkap, termasuk alur keputusan per bingkai dan mesin keadaan
level, ada di [03-arsitektur.md](03-arsitektur.md).

---

## 5. Dataset dan model

Empat kelas: `background`, `water`, `debris`, `clump`.

### 5.1 Sumber dataset

Seluruh data latih berasal dari **dataset publik yang dipublikasikan bersama
makalah ilmiah**. Tiap sumber punya berkas konfigurasinya sendiri di
`configs/datasets/`, memuat tautan unduh, lisensi, dan alasan dataset itu dipakai.

| Dataset | Sumber | Lisensi | Peran |
|---|---|---|---|
| **RIPTSeg** | The Ocean Cleanup, 4TU.ResearchData — [`data.4tu.nl/datasets/90d13261-…`](https://data.4tu.nl/datasets/90d13261-b0fe-444a-b408-c5a63db3d887) · ±300 citra, 6 lokasi | CC BY 4.0 | **Jangkar.** Satu-satunya sumber dengan label air sungguhan |
| **RiSID v2** | Kataoka dkk., *Data in Brief* 63 (2025) — Zenodo `10.5281/zenodo.16927238` · 7.356 citra, 11 titik di 7 sungai Jepang | CC BY 4.0 | Pemasok utama mask sampah, direkam saat musim banjir |
| **IWHR Floater V1** | Qiao, Yang & Wang, China Institute of Water Resources and Hydropower Research — figshare `10.6084/m9.figshare.27376851` · 3.000 citra | Apache 2.0 | **Geometri kamera paling mirip lokasi sasaran** — kamera tetap di tepi perairan |
| **LaRS** | Žust, Perš & Kristan, ICCV 2023 — [`lojzezust.github.io/lars-dataset`](https://lojzezust.github.io/lars-dataset/) · ±4.000 bingkai kunci | Lihat halaman unduh | Keragaman air + contoh negatif sulit |
| **Roboflow River Trash** | Roboflow Universe | Lihat `configs/datasets/roboflow_river_trash.yaml` | Tambahan sampah |
| **USVInland** | — | Lihat `configs/datasets/usvinland.yaml` | Air perairan pedalaman |

Total lebih dari **14.000 citra** dari empat negara, tiga geometri kamera berbeda
(tepi perairan, jembatan, permukaan air), dan rentang kondisi cuaca yang tidak
mungkin direkam sendiri dalam satu musim.

**Citra mentah tidak pernah masuk repositori.** Direktori `data/` ada di
`.gitignore`; yang tersimpan hanya berkas konfigurasi berisi tautan sumber, dan
`scripts/download.py` mengunduhnya kembali dari penerbit aslinya. Ini menjaga
ketentuan redistribusi tiap penerbit sekaligus membuat repositori tetap ringan.

Katalog lengkap termasuk alasan tiap dataset dipilih atau dibuang ada di
[`../datasets.md`](../datasets.md).

### 5.2 Model terpilih

**SegFormer-B0** dilatih pada 640 px dengan pemilihan checkpoint berdasarkan
`iou_debris`, berhenti dini pada epoch 40.

`runs/combined_segformer_b0_640/summary.json`, selesai 2026-08-17T14:17:02Z.

---

## 6. Hasil evaluasi model

### 6.1 Dua angka, keduanya dilaporkan

Pelaporan model yang baik menyertakan angka validasi **dan** angka uji. Validasi
dipakai untuk memilih checkpoint, sehingga secara definisi menguntungkan model
yang dipilih; angka uji tidak ikut menentukan pilihan apa pun, dan karena itu
menjadi perkiraan yang lebih tepat untuk data baru.

| Pengukuran | Kelas | Nilai | Sumber |
|---|---|---|---|
| Validasi | debris | IoU 0,7313 | `runs/combined_segformer_b0_640/summary.json` |
| **Uji** | **debris** | **IoU 0,4743** | `bench/accuracy.json` |
| Uji | debris | presisi 0,5327 · **recall 0,8121** | idem |
| Uji | water | IoU 0,8034 | idem |
| Uji | background | IoU 0,9640 | idem |

**Bacaan atas angka ini.** Air dan latar tersegmentasi kuat — IoU 0,8034 dan
0,9640. Untuk sampah, **recall 0,8121 adalah angka yang paling menentukan**: model
menemukan empat dari lima piksel sampah yang ada.

Untuk sistem peringatan, recall memang yang harus diutamakan — sampah yang
terlewat berarti peringatan yang tidak muncul. Presisi 0,5327 berarti sebagian
piksel yang ditandai bukan sampah, dan kesalahan jenis itu tertahan di lapis
berikutnya: putusan tidak dipicu oleh satu piksel, melainkan oleh **luas total
yang melewati ambang 18%**.

### 6.2 Perbandingan tujuh arsitektur

Seluruh kandidat diukur dengan protokol yang sama. Latensi diukur pada CPU satu
utas sebagai pembanding setara antar-model.

| Model | Params (juta) | GFLOPs @640 | Latensi CPU | IoU debris (uji) |
|---|---|---|---|---|
| **segformer_b0** | **3,72** | 26,1 | 1.012,9 ms | **0,4743** |
| lraspp_mnv3 | 3,22 | 6,1 | 188,9 ms | 0,4191 |
| deeplabv3plus_mnv3 | 4,71 | 14,5 | 422,2 ms | 0,4131 |
| unet_mnv3 | 6,69 | 38,6 | 636,3 ms | 0,3851 |
| fast_scnn | 1,14 | 2,6 | 83,6 ms | — |
| deeplabv3_mnv3 | 11,02 | 30,7 | 447,5 ms | — |
| unet_effnet_lite | 5,20 | 36,4 | 641,8 ms | — |

SegFormer-B0 unggul **+0,055 IoU** atas kandidat terbaik berikutnya dengan jumlah
parameter hampir terkecil kedua.

**Latensinya di CPU memang tertinggi, dan itulah justru alasan arsitektur sistem
memisahkan Pi dari server.** Pada GPU model ini berjalan 28 ms/bingkai (±35 fps),
jauh melampaui kebutuhan karena aliran kamera hanya 30 fps. Tabel CPU tetap
dilaporkan karena ia yang menjelaskan pemisahan itu: menaruh model di Pi akan
memaksa turun ke LR-ASPP atau Fast-SCNN dan kehilangan 0,05–0,09 IoU pada kelas
yang paling sulit.

---

## 7. Pengujian sistem

### 7.1 Uji perangkat lunak otomatis

**214 uji di tiga rangkaian terpisah**, seluruhnya berjalan tanpa kamera, GPU,
maupun jaringan — kamera, model, dan penyimpanan disuntikkan sebagai objek
pengganti.

| Rangkaian | Jumlah | Perintah |
|---|---|---|
| Python | **95 lulus** | `PYTHONPATH=src pytest tests/ -q` |
| Web | **72 lulus**, 11 berkas | `cd web && npx vitest run` |
| Firmware (host) | **47 lulus** | `powershell tests\firmware\run_tests.ps1` |

Uji firmware dikompilasi dengan g++ langsung ke biner host — tanpa Arduino, tanpa
perangkat keras. Itu mungkin karena berkas `logic_*.h` adalah C++ murni; pemisahan
`logic_` versus `hw_` dirancang persis untuk ini.

**Uji-uji ini terbukti menggigit, bukan sekadar lulus.** Mutasi `>` menjadi `>=`
disuntikkan sengaja ke ambang mesin keadaan level, dan tertangkap oleh pemeriksaan
batas. Seluruh nilai uji firmware juga diturunkan dari konstanta `config.h`, bukan
angka mati, sehingga penyetelan ambang untuk lokasi baru membawa uji-nya serta.

### 7.2 Ketahanan aliran kamera

Satu lintasan 180 detik terhadap `TBCare.local:81/stream`:

| Butir | Nilai |
|---|---|
| Bingkai diterima | **5.402** |
| Laju | **30,0 fps** |
| Jeda terburuk antar bingkai | **0,18 detik** |
| Putus | **nol** |

### 7.3 Pemulihan otomatis dari putus jaringan

Sumber diputus sengaja di tengah jalan, lalu dihidupkan kembali. Gelung inferensi
**pulih sendiri pada percobaan ke-3** dengan jeda menaik 1→2→4→8→16→30 detik,
tanpa proses mati dan tanpa campur tangan.

Sistem membedakan berkas video yang habis dari aliran yang terputus — keduanya
tiba di titik kode yang sama, tetapi hanya yang kedua yang perlu disambung ulang.
Saat pulih, yang diatur ulang hanyalah yang dirusak jeda: cap waktu bingkai
sebelumnya dan estimator kecepatan. Riwayat penghalusan dan monitor penyumbatan
dipertahankan, karena adegannya sama.

### 7.4 Uji rantai penuh terhadap adegan nyata

Aliran Pi diarahkan ke rig berisi sampah sungguhan, satu sesi tanpa henti:

| Butir | Nilai |
|---|---|
| Baris `observations` tercatat | **82.777** dalam 69 menit |
| Laju tulis | ±26 baris/detik |
| Rata-rata luas tutupan | 0,0883 |
| Puncak luas tutupan | 0,274 |
| Baris beralarm | 29.121 |
| Jeda terburuk antar baris | 0,13 detik |

Total sepanjang pengembangan: **502.210 baris** `observations`.

**Rantai lengkap terbukti bekerja ujung ke ujung.** Sampah nyata dimasukkan ke
bidang pandang, model menandainya, luasnya melewati ambang 18%, dan dasbor
berpindah ke keadaan `blocked` dengan alasan tercetak: `area 0,21 ≥ 0,18`. Seluruh
rantai — kamera, model, basis data, putusan, tampilan — berjalan dalam waktu nyata
tanpa satu pun langkah manual.

### 7.5 Jalur pengiriman ESP32

**219 baris** tersimpan di `esp_readings`.

| Butir | Hasil |
|---|---|
| Baris muncul di basis data | **LULUS** |
| Idempotensi kirim ulang | **LULUS** — `INSERT OR IGNORE`, kiriman kedua menjawab `inserted: 0` |
| Sensor ultrasonik | **LULUS** — membaca jarak dengan benar |
| Tipping bucket | **LULUS** — `tip_total` 0→148, konversi mm/jam benar |
| NTP dengan cadangan RTC | **LULUS** — kedua jalur waktu terpakai |
| Kekuatan sinyal | −61 s/d −78 dBm, stabil sepanjang uji |

**Jam berpindah sendiri ke RTC saat NTP tidak tersedia**, dan tiap baris membawa
kolom `time_src` yang menyatakan dari mana jamnya berasal — sehingga sumber waktu
tiap pengukuran bisa ditelusuri belakangan.

### 7.6 Endpoint unggah gambar

Kelima jalur dijawab sesuai rancangan, termasuk penolakan keamanan:

| Kirim | Balasan |
|---|---|
| JPEG sah ke `frame` / `mask` | `200 {"name":"frame","bytes":68}` |
| Badan kosong | `400 empty body` |
| Bukan JPEG | `415 body is not a JPEG` |
| Nama tak dikenal | `404 unknown preview: status` |
| Percobaan traversal `../../etc/passwd` | `404 unknown preview` |

Nama berkas dipetakan lewat himpunan tertutup, bukan jalur yang disanitasi —
sehingga percobaan traversal tidak pernah menyentuh sistem berkas.

---

## 8. Lingkup dan batas rancangan

Batas berikut adalah keputusan rancangan yang disengaja.

**Satu unit kamera per pintu air.** Banyak kamera dalam satu basis data berada di
luar lingkup: SQLite mode WAL mengizinkan satu penulis, dan itu memadai untuk satu
titik pantau. Menambah titik pantau berarti menambah satu unit lengkap dengan
basis datanya sendiri — nama site pada tiap baris sudah menyiapkan pemisahan itu.

**Kamera hanya melihat permukaan.** Penyumbatan di bawah air tidak terdeteksi
kamera. Karena itu jalur ultrasonik ada: tinggi muka air naik apa pun penyebab
penyumbatannya, sehingga kedua jalur saling menutupi.

**Sistem melaporkan, operator memutuskan.** Pembersihan dan pengoperasian pintu
tetap tindakan manusia. Sistem tidak pernah menggerakkan apa pun kecuali relai
pompa pada rig uji.

**Ambang disetel per lokasi.** Nilai 18% dan ambang tinggi air berasal dari
konfigurasi, bukan dari kode, sehingga pemasangan di pintu air lain adalah
penyetelan berkas — bukan penulisan ulang program. Zona pintu digambar operator di
tempat dan tersimpan sebagai koordinat pecahan, agar tetap sahih ketika kamera
diganti atau resolusinya berubah.

**Jaringan lokal, bukan internet.** Seluruh pemrosesan terjadi di perangkat
sendiri; tidak ada video yang keluar dari jaringan. Konsekuensinya sistem
dirancang untuk jaringan tertutup dan tidak menyertakan lapisan autentikasi yang
akan dibutuhkan bila dipaparkan ke internet.

---

## 9. Simpulan

**Rantai lengkap berjalan waktu nyata dan terbukti ujung ke ujung.** Kamera →
model → basis data → putusan → dasbor menghasilkan 82.777 baris dalam 69 menit
tanpa putus, dengan jeda terburuk antar baris 0,13 detik. Sampah sungguhan yang
dimasukkan ke bidang pandang menaikkan keadaan sistem ke `blocked` dengan alasan
tercetak.

**Segmentasi kuat pada kelas yang menopang pengukuran.** Air IoU 0,8034, latar
0,9640, dan recall sampah 0,8121 — model menemukan empat dari lima piksel sampah,
yang merupakan sisi yang benar untuk sistem peringatan.

**Pemilihan model berdasar bukti, bukan preferensi.** Tujuh arsitektur diukur
dengan protokol identik; yang menang unggul 0,055 IoU dengan jumlah parameter
hampir terkecil kedua.

**Sistem bertahan terhadap gangguan yang wajar terjadi di lapangan.** Aliran yang
terputus disambung ulang sendiri. Server yang mati tidak menghilangkan data
sensor, karena microSD menyimpan lebih dulu dan kursor unggah hanya maju setelah
server mengonfirmasi. Peringatan BAHAYA tetap sampai lewat SMS meski seluruh sisi
komputer padam.

**Perangkat lunaknya diuji, dan ujinya diuji.** 214 pemeriksaan otomatis di tiga
bahasa, dengan mutasi yang disuntikkan sengaja untuk membuktikan uji-uji itu masih
menangkap kesalahan.

**Arah pengembangan berikutnya:** menambah citra dari lokasi penerapan ke data
latih untuk menyetel model pada geometri kamera dan jenis sampah setempat, serta
menampilkan debit air di dasbor — informasi yang disebut operator sebagai paling
dibutuhkan, dan perhitungannya sudah tersedia di `src/physics.py`.

---

## 10. Angka kunci untuk dikutip

| Besaran | Nilai | Sumber |
|---|---|---|
| IoU debris — validasi / uji | 0,7313 / 0,4743 | `summary.json` · `bench/accuracy.json` |
| Recall debris, uji | **0,8121** | `bench/accuracy.json` |
| IoU water, uji | 0,8034 | idem |
| IoU background, uji | 0,9640 | idem |
| Kandidat arsitektur dibandingkan | 7 | `bench/cost.json` |
| Ukuran model terpilih | 3,72 juta parameter · 26,1 GFLOPs @640 | idem |
| Latensi GPU | 28 ms/bingkai (±35 fps) | RTX 5050 |
| Baris `observations` total | 502.210 | basis data |
| Sesi uji rantai penuh | 82.777 baris dalam 69 menit | idem |
| Puncak luas tutupan terukur | 0,274 | idem |
| Baris `esp_readings` | 219 | idem |
| Ketahanan aliran kamera | 5.402 bingkai · 30,0 fps · jeda 0,18 s | uji 180 detik |
| Pemulihan putus jaringan | percobaan ke-3, otomatis | uji putus sengaja |
| Uji otomatis | 214 (95 + 72 + 47) | tiga rangkaian |
| Baris kode | 11.210 + 1.599 uji | `wc -l` |

---

## 11. Rujukan silang ke dokumen lain

| Ingin tahu | Baca |
|---|---|
| Struktur kode dan cara menjalankan | [01](01-repositori.md) |
| Penjelasan teknis dan keputusan desain | [02](02-dokumentasi-teknis.md) |
| Diagram arsitektur dan alur per bingkai | [03](03-arsitektur.md) |
| Daftar teknologi, versi, dan konstanta | [04](04-spesifikasi.md) |
| Skema basis data dan seluruh route API | [05](05-database-api.md) |
| Evaluasi model dan perbandingan arsitektur | [06](06-model-ai.md) |
| Keluaran mentah seluruh pengujian | [07](07-data-pengujian.md) |
| Protokol pengujian dan hasilnya | [08](08-protokol-uji.md) |
| Tangkapan layar dan berkas media | [09](09-dokumentasi-visual.md) |
| Referensi dan penggunaan AI | [10](10-referensi-batasan-ai.md) |
| Hasil wawancara operator | [`../hasil_wawancara_operator.md`](../hasil_wawancara_operator.md) |

---

[← Daftar isi](README.md) · [← Sebelumnya: Referensi, batasan, penggunaan AI](10-referensi-batasan-ai.md)
