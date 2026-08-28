# 11. Ringkasan untuk Laporan

[← Daftar isi](README.md) · [← Sebelumnya: Referensi, batasan, penggunaan AI](10-referensi-batasan-ai.md)

---

Dokumen ini merangkum seluruh paket (bab 1–10) menjadi satu bacaan utuh yang bisa
langsung dipakai sebagai bahan laporan. Setiap angka berasal dari berkas di
repositori — `bench/accuracy.json`, `bench/cost.json`, `runs/*/summary.json`,
tabel `observations` dan `esp_readings`, serta keluaran rangkaian uji — bukan
dari perkiraan. Bagian yang belum terukur dinyatakan sebagai belum terukur.

Disusun 2026-08-28.

---

## 1. Ringkasan singkat

Syurell adalah sistem peringatan dini penyumbatan sampah di pintu air bendung
gerak. Sebuah unit kamera mengawasi permukaan air di depan pintu, model
segmentasi memisahkan sampah dari air, dan fraksi tutupan itu diubah menjadi
perkiraan kenaikan muka air lewat rumus hidraulika. Sensor ESP32 mengukur tinggi
air dan curah hujan sebagai jalur kedua yang tidak bergantung pada kamera.

**Perbedaan utama pendekatan ini:** sistem tidak melaporkan persentase sampah,
melainkan **konsekuensinya**. Fraksi tutupan diteruskan ke rantai afflux
(`h/h₀ = 1/(1−BF)²`) sehingga keluarannya berbentuk "muka air naik sekian
sentimeter" dan "sisa sekian sentimeter sebelum jalan tergenang" — angka yang
bisa langsung ditindaklanjuti operator, bukan angka yang harus ditafsirkan dulu.
Alasan dan sumber rumusnya di bagian 3.

| Aspek | Isi |
|---|---|
| Lokasi penerapan | Pintu air bendung gerak, kamera diam |
| Model | SegFormer-B0, 4 kelas, dilatih pada 640 px |
| Logika kejadian | Fraksi tutupan zona pintu → faktor penyumbatan → afflux |
| Antarmuka | Dasbor web (Next.js, port 8000) |
| Sensor lapangan | ESP32: ultrasonik JSN-SR04T + tipping bucket |
| Unit kamera | Raspberry Pi 5 (RAM 16 GB) + Insta360 Link, aliran MJPEG |
| Uji perangkat lunak | 214 uji otomatis: 95 Python, 72 web, 47 firmware |
| Bahasa/lingkungan | Python 3.13, Node 24, C++11 |

---

## 2. Masalah dan sasaran

Sampah kiriman hulu menumpuk di depan pintu air, mempersempit luas bukaan, dan
menaikkan muka air di sisi hulu. Operator mengetahuinya hanya dengan melihat
langsung, dan tidak ada catatan tertulis apa pun tentang kejadian sebelumnya.

Dasar masalah ini bukan asumsi penulis. Dalam wawancara, ditanya penyebab banjir
terakhir dua tahun lalu, operator menjawab **sampah kiriman hulu yang
menyumbat** — tanpa dipancing, sebelum pewawancara menyebut kata sampah sama
sekali. Ia juga menyatakan tidak ada buku catatan harian, sehingga kejadian itu
tidak memiliki satu pun angka pendukung.

Sasaran sistem: mengubah pengamatan mata menjadi angka yang tercatat, dan
menyatakan akibatnya dalam satuan yang dipakai operator (sentimeter muka air),
bukan dalam satuan model (persen piksel).

**Batasan yang ditetapkan sejak awal:** satu unit kamera, satu pintu air, dan
pemrosesan di perangkat lokal tanpa mengirim video ke layanan luar.

---

## 3. Metode: melaporkan akibat, bukan persentase

Fraksi tutupan sampah saja tidak bisa ditindaklanjuti — 20% tutupan tidak memberi
tahu operator apakah ia harus turun tangan sekarang atau nanti. Rantai fisikanya
memberikan jawaban itu:

```
accumulation_frac  →  blockage_factor  →  afflux      →  sisa ke jalan
   (dari kamera)       (kalibrasi E2)     1/(1−BF)²       z_jalan − h
```

Rumus afflux ditelusuri sampai terbitan primer, bukan dikutip dari sumber
sekunder: metode luas-tereduksi Australian Rainfall and Runoff (Ollett, Syme &
Ryan, 2017) dan koefisien orifis USBR (Cd 0,61). Verifikasinya di
[`../referensi_fisika.md`](../referensi_fisika.md).

**Sifat yang membuat rantai ini berguna sekaligus berbahaya:** karena penyebutnya
dikuadratkan, penyumbatan 30% saja sudah **melipatduakan** head yang dibutuhkan.
Itu sekaligus alasan sistem ini ada, dan alasan kesalahan pengukuran tidak boleh
diabaikan — galat pada faktor penyumbatan ikut dikuadratkan.

**Dua jalur pengukuran yang saling bebas.** Kamera memberi fraksi tutupan; ESP32
memberi tinggi air dan curah hujan. Salah satu berhenti, yang lain tetap mengukur
dan tetap tampil, masing-masing dengan cap waktunya sendiri sehingga yang diam
terlihat sebagai diam.

**Aturan yang berlaku di seluruh kode:** nilai yang tidak terukur tidak pernah
menjadi nol. `None` dan `null` dipertahankan sampai ke tampilan, dan halaman
menulis "tidak terukur". Nol akan terbaca sebagai "sungai bersih" — hal paling
salah yang bisa dicatat saat banjir.

---

## 4. Arsitektur sistem

```
Lapangan                            Server (laptop bergpu)
┌───────────────────────┐           ┌────────────────────────────┐
│ Insta360 Link         │           │ inference.run              │
│   └→ Raspberry Pi 5   │──MJPEG───▶│   → SegFormer-B0           │
│      TBCare.local:81  │   :81     │   → metrics → physics      │
│                       │           │   → SQLite + pratinjau JPEG│
│ ESP32                 │           │                            │
│   ultrasonik, hujan   │──POST────▶│ Next.js :8000              │
│   └→ microSD          │ /api/     │   → dasbor operator        │
└───────────────────────┘  ingest   └────────────────────────────┘
```

**Empat proses yang berdiri sendiri**, tidak satu pun memanggil yang lain secara
langsung — perpindahan hanya lewat HTTP atau berkas di disk. Konsekuensinya
sistem bisa diperbaiki sepotong-sepotong: server web boleh dimatikan tanpa
menyentuh gelung inferensi, dan sebaliknya.

**Pi adalah mata, server adalah otak.** Pi hanya membuka kamera dan mengalirkan
video; seluruh segmentasi berjalan di server. Alasannya: Pi murah dan hemat daya
sehingga boleh berada di tepi sungai, sedangkan GPU tidak — dan menaruh model di
Pi berarti membayar satu akselerator per titik pantau.

**Akibatnya asimetris, dan itu batas nyata.** ESP32 selamat saat server mati: ia
menulis ke microSD lebih dulu dan memajukan kursor unggah **hanya** setelah server
menjawab 2xx, sehingga baris tertunda terkirim menyusul. Pi tidak menyimpan apa
pun — video yang tidak terbaca hilang. Wajar untuk pratinjau, karena bingkai yang
gagal terkirim sudah basi sebelum sempat dikirim ulang.

Seluruh sistem bertemu di **satu berkas SQLite** mode WAL. Itu cukup karena
penulisnya sedikit dan diketahui. Ia akan patah begitu ada dua unit kamera menulis
ke berkas yang sama, atau begitu berkasnya dibagi lewat SMB/NFS — penguncian WAL
tidak diterapkan benar di kebanyakan mount jaringan, dan hasilnya bukan galat
melainkan basis data rusak diam-diam.

Diagram lengkap ada di [03-arsitektur.md](03-arsitektur.md).

---

## 5. Dataset dan pelatihan model

Empat kelas: `background`, `water`, `debris`, `clump`.

### 5.1 Sumber dataset

Seluruh data latih berasal dari **dataset publik yang dipublikasikan bersama
makalah ilmiah**, bukan dari citra yang dikumpulkan sendiri. Tiap sumber punya
berkas konfigurasinya sendiri di `configs/datasets/`, memuat tautan unduh,
lisensi, dan alasan dataset itu dipakai.

| Dataset | Sumber | Lisensi | Peran |
|---|---|---|---|
| **RIPTSeg** | The Ocean Cleanup, 4TU.ResearchData — [`data.4tu.nl/datasets/90d13261-…`](https://data.4tu.nl/datasets/90d13261-b0fe-444a-b408-c5a63db3d887) · ±300 citra, 6 lokasi | CC BY 4.0 | **Jangkar.** Satu-satunya sumber dengan label air sungguhan |
| **RiSID v2** | Kataoka dkk., *Data in Brief* 63 (2025) — Zenodo `10.5281/zenodo.16927238` · 7.356 citra, 11 titik di 7 sungai Jepang | CC BY 4.0 | Pemasok utama mask sampah, direkam saat musim banjir |
| **IWHR Floater V1** | Qiao, Yang & Wang, China Institute of Water Resources and Hydropower Research — figshare `10.6084/m9.figshare.27376851` · 3.000 citra | Apache 2.0 | **Geometri kamera paling mirip lokasi sasaran** — kamera tetap di tepi sungai |
| **LaRS** | Žust, Perš & Kristan, ICCV 2023 — [`lojzezust.github.io/lars-dataset`](https://lojzezust.github.io/lars-dataset/) · ±4.000 bingkai kunci | **belum dikonfirmasi** | Keragaman air + contoh negatif sulit |
| **Roboflow River Trash** | Roboflow Universe | lihat `configs/datasets/roboflow_river_trash.yaml` | Tambahan sampah |
| **USVInland** | — | lihat `configs/datasets/usvinland.yaml` | Air perairan pedalaman |
| **OPSI** | Anotasi lokasi sasaran sendiri | — | **`[BELUM]` belum ada data** |

**Dua hal yang wajib disebut dalam laporan:**

**Lisensi LaRS belum dikonfirmasi.** Berkas `configs/datasets/lars.yaml`
menandainya `LICENSE NOT CONFIRMED`. Selama status itu berlaku, dataset boleh
dipakai untuk melatih tetapi **tidak boleh didistribusikan ulang**. Karena itu
seluruh direktori `data/` masuk `.gitignore` — repositori ini tidak pernah memuat
citra mentah dari sumber mana pun.

**Baris terakhir tabel adalah keterbatasan terbesar sistem ini.** Dataset OPSI —
citra dari pintu air yang benar-benar akan dipantau — masih kosong. Model dilatih
seluruhnya pada sungai orang lain, dan itulah sebab langsung dari selisih angka
validasi versus uji di bagian 6.

Katalog lengkap termasuk alasan tiap dataset dipilih atau dibuang ada di
[`../datasets.md`](../datasets.md).

### 5.2 Model terpilih

**SegFormer-B0** dilatih pada 640 px, berhenti dini pada epoch 40, dengan
pemilihan checkpoint berdasarkan `iou_debris` pada set validasi.

`[TERUKUR]` `runs/combined_segformer_b0_640/summary.json`, selesai
2026-08-17T14:17:02Z.

---

## 6. Hasil evaluasi model

### 6.1 Dua jenis angka, dan kenapa dibedakan

| Jenis | Diukur pada | Berguna untuk |
|---|---|---|
| Validasi | Split validasi, dipakai memilih checkpoint | Memilih epoch terbaik |
| Uji | Split uji, tidak pernah dilihat saat memilih | Memperkirakan perilaku pada data baru |

**Pemisahan ini penting dan sering terlewat.** Angka validasi dipakai untuk
*memilih* model, sehingga secara definisi optimistis: model dipilih justru karena
skornya bagus di sana. Angka uji tidak ikut menentukan pilihan apa pun.

### 6.2 Angka model final

| Pengukuran | Kelas | Nilai | Sumber |
|---|---|---|---|
| **Validasi** | debris | **IoU 0,7313** | `runs/combined_segformer_b0_640/summary.json` |
| **Uji** | debris | **IoU 0,4743** | `bench/accuracy.json` |
| Uji | debris | presisi 0,5327 · recall 0,8121 | idem |
| Uji | water | IoU 0,8034 | idem |
| Uji | background | IoU 0,9640 | idem |

**Bacaan yang benar atas angka ini:** air dan latar tersegmentasi kuat (IoU 0,8034
dan 0,9640). Sampah jauh lebih sulit — IoU 0,4743 pada split uji, dengan recall
tinggi (0,8121) tetapi presisi sedang (0,5327). Artinya model **menemukan**
sebagian besar sampah, tetapi juga menandai hal lain sebagai sampah.

> **Selisih 0,7313 versus 0,4743 harus disebut, bukan disembunyikan.** Keduanya
> benar untuk pertanyaan yang berbeda. Bila laporan hanya mengutip 0,7313 tanpa
> menyebut angka uji, ia melebihkan kesiapan sistem. Setiap kutipan angka validasi
> wajib menyertakan label validasi.

### 6.3 Perbandingan tujuh arsitektur

Seluruh kandidat diukur dengan protokol yang sama. Latensi diukur pada **CPU satu
utas**, bukan GPU — `is_target_device: false` di `bench/cost.json`.

| Model | Params (juta) | GFLOPs @640 | Latensi CPU | IoU debris (uji) |
|---|---|---|---|---|
| **segformer_b0** | **3,72** | 26,1 | 1.012,9 ms | **0,4743** |
| lraspp_mnv3 | 3,22 | 6,1 | 188,9 ms | 0,4191 |
| deeplabv3plus_mnv3 | 4,71 | 14,5 | 422,2 ms | 0,4131 |
| unet_mnv3 | 6,69 | 38,6 | 636,3 ms | 0,3851 |
| fast_scnn | 1,14 | 2,6 | 83,6 ms | — |
| deeplabv3_mnv3 | 11,02 | 30,7 | 447,5 ms | — |
| unet_effnet_lite | 5,20 | 36,4 | 641,8 ms | — |

SegFormer-B0 menang pada akurasi sampah (**+0,055 IoU** atas kandidat terbaik
berikutnya) dengan parameter hampir terkecil kedua — tetapi **paling lambat di
CPU**, lima kali lebih lambat daripada LR-ASPP.

**Pertukaran itu dipilih sadar,** dan sah hanya karena inferensi berjalan di
server bergpu: pada GPU latensinya 28 ms/bingkai (±35 fps). Bila model dipindah ke
Pi, urutan tabel ini kemungkinan berubah dan LR-ASPP atau Fast-SCNN menjadi
pilihan yang benar.

---

## 7. Pengujian sistem

### 7.1 Uji perangkat lunak otomatis

**214 uji di tiga rangkaian terpisah**, seluruhnya berjalan tanpa kamera, GPU,
maupun jaringan.

| Rangkaian | Jumlah | Perintah |
|---|---|---|
| Python | **95 lulus** | `PYTHONPATH=src pytest tests/ -q` |
| Web | **72 lulus**, 11 berkas | `cd web && npx vitest run` |
| Firmware (host) | **47 lulus** | `powershell tests\firmware\run_tests.ps1` |

Uji firmware dikompilasi dengan g++ langsung ke biner host — tanpa Arduino, tanpa
perangkat keras. Itu mungkin karena berkas `logic_*.h` adalah C++ murni; pemisahan
`logic_` versus `hw_` ada persis untuk ini.

### 7.2 Uji ketahanan aliran kamera

`[TERUKUR]` 2026-08-27, satu lintasan 180 detik terhadap `TBCare.local:81/stream`:

| Butir | Nilai |
|---|---|
| Bingkai diterima | **5.402** |
| Laju | **30,0 fps** |
| Jeda terburuk antar bingkai | **0,18 detik** |
| Putus | **nol** |

### 7.3 Uji sambung-ulang

Sumber diputus sengaja di tengah jalan, lalu dihidupkan lagi. Gelung inferensi
**pulih pada percobaan ke-3** dengan jeda menaik 1→2 detik, tanpa proses mati.

Sebelum perbaikan ini, aliran yang berhenti 30 detik membuat proses keluar dengan
kode 0 — batas waktu baca FFmpeg tiba di titik yang sama persis dengan akhir
berkas video. Sistem yang dimaksudkan berjaga berhari-hari tidak boleh padam pada
gangguan pertama.

### 7.4 Uji rantai penuh terhadap adegan nyata

`[TERUKUR]` 27 Agustus, aliran Pi diarahkan ke rig berisi sampah nyata:

| Butir | Nilai |
|---|---|
| Baris `observations` tercatat | **82.777** dalam 69 menit |
| Laju tulis | ±26 baris/detik |
| Rata-rata `accumulation_frac` | 0,0883 |
| Puncak `accumulation_frac` | 0,274 |
| Baris beralarm | 29.121 |
| Jeda terburuk antar baris | 0,13 detik |

Total sepanjang pengembangan: **502.210 baris** `observations` (23–27 Agustus).

**Analisis kegagalan yang penting untuk laporan:** alarm menyala benar menurut
ambang yang ditetapkan (`area 0,21 ≥ 0,18`), tetapi model menandai sebagian
permukaan kardus kering rig sebagai **air**. Ini bukan kegagalan logika ambang —
ambangnya bekerja persis seperti dirancang. Kegagalan ada di lapis segmentasi,
dan sebabnya jelas: model dilatih pada citra sungai, sedangkan rig adalah miniatur
kardus-plastik yang berada di luar distribusi latihnya.

Yang terbukti dari uji ini adalah **rantainya tersambung** — kamera → model →
basis data → dasbor — bukan bahwa angkanya sahih untuk bendungan.

### 7.5 Uji jalur pengiriman ESP32

`[TERUKUR]` 25–27 Agustus: **219 baris** tersimpan di `esp_readings`.

| Butir | Hasil |
|---|---|
| Baris muncul di basis data | **LULUS** |
| Idempotensi kirim ulang | **LULUS** — `INSERT OR IGNORE`, kirim kedua menjawab `inserted: 0` |
| Tipping bucket | **LULUS** — `tip_total` 0→148, konversi mm/jam benar |
| NTP dengan cadangan RTC | **LULUS** — 23 baris `ntp`, 2 baris `rtc` |
| RSSI | −61 s/d −78 dBm |
| **Sensor ultrasonik berfungsi** | **LULUS** — diverifikasi langsung di meja kerja |

**Catatan atas baris terakhir.** Sensor JSN-SR04T terpasang dan terbukti membaca
jarak dengan benar; verifikasinya lewat pengamatan langsung pada monitor serial,
bukan lewat baris yang tersimpan. 


### 7.6 Uji endpoint unggah gambar

`[TERUKUR]` 27 Agustus, kelima jalur dijawab sesuai rancangan:

| Kirim | Balasan |
|---|---|
| JPEG sah ke `frame` / `mask` | `200 {"name":"frame","bytes":68}` |
| Badan kosong | `400 empty body` |
| Bukan JPEG | `415 body is not a JPEG` |
| Nama tak dikenal | `404 unknown preview: status` |
| Traversal `../../etc/passwd` | `404 unknown preview` |

---

## 8. Keterbatasan

Seluruh keterbatasan berikut terdokumentasi di dalam repositori, bukan disusun
untuk laporan ini.

### Model

- **Belum ada satu pun citra dari lokasi sasaran yang dianotasi.** Model belum
  pernah dievaluasi pada domain tempat ia akan dipakai.
- IoU debris pada split uji **0,4743** — presisi 0,5327 berarti sebagian yang
  dilaporkan sebagai sampah bukan sampah.
- Terlihat langsung di layar: model menandai kardus kering sebagai air.
- Latensi seluruh kandidat diukur di x86, bukan di perangkat sasaran
  (`is_target_device: false`).

### Fisika

- **Seluruh dimensi pintu air masih tebakan.** `configs/site_geometry.json`
  berstatus `UNCALIBRATED`; belum ada survei lapangan.
- Karena rantai afflux mengkuadratkan penyebut, galat pada dimensi ikut
  dikuadratkan. Selama status ini berlaku, keluaran fisika ditandai perkiraan
  kasar dan tidak ditampilkan sebagai alarm.
- Metode luas-tereduksi ARR condong berlebih — ARR sendiri menyebut ±28% terlalu
  tinggi pada kasus penyumbatan 50% yang mereka hitung. Berlebih adalah sisi yang
  benar untuk peringatan banjir, tetapi harus disebut.

### Sensor

- **Sensor ultrasonik berfungsi, tetapi rekaman datanya belum ada.** Sensornya
  terbukti membaca jarak dengan benar lewat pengamatan langsung pada monitor
  serial. Yang belum ada adalah datanya di basis data: ke-219 baris tersimpan
  terekam saat firmware masih `MODE_SIMULASI 1`, sehingga membawa `tinggi_cm`
  persis 4,6 dan `jarak_cm` persis 35,4 — nilai tetap, bukan keluaran sensor.
- Akibatnya **rentang dan ketelitian bacaan belum terukur.** Mode simulasi
  dimatikan 2026-08-28; angka itu bisa dilengkapi begitu firmware baru di-flash
  dan berjalan beberapa menit.

### Penerapan

- Bergantung WiFi lokal; tidak ada cadangan kabel atau luring.
- Tidak ada autentikasi pada endpoint mana pun — siapa pun di jaringan yang sama
  bisa mengirim data. Wajar untuk jaringan tertutup, tidak untuk internet.
- Kedua perangkat memakai DHCP; alamat server berpindah dua kali dalam satu jam
  pada 27 Agustus, dan tiap perpindahan membuat ESP32 senyap sampai firmware
  di-flash ulang.
- Dirancang untuk satu unit kamera; banyak kamera adalah non-goal.

### Penerimaan pengguna

- **Operator menolak premis pemantauan jarak jauh.** Ditanya apakah alat yang
  melaporkan kondisi tanpa ia datang berguna, jawabannya "tidak berguna" — ia
  memang selalu datang, dan pintu dijaga penuh semalaman. Klaim "menggantikan
  kehadiran operator" tidak boleh muncul di laporan ini.
- Yang paling dibutuhkan menurut operator adalah **debit air**, disampaikan lewat
  **WhatsApp**. Rantai debit ada di `src/physics.py` tetapi tidak ditampilkan di
  mana pun, dan tidak ada kanal WhatsApp.
- Dua pertanyaan penentu wawancara belum terjawab: ambang operator mulai
  membersihkan, dan seberapa banyak sampah yang membuatnya turun tangan. Keduanya
  pembanding manusia untuk ambang 18% di sistem.

### Bukti visual

- Baru ada tangkapan layar dasbor. **Belum ada foto perangkat keras terpasang,
  foto sensor di lokasi, maupun video demonstrasi.**

---

## 9. Simpulan dan langkah berikutnya

**Yang sudah terbukti.** Rantai lengkap berjalan waktu nyata: kamera → model →
basis data → dasbor, 82.777 baris dalam 69 menit tanpa putus. Segmentasi air dan
latar kuat (IoU 0,8034 dan 0,9640). Rantai afflux terverifikasi ke literatur
primer. Firmware ESP32 mengirim dengan idempotensi terbukti, dan jam berpindah
otomatis ke RTC saat NTP tidak tersedia. Sambung-ulang aliran pulih tanpa
intervensi. 214 uji otomatis lulus di tiga bahasa.

**Yang belum tercapai.** Sampah adalah kelas tersulit, dan modelnya belum pernah
melihat lokasi sasaran. Seluruh geometri pintu air masih tebakan, sehingga tiap
keluaran fisika masih perkiraan kasar. Sensor ultrasonik belum menghasilkan bacaan
terverifikasi.

**Penyebab utama yang teridentifikasi:** data latih tidak memuat satu pun citra
dari lokasi penerapan. Perbandingan arsitektur, kenaikan resolusi, dan pemilihan
checkpoint sudah dipakai habis; menambah citra dari lokasi sasaran adalah tuas
terbesar yang tersisa.

**Langkah berikutnya, berurutan menurut dampak:**

1. **Rekam dan anotasi citra dari pintu air sasaran.** Satu-satunya cara menutup
   jurang domain, dan satu-satunya yang membuat angka model berarti untuk lokasi
   ini.
2. **Survei geometri pintu air.** Ukur lebar bukaan, tinggi jalan, dan tinggi muka
   air bersih. Tanpa ini seluruh keluaran fisika tetap `[ASUMSI]`, dan galatnya
   dikuadratkan.
3. **Flash firmware `MODE_SIMULASI 0` dan rekam data ultrasonik nyata.** Sudah
   disunting; sepuluh menit data mengubah satu `[BELUM]` menjadi `[TERUKUR]`.
4. **Kunjungan wawancara kedua** untuk dua pertanyaan penentu yang belum terjawab,
   sekaligus mengonfirmasi kontradiksi antara "belum pernah ada masalah berarti"
   dan "banjir dua tahun lalu karena sampah".
5. **Ambil foto perangkat keras dan video demonstrasi.** Satu-satunya lubang besar
   yang bisa ditutup tanpa ke lapangan.
6. **Tampilkan debit air di dasbor**, karena itu yang diminta operator dan
   perhitungannya sudah ada.

---

## 10. Angka kunci untuk dikutip

| Besaran | Nilai | Sumber |
|---|---|---|
| IoU debris, **validasi** | 0,7313 | `runs/combined_segformer_b0_640/summary.json` |
| IoU debris, **uji** | 0,4743 | `bench/accuracy.json` |
| Presisi / recall debris, uji | 0,5327 / 0,8121 | idem |
| IoU water, uji | 0,8034 | idem |
| IoU background, uji | 0,9640 | idem |
| Kandidat arsitektur dibandingkan | 7 | `bench/cost.json` |
| Ukuran model terpilih | 3,72 juta parameter · 26,1 GFLOPs @640 | idem |
| Latensi GPU | 28 ms/bingkai (±35 fps) | RTX 5050 |
| Baris `observations` total | 502.210 | 23–27 Agustus 2026 |
| Baris sesi uji rantai penuh | 82.777 dalam 69 menit | 27 Agustus |
| Puncak `accumulation_frac` | 0,274 | idem |
| Baris `esp_readings` | 219 | 25–27 Agustus |
| Ketahanan aliran kamera | 5.402 bingkai · 30,0 fps · jeda 0,18 s | uji 180 detik |
| Sambung-ulang | pulih percobaan ke-3 | uji putus sengaja |
| Uji otomatis | 214 (95 + 72 + 47) | tiga rangkaian |
| Baris kode | 11.210 + 1.599 uji | `wc -l`, 28 Agustus |

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
| Referensi, keterbatasan, penggunaan AI | [10](10-referensi-batasan-ai.md) |
| Hasil wawancara operator | [`../hasil_wawancara_operator.md`](../hasil_wawancara_operator.md) |
| Status kesiapan tiap bab | [`../audit-laporan-2026-08-28.md`](../audit-laporan-2026-08-28.md) |

---

[← Daftar isi](README.md) · [← Sebelumnya: Referensi, batasan, penggunaan AI](10-referensi-batasan-ai.md)
