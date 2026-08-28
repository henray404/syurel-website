# 10. Referensi, Batasan, dan Dokumentasi Penggunaan AI

[← Daftar isi](README.md) · [← Sebelumnya: Dokumentasi visual](09-dokumentasi-visual.md)

---

## 10.1 Daftar pustaka

Setiap sumber di bawah **benar-benar dibaca dan dipakai**. Tidak ada yang
dicantumkan hanya untuk memanjangkan daftar. Yang belum sempat diverifikasi
ditandai begitu.

### A. Hidraulika — dasar rumus afflux

**A1.** US Bureau of Reclamation. *Water Measurement Manual*, Bab 9 (Submerged
Orifices), §5.
Dipakai untuk: `Q = Cd · A · √(2 g Δh)` dan nilai `Cd = 0,61`.
Temuan yang baru diketahui dari sumber ini: `Cd = 0,61` bukan satu koefisien
melainkan **hasil kali** `Cc · Cvf · Cva` (kontraksi, kecepatan pendekatan,
kehilangan). Ini penting saat ditanya penguji mengapa nilainya bukan angka
tunggal empiris.

**A2.** Mohammed, A. Y. (2022). *Driftwood blocking sensitivity on sluice gate
flow.* **Open Engineering 12**: 384. DOI `10.1515/eng-2022-0384`.
Dipakai untuk: **membuktikan premis proyek**. Percobaan flume dengan batang kayu
dan bonggol akar pada beberapa bukaan pintu dan tinggi hulu.
Hasil yang dikutip:
1. Penumpukan menaikkan kedalaman air hulu **15%** — terukur, bukan dimodelkan.
2. Bukaan lebih besar **dan** tinggi hulu ~50% maksimum → kemungkinan kayu
   tersangkut **turun**.
3. **Bonggol akar lebih mudah menyumbat daripada batang** — bentuk menggumpal
   lebih menyumbat daripada benda memanjang.
4. Kayu tersangkut **di bawah** pintu memicu gerusan.

Tanpa sumber ini, seluruh proyek berdiri di atas dugaan bahwa sampah **terapung**
mengurangi luas bukaan pintu yang membuka dari **bawah**. Dugaan itu sekarang
punya pengukuran.

**A3.** Ollett, P., Syme, B., & Ryan, P. (2017). *Australian Rainfall and Runoff
blockage guidelines: numerical implementation.* **Journal of Hydrology (New
Zealand) 56**(2): 109–122.
Dipakai untuk: **menamai dan mengkritik metode sendiri**. Metode proyek ini
adalah **Reduced Area Method (RAM)**. ARR menyatakan RAM cocok untuk penyumbatan
"bottom-up" (sedimentasi), sementara penyumbatan **di mulut** — rakit sampah
terapung — semestinya memakai **Energy Loss Method**, karena RAM "can exaggerate
energy losses". Contoh terhitung ARR pada penyumbatan 50%: RAM 6,04 m melawan
ELM 4,71 m, **28% lebih tinggi**.
ARR juga menganjurkan **uji sensitivitas dengan kedua metode**. Proyek ini baru
punya satu.

**A4.** Witheridge, G. (2009). Relasi `BF = BR^(5/4)` — perkiraan pengurangan
kapasitas debit untuk kendali masuk. **Tidak dipakai dalam perhitungan**,
dicantumkan karena mungkin ditanya.

**A5.** Meusburger — dikutip di `referensi_fisika.md` sebagai penguat bahwa
`h ∝ 1/A²` adalah relasi standar. `[Belum diverifikasi ke terbitan primer]`.

Verifikasi lengkap ada di [`../referensi_fisika.md`](../referensi_fisika.md).

---

### B. Dataset

**B1.** Don, Pinson, Guillen Cebrian, & Asano (2024). *Foundation Model or
Finetune? Evaluation of few-shot semantic segmentation for river pollution.*
GreenFOMO @ ECCV 2024. arXiv `2409.03754`.
Dataset **RIPTSeg**: 4TU.ResearchData, DOI
`10.4121/90d13261-b0fe-444a-b408-c5a63db3d887.v1`.
Kode: `github.com/TheOceanCleanup/RiverTrashSegmentation`.
300 citra, 6 lokasi, 4.387 mask, CC BY 4.0. Rekaman operasional The Ocean
Cleanup 2020–2023.
**Nilainya:** satu-satunya dataset publik yang melabeli **sampah dan air di
citra yang sama** — persis yang dibutuhkan metrik coverage — dan satu-satunya
yang daftar kelasnya memuat **struktur** (`barrier`), analog langsung kasus
penyumbatan di pilar atau saringan sampah.

**B2.** Kataoka, Yoshida, & Yamamoto (2025). *River Surface Image Dataset
(RiSID).* **Data in Brief vol. 63**.
Zenodo DOI `10.5281/zenodo.16927238` (v2, terbit 2025-08-22); v1
`10.5281/zenodo.15533743`.
7.356 citra, 8.022 objek beranotasi, 11 situs di 7 sungai Jepang (Arakawa,
Danzu, Edo, Hikiji, dan lainnya), dikumpulkan 2010–2024, CC BY 4.0.
Anotasi poligon COCO dalam tiga granularitas (7 / 5 / 2 kelas).
**Nilainya:** pemasok massal mask sampah, dan satu-satunya himpunan besar yang
sengaja diambil saat **kondisi banjir** — cocok dengan kasus penggunaan
penyumbatan. Air **tidak** dilabeli, sehingga butuh label semu.

**B3.** Qiao, G., Yang, M., & Wang, H. (2025). *IWHR_AI_Lable_Floater_V1.*
**Scientific Data**, `nature.com/articles/s41597-025-04594-9`.
figshare DOI `10.6084/m9.figshare.27376851.v1`.
3.000 citra, kotak pembatas Pascal VOC, **Apache 2.0**.
**Nilainya:** kamera pengawas terpasang di tepi perairan pedalaman — **geometri
kamera yang paling mendekati penempatan proyek ini**. Penulisnya sendiri
melaporkan akurasi deteksi baseline tetap rendah karena pencahayaan rumit dan
objek kecil.

Katalog lengkap, termasuk dataset yang ditolak dan alasannya, ada di
[`../datasets.md`](../datasets.md).

---

### C. Arsitektur model dan pustaka

| Ref | Komponen | Sumber | Lisensi |
|---|---|---|---|
| C1 | SegFormer (`mit_b0`) | Implementasi native `segmentation-models-pytorch` ≥0.5.0 | MIT |
| C2 | LR-ASPP MobileNetV3, DeepLabv3-MNv3 | torchvision | Apache-2.0 |
| C3 | U-Net (MNv3, EfficientNet-lite), DeepLabV3+ | `segmentation-models-pytorch` | MIT |
| C4 | Fast-SCNN | Disalin ke dalam repo, `src/models/fast_scnn.py` | MIT |
| C5 | YOLO11n-seg | ultralytics | **AGPL-3.0 — dikecualikan** |
| C6 | SAM | Label air semu dan konversi bbox→mask | — |
| C7 | PyTorch | pytorch.org | BSD |
| C8 | Next.js, React | vercel/next.js, react.dev | MIT |
| C9 | better-sqlite3 | npm | MIT |
| C10 | RTClib | adafruit/RTClib | BSD |

---

### D. Sumber data operasional

| Ref | Sumber | Dipakai untuk |
|---|---|---|
| D1 | Open-Meteo (archive + forecast API) | Curah hujan regional, `src/external/rainfall.py` |
| D2 | BMKG (API prakiraan wilayah, kode `adm4`) | Prakiraan hujan Indonesia |

---

## 10.2 Batasan sistem

Dikelompokkan menurut sumber keterbatasannya, bukan menurut seberapa buruk
kedengarannya.

### Batasan A — belum ada kalibrasi lapangan

**Ini batasan paling menentukan di seluruh proyek.**

| Parameter | Nilai sekarang | Akibat kalau salah |
|---|---|---|
| `h_bersih_m` | 0,8 (tebak) | **Menggeser seluruh hasil afflux.** Ini garis dasarnya |
| `z_jalan_m` | 1,6 (tebak) | `critical_bf` salah — angka yang paling ingin diramalkan |
| `b_m`, `a_m` | 2,0 × 1,0 (tebak) | Debit salah; rasio afflux **tidak** terpengaruh (tanpa dimensi) |
| `Cd` | 0,61 (literatur) | Wajar, tapi lebih baik dikalibrasi dari miniatur |
| `JARAK_DASAR` | 100 cm (tebak) | **Setiap tinggi air salah** |
| `MM_PER_TIP` | 0,30 mm (tebak) | Setiap angka mm/jam salah secara fisik |
| `skala`, `bias` kamera | 1,0 / 0,0 (identitas) | Galat dikuadratkan oleh `1/(1−BF)²` |

Selama `configs/site_geometry.json` berstatus `UNCALIBRATED`, web menandai
seluruh keluaran fisika sebagai perkiraan kasar dan **tidak** menampilkannya
sebagai peringatan. Ada uji otomatis yang menjaga status itu tidak dinaikkan
diam-diam.

### Batasan B — model belum melihat domain sasaran

- Dilatih pada RIPTSeg (Ocean Cleanup, multi-negara) + IWHR (Tiongkok).
- **Nol citra dari bendung gerak sasaran.**
- Kondisi Indonesia yang sama sekali tak terwakili: air cokelat sangat keruh,
  sachet kecil, eceng gondok.
- Bukti visual jurang ini ada di [09 §9.4](09-dokumentasi-visual.md): model
  melabeli plastik hitam mengilap sebagai air.
- Set uji 50 citra dari satu lokasi; satu seed; ragam antar-run tidak diukur.

### Batasan C — perangkat keras

- **Ultrasonik belum menghasilkan satu pun bacaan sah**
  ([07 §7.2](07-data-pengujian.md)). Tinggi muka air adalah pengukuran utama
  proyek, dan sistem belum mengukurnya.
- SMS dan relai pompa: logikanya teruji, **sirkuitnya belum**.
- Belum pernah diuji di Raspberry Pi — semua angka latensi Pi adalah
  ekstrapolasi dari x86.
- Satu titik ukur tinggi air; kemiringan muka air di kolam hulu tidak terlihat.
- Uji ketahanan terpanjang 30 jam.

### Batasan D — model fisika

- **Reduced Area Method melebih-lebihkan** untuk penyumbatan di mulut (A3).
  Angkanya batas atas, bukan taksiran terbaik. ARR menganjurkan uji sensitivitas
  dua metode; proyek ini baru punya satu.
- Model meledak saat `BF → 1`; di atas 0,85 sistem menolak memberi angka.
- Mengasumsikan **aliran bebas**. Pintu tenggelam (*submerged*) punya persamaan
  berbeda dan belum ditangani.
- Mengasumsikan sampah mengurangi luas secara **seragam**. Rakit sampah
  sesungguhnya tidak seragam.
- Kalibrasi kamera masih identitas, sementara kesalahannya dikuadratkan.

### Batasan E — perangkat lunak dan penempatan

- Tanpa autentikasi di `/api/ingest` — siapa pun di jaringan bisa menyuntikkan
  bacaan palsu ke sistem peringatan banjir.
- Tanpa HTTPS, tanpa pembatasan laju.
- Semuanya satu mesin; tidak ada lapisan sinkronisasi kalau inferensi pindah ke
  lokasi.
- Tanpa rotasi/retensi basis data.
- Tanpa uji komponen React dan tanpa uji ujung-ke-ujung peramban.
- **Sebagian besar pekerjaan mutakhir belum di-commit** — lihat
  [01 §1.4](01-repositori.md).

### Batasan F — lingkup

- Sistem **melaporkan**, tidak **memutuskan**. Pembersihan tetap tindakan
  manusia.
- Kamera hanya melihat permukaan. Penyumbatan bawah air tidak terdeteksi.
- Tidak memodelkan hidrologi hulu; ia mengukur keadaan sekarang, bukan
  meramalkan debit.

### Batasan G — operator menolak premis pemantauan jarak jauh

Wawancara putaran pertama sudah terlaksana
([`../hasil_wawancara_operator.md`](../hasil_wawancara_operator.md)), dan
jawabannya membatalkan satu asumsi yang mendasari proyek ini.

Ditanya apakah alat yang melaporkan kondisi tanpa ia datang ke lokasi berguna,
operator menjawab **"tidak berguna"** — alasannya ia memang selalu datang.
Jawaban lain menguatkannya: pintu air **dijaga penuh pada malam hari**, lebih
ketat lagi saat hujan. Justifikasi "tidak ada yang memantau jam dua pagi" yang
dibayangkan sebelum wawancara **gugur di lokasi ini**.

Yang tersisa sebagai nilai sistem, dan semuanya bersandar pada jawaban lain di
wawancara yang sama, bukan pada karangan penulis:

1. **Melihat hulu sebelum berangkat.** Operator menyebut sampah datang dari hulu
   (`E4`), dan menyebut hulu sebagai penyebab banjir dua tahun lalu (`F2`).
   Kehadiran di pintu tidak memberi tahu apa yang sedang dikirim hulu.
2. **Menjadi buku catatan yang tidak pernah ada.** Tidak ada catatan harian
   (`D1`). Semua jawaban berbentuk "dulu" dan "dua tahun lalu" tidak punya angka
   pendukung justru karena itu.
3. **Angka menggantikan penilaian mata.** Dasar keputusan membuka pintu bersifat
   kualitatif (`A5`); debit terhitung memberi ukuran yang bisa dibawa ke dinas.

**Klaim "menggantikan kehadiran operator" tidak boleh muncul di laporan ini.**
Narasumbernya sendiri sudah menolaknya.

Satu jawaban berjalan ke arah sebaliknya dan justru memperkuat proyek: ditanya
penyebab banjir terakhir, operator menyebut **sampah kiriman hulu yang
menyumbat** — tanpa dipancing, sebelum pewawancara menyebut kata sampah sama
sekali. Bukti seperti itu jauh lebih kuat daripada jawaban terpandu.

**Yang masih menggantung:** dua pertanyaan penentu tidak terjawab — dari mana
operator tahu sudah waktunya membersihkan (`C3`), dan seberapa banyak sampah yang
membuatnya turun tangan (`G4`). Keduanya pembanding manusia untuk
`blockage.area_threshold`. Tanpa itu, ambang 18% di sistem belum punya padanan
lapangan.

**Yang diminta operator, dan belum dibangun:** ditanya informasi apa yang paling
dibutuhkan, jawabannya **debit air** (`G2`), disampaikan lewat **WhatsApp**
(`G3`). Rantai debit sudah ada di `src/physics.py`, tetapi tidak ditampilkan di
mana pun setelah kartu fisika dihapus, dan tidak ada kanal WhatsApp — yang
terpasang baru rel notifikasi di dalam dasbor dan SMS lewat SIM800L.

---

## 10.3 Dokumentasi penggunaan AI

Bagian ini ditulis lengkap dan spesifik. Menyamarkan penggunaan AI dalam laporan
yang diperiksa penguji adalah risiko yang tidak sebanding dengan manfaatnya, dan
pekerjaannya sendiri tidak butuh disamarkan.

### 10.3.1 AI sebagai bagian dari produk

| Komponen | Apa | Terlatih di | Buatan sendiri? |
|---|---|---|---|
| SegFormer-B0 | Segmentasi semantik 4 kelas | RIPTSeg + IWHR | **Bobot dilatih sendiri**, arsitektur dari pustaka MIT |
| SAM | Label air semu, konversi bbox→mask | Pra-latih | Dipakai apa adanya sebagai alat bantu anotasi |

**Yang dilatih sendiri:** seluruh bobot di `runs/`. Tujuh run dicatat di
[06 §6.5](06-model-ai.md), lengkap dengan konfigurasi, metrik per-epoch, dan
log. Semuanya bisa direproduksi dengan perintah di [06 §6.10](06-model-ai.md).

**Yang tidak dilatih sendiri:** definisi arsitektur (torchvision, smp) dan bobot
awal pra-latih ImageNet. Ini praktik standar dan lisensinya jelas.

**Label semu SAM adalah batasan yang perlu dinyatakan.** Air di IWHR tidak
dilabeli manusia — ia dihasilkan SAM lalu ditinjau. Karena itu ada
`per_dataset_cap` di konfigurasi pelatihan: tanpa pembatas, tiap epoch akan
~93% IWHR, dan satu-satunya air beranotasi manusia di proyek ini akan tenggelam
di bawah label semu.

### 10.3.2 Aturan yang diberlakukan atas penggunaan AI

Empat aturan berikut dipegang sepanjang pengembangan, dan jejaknya bisa
diperiksa di kode:

**1. Setiap angka harus berasal dari perintah yang benar-benar dijalankan.**
Tidak ada satu pun angka di laporan ini yang berasal dari perkiraan model
bahasa. Setiap tabel disertai perintah yang menghasilkannya.

**2. Tidak ada sumber yang dikutip tanpa dibaca.** Tautan di `datasets.md`
diperiksa satu per satu sampai kode status HTTP-nya; klaim di
`referensi_fisika.md` ditelusuri sampai terbitan primer. Yang tidak
terverifikasi ditandai `[Belum diverifikasi]`, bukan dibiarkan tampak pasti.

**3. Kode yang dihasilkan AI wajib punya uji.** 210 pemeriksaan otomatis di
[08](08-protokol-uji.md) ada persis untuk ini. Kode dari model bahasa yang
terlihat masuk akal tapi salah adalah mode kegagalan yang nyata; uji adalah
satu-satunya penangkalnya.

**4. Ketidaktahuan ditulis, bukan diisi.** Penanda `[BELUM]` dan `[ASUMSI]`
tersebar di seluruh laporan, dan `README.md` melarang menaikkannya tanpa bukti
yang bisa diulang. Bug ultrasonik di [07 §7.2](07-data-pengujian.md) adalah
contohnya: lebih mudah menulis "sistem mengukur tinggi air" daripada
mendokumentasikan kegagalannya.

### 10.3.3 Yang harus disadari tentang cara laporan ini disusun

Dokumen ini disusun dengan membaca ulang repositori dan basis data langsung —
`git log`, `git status`, kueri SQLite, menjalankan rangkaian uji, membuka berkas
gambar. Bukan dari ingatan percakapan.

Konsekuensinya: **angka di laporan ini adalah keadaan repositori pada
2026-08-25**, dan akan usang begitu kode berubah. Cara memperbaruinya adalah
menjalankan ulang perintah yang tercantum, bukan menyunting angkanya.

Satu hal yang layak diperiksa penguji sendiri: seluruh pemeriksaan di
[08 §8.1](08-protokol-uji.md) bisa dijalankan ulang dalam beberapa menit di
mesin mana pun yang punya repo ini.

---

## 10.4 Ringkasan kejujuran

Ditaruh di akhir karena ini kesimpulan yang sebenarnya dari sepuluh berkas.

| Bagian | Status | Bukti |
|---|---|---|
| Model segmentasi | **`[TERUKUR]`** val debris IoU 0,7313 | `runs/combined_segformer_b0_640/summary.json` |
| Perangkat lunak web | **`[TERUKUR]`** 72/72 lulus, 11 berkas | `npx vitest run` |
| Perangkat lunak Python | **`[TERUKUR]`** 95/95 lulus | `pytest tests/ -q` |
| Firmware — logika | **`[TERUKUR]`** 47/47 lulus | `run_tests.ps1` |
| **Firmware — kirim ke server** | **`[TERUKUR]`** 219 baris tersimpan | `esp_readings`, 25–27 Agu 2026 |
| Unit kamera Raspberry Pi | **`[TERUKUR]`** 5.402 bingkai, 30,0 fps | uji ketahanan 180 detik, 2026-08-27 |
| Rantai kamera→model→basis data→web | **`[TERUKUR]`** 502.210 baris | `observations` |
| Tipping bucket | **`[TERUKUR]`** hitungan & konversi benar | `tip_total` 0→148, mm/jam ✓ |
| NTP + cadangan RTC | **`[TERUKUR]`** kedua jalur terpakai | `time_src` 23 ntp / 2 rtc |
| **Sensor ultrasonik** | **`[BELUM]`** semua baris dari `MODE_SIMULASI` | `esp_readings`: `tinggi_cm` tetap 4,6 |
| Wawancara operator | **`[TERUKUR]`** putaran pertama terlaksana | [`../hasil_wawancara_operator.md`](../hasil_wawancara_operator.md) |
| Fisika afflux — rumus | **`[TERUKUR]`** terverifikasi ke literatur primer | `referensi_fisika.md` |
| Fisika afflux — parameter | **`[ASUMSI]`** seluruh dimensi pintu tebakan | `site_geometry.json` |
| Kalibrasi lapangan | **`[BELUM]`** belum ada survei | — |
| Foto/video implementasi | **`[BELUM]`** hanya 1 foto lokasi | [09](09-dokumentasi-visual.md) |

**Jangan menaikkan status apa pun di tabel ini tanpa bukti yang bisa diulang.**
Sistem ini mengeluarkan peringatan banjir; melebihkan kesiapannya bukan
kesalahan administratif, melainkan bahaya.

---

## 10.5 Tiga langkah berikutnya, berurutan

1. **Perbaiki sensor ultrasonik.** Protokolnya sudah ditulis di
   [08 §8.6](08-protokol-uji.md). Tanpa ini tidak ada tinggi muka air.
2. **Commit semua pekerjaan yang belum masuk git.** Repositori yang diserahkan
   saat ini tidak memuat firmware, fisika, maupun tampilan web mutakhir. Lihat
   [01 §1.4](01-repositori.md). **Jangan sekali pun meng-commit
   `config_secrets.h`.**
3. **Survei lokasi dan ukur geometri pintu air.** Setiap keluaran fisika tetap
   `[ASUMSI]` sampai ini selesai, dan itu adalah bagian yang membuat proyek ini
   berarti.

---

[← Daftar isi](README.md) · [← Sebelumnya: Dokumentasi visual](09-dokumentasi-visual.md)
