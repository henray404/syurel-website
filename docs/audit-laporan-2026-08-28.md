# Audit kesiapan laporan — 28 Agustus 2026

Status tiap bab di [`laporan/`](laporan/): apa yang sudah terbukti, apa yang
masih tebakan, dan apa yang berubah pada revisi ini. Setiap angka berasal dari
perintah yang benar-benar dijalankan.

`docs/laporan/` · 3.525 baris · 11 berkas

| Ukuran | Nilai |
|---|---|
| Uji firmware | **47/47** |
| Uji web | **72/72**, 11 berkas |
| Uji Python | **95/95** |
| Debris IoU (validasi) | **0,7313** |
| Aset visual yang benar-benar ada | **1 foto** |

> **Sebelum revisi ini, uji firmware sesungguhnya 29/47** sementara laporan
> mengklaim 47 lulus. Itu penyimpangan paling berbahaya yang ditemukan, dan
> sudah diperbaiki.

---

## 01 — Kode sumber & repositori

`laporan/01-repositori.md` · 280 baris · **Kuat**

Pohon berkas lengkap, riwayat commit, dan perintah membangun untuk keempat
bagian: Python, web, firmware, pelatihan.

| | |
|---|---|
| **Terbukti** | Struktur direktori beranotasi; setiap perintah bisa disalin dan dijalankan ulang |
| **Diperbaiki** | Pohon `web/lib/` disesuaikan — `fisika` dan `hujan` dihapus, `bmkg` ditambah; jumlah berkas uji 10 → 11 |
| **Sisa** | Baris 14 masih menulis **28 commit**; `git rev-list --count HEAD` sekarang menjawab **33** |

---

## 02 — Dokumentasi teknis

`laporan/02-dokumentasi-teknis.md` · 365 baris · **Kuat**

Penjelasan modul demi modul, plus alasan di balik keputusan yang tidak terlihat
dari kode saja — pemisahan `logic_` versus `hw_` di firmware, yang memungkinkan
uji host tanpa perangkat keras, adalah contoh terbaiknya.

| | |
|---|---|
| **Terbukti** | Tabel modul lengkap; keputusan desain disertai alasan, bukan sekadar deskripsi |
| **Diperbaiki** | Tabel implementasi kembar tinggal validasi poligon — fisika afflux kini tunggal di Python setelah `web/lib/fisika.ts` dihapus. Satu kewajiban sinkronisasi ikut hilang |

Bab ini menyimpan bahan terkuat laporan: kegagalan yang dijelaskan
sebab-akibatnya, bukan disembunyikan. Penguji menilai pemahaman, dan pemahaman
terlihat dari bagian ini.

---

## 03 — Arsitektur & diagram alir

`laporan/03-arsitektur.md` · 352 baris · **Kuat**

Diagram Mermaid satu layar, kontrak antar-komponen, urutan waktu pengiriman
ESP32, dan tabel mode kegagalan per komponen.

| | |
|---|---|
| **Ditambah** | Raspberry Pi 5 masuk diagram sebagai unit kamera; jalur `CAM → PI → MJPEG → inferensi` menggantikan panah langsung yang melompati jaringan |
| **Ditambah** | Dua baris mode kegagalan baru: Pi mati, dan tautan Pi→server putus |
| **Ditambah** | Perilaku sambung-ulang `run.py` dijelaskan, termasuk apa yang di-reset saat pulih dan mengapa penghalus justru dipertahankan |

**Keputusan arsitektur yang layak ditonjolkan di sidang:** Pi adalah mata, server
adalah otak. Pi murah dan hemat daya sehingga boleh berada di tepi sungai; GPU
tidak. Menaruh model di Pi berarti membayar satu akselerator per titik pantau.

---

## 04 — Spesifikasi teknologi & komponen

`laporan/04-spesifikasi.md` · 292 baris · **Sebagian asumsi**

Daftar setiap komponen keras dan lunak dengan versi yang benar-benar terpasang,
plus geometri pintu air yang dipakai fisika.

| | |
|---|---|
| **Ditambah** | Raspberry Pi 5 RAM 16 GB + Insta360 Link masuk tabel perangkat keras |
| **Ditambah** | Subbab kinerja unit kamera: **5.402 bingkai, 30,0 fps, jeda terburuk 0,18 detik** dalam uji ketahanan 180 detik |
| **Diperbaiki** | Baris `[BELUM] belum pernah diuji di Pi` dihapus — ia salah membingkai rancangan. Inferensi memang tidak pernah dimaksudkan berjalan di Pi |
| **Tetap terbuka** | `[ASUMSI]` seluruh dimensi pintu air di `site_geometry.json` masih tebakan; kesalahannya dikuadratkan di rumus afflux |

**Catatan jaringan yang dibayar mahal:** alamat DHCP berpindah dua kali dalam
satu jam pada 27 Agustus, dan setiap perpindahan membuat ESP32 senyap sampai
firmware di-flash ulang. `TBCare.local` lewat mDNS sudah diverifikasi bisa dibuka
OpenCV — pakai itu, bukan alamat IP.

---

## 05 — Skema basis data & API

`laporan/05-database-api.md` · 445 baris · **Kuat**

Tiga tabel SQLite dengan penjelasan kolom demi kolom, sebelas endpoint, dan
alasan tiap keputusan skema.

| | |
|---|---|
| **Ditambah** | `POST /api/live/{frame\|mask}` didokumentasikan penuh — kelima kode balasan adalah keluaran nyata uji HTTP, termasuk percobaan traversal yang dijawab 404 |
| **Diperbaiki** | Kunci `fisika` dan `hujan` dibuang dari contoh `/api/latest`, mengikuti kartu yang dihapus |
| **Diperbaiki** | `mm_per_jam` tidak lagi menyebut "60 bin" — `RAIN_WINDOW_MIN` sudah 10 menit |
| **Diperjelas** | Diagnosis `n_sampel` ditulis ulang: bukan sensor gagal, melainkan seluruh baris berasal dari mode simulasi |

---

## 06 — Model AI & evaluasi

`laporan/06-model-ai.md` · 405 baris · **Terukur, tapi di luar domain**

Tujuh arsitektur dibandingkan dengan protokol yang sama; SegFormer-B0 menang di
**val debris IoU 0,7313** melawan 0,6304 milik baseline LR-ASPP.

| | |
|---|---|
| **Terbukti** | Perbandingan tujuh model dengan metode identik — bagian paling ilmiah di seluruh laporan |
| **Terbukti** | Latensi 28 ms/bingkai di RTX 5050 (±35 fps) |
| **Belum** | **Nol citra dari lokasi sasaran yang dianotasi.** Model belum pernah dievaluasi di domain tempat ia akan dipakai |

**Keterbatasan paling jujur yang harus ditulis,** dan terlihat langsung di layar:
model menandai kardus kering rig sebagai air. Ia dilatih pada sungai, bukan
miniatur. Yang terbukti pada 27–28 Agustus adalah **rantainya tersambung** —
kamera → model → basis data → web — bukan bahwa angkanya sahih untuk bendungan.

---

## 07 — Data mentah pengujian

`laporan/07-data-pengujian.md` · 305 baris · **Ada lubang jujur**

Data apa adanya, tanpa dipilih: kueri SQL, ringkasan statistik, dan daftar
terbuka hal yang belum ada.

| | |
|---|---|
| **Terbukti** | 219 baris `esp_readings` (25–27 Agustus); 502.210 baris `observations` |
| **Terbukti** | Tipping bucket benar; NTP dengan cadangan RTC — kedua jalur waktu terpakai |
| **Ditambah** | Catatan bahwa kenaikan `n_sampel` dari 0 ke 3–4 **bukan** tanda sensor sembuh |
| **Tetap terbuka** | 13 penanda `[BELUM]`, terbanyak di seluruh laporan — kebanyakan menunggu kerja lapangan |

---

## 08 — Protokol & hasil uji

`laporan/08-protokol-uji.md` · 375 baris · **Diperbaiki pada revisi ini**

Prosedur yang bisa diulang penguji, dengan perintahnya dicantumkan — dan justru
itu yang membongkar masalah terbesar hari ini.

| | |
|---|---|
| **Ditemukan** | Laporan mengklaim **47 lulus**; kenyataannya **18 gagal**. Ambang pernah diskalakan dari sungai (30/60 cm) ke rig (3,0/4,5 cm) dan `RAIN_WINDOW_MIN` dari 60 ke 10 menit, tanpa uji ikut menyesuaikan |
| **Diperbaiki** | Setiap nilai uji kini **diturunkan dari konstanta `config.h`**, bukan angka mati — penskalaan berikutnya membawa uji-nya serta |
| **Diverifikasi** | Mutasi `>` → `>=` disuntik ke `logic_level.h:75` dan tertangkap. Angka 47/47 berarti perilaku benar, bukan uji yang menyetujui dirinya sendiri |

Kejadian ini sendiri adalah bahan laporan yang kuat: pengujian yang menangkap
penyimpangannya sendiri lebih meyakinkan daripada angka sempurna tanpa cerita.

---

## 09 — Tangkapan layar, foto, video

`laporan/09-dokumentasi-visual.md` · 266 baris · **Paling lemah**

Satu-satunya aset visual yang benar-benar ada di repositori adalah `image.png` —
foto lokasi sasaran.

| | |
|---|---|
| **Ditambah** | Foto lokasi dibaca analitis: struktur pintu biru, sampah terapung (kangkung dan eceng gondok — persis yang disebut operator), jalan yang menjadi `z_jalan_m`, dan pantulan cermin yang membuktikan bahaya silau itu nyata |
| **Ditemukan** | `firmware/esp32/image.png` ternyata tangkapan tabel pinout, bukan foto — isinya sudah tersalin sebagai tabel di §9.3 |
| **Perlu dilengkapi** | Foto perangkat keras, tangkapan layar dasbor, dan video demo. Taruh di `docs/gambar/` dengan nama deskriptif |

**Bab inilah yang paling merugikan di penjurian,** karena juri menilai dari bukti
yang bisa dilihat. Foto lokasi yang ada pun masih tangkapan layar bercelah —
bilah alat penyunting menempel di tepi kanan dan harus dipotong.

---

## 10 — Pustaka, batasan, penggunaan AI

`laporan/10-referensi-batasan-ai.md` · 343 baris · **Kuat**

Daftar pustaka yang ditelusuri sampai terbitan primer, tujuh batasan sistem, dan
dokumentasi penggunaan AI yang ditulis terbuka.

| | |
|---|---|
| **Ditambah** | **Batasan G** — operator menolak premis pemantauan jarak jauh. Ditanya apakah alat semacam ini berguna, jawabannya "tidak berguna", karena ia memang selalu datang dan pintu dijaga penuh semalaman |
| **Ditambah** | Tiga nilai sistem yang tetap berdiri, semuanya bersandar pada jawaban wawancara lain: melihat hulu, menjadi catatan yang tak pernah ada, dan mengganti penilaian mata dengan angka |
| **Diperbaiki** | Tabel ringkasan kejujuran disegarkan ke angka hari ini |

Yang paling kuat justru jawaban tanpa dipancing: ditanya penyebab banjir
terakhir, operator menyebut **sampah kiriman hulu yang menyumbat** — sebelum
pewawancara menyebut kata sampah sama sekali. Laporan yang memuat penolakan
narasumber *dan* dukungannya jauh lebih kredibel daripada yang hanya memuat salah
satunya.

---

## Yang tersisa, berurutan menurut dampak

1. **Flash firmware `MODE_SIMULASI 0`.** Sudah disunting, tinggal dipasang.
   Sepuluh menit data mengubah satu `[BELUM]` jadi `[TERUKUR]` di dua bab. Ingat
   unggah berpindah dari 15 detik ke 5 menit — itu irama produksi, bukan
   kesalahan.
2. **Ambil foto perangkat keras dan tangkapan layar dasbor.** Bab 09 satu-satunya
   yang hampir kosong, dan satu-satunya lubang besar yang bisa ditutup tanpa ke
   lapangan.
3. **Perbaiki jumlah commit di `laporan/01-repositori.md:14`.** Tertulis 28,
   sebenarnya 33.
4. **Potong bilah alat dari `image.png`** dan catat tanggal serta arah
   pengambilannya, supaya bisa dirujuk sebagai bukti survei.
5. **Matikan uplink Pi** (`KANAYA_UPLINK_ENABLED=0`). Sekarang dua penulis mengisi
   `frame.jpg` yang sama — tidak merusak, tapi panel Kamera berkedip dan mask
   bisa tak sinkron.
