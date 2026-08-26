# 6. Dokumentasi Model AI dan Evaluasi

[← Daftar isi](README.md) · [← Sebelumnya: Basis data & API](05-database-api.md)

---

## 6.1 Apa yang diminta dari model

Satu tugas, dirumuskan sesempit mungkin: **segmentasi semantik permukaan
sungai**, empat kelas.

| id | Kelas | Isi |
|---|---|---|
| 0 | `background` | Bukan air dan bukan sampah: langit, tanggul, vegetasi darat, struktur |
| 1 | `water` | Permukaan air |
| 2 | `debris` | **Apa pun yang mengapung dan bukan air**: plastik, sachet, styrofoam, kantong, kayu, vegetasi terapung, eceng gondok |
| 3 | `clump` | Gumpalan sampah rapat (turunan heuristik, bukan anotasi) |

**`debris`, bukan `trash`, dan itu keputusan skema.** Asal-usul benda
(antropogenik vs alami) sengaja **tidak** masuk skema. Untuk pertanyaan yang
diajukan proyek — berapa fraksi permukaan air yang tertutup benda terapung —
sebatang kayu dan sebuah sachet menyumbat pintu dengan cara yang sama.

Nilai `ignore_index: 255` disediakan untuk piksel yang tidak boleh menyumbang ke
fungsi rugi.

---

## 6.2 Dataset

### Katalog

| Dataset | Isi | Anotasi | Lisensi | Peran |
|---|---|---|---|---|
| **RIPTSeg** | ~300 citra, 6 lokasi, 4.387 poligon COCO | Manusia | CC BY 4.0 | **Latih + evaluasi utama** |
| **IWHR** | 3.000 citra, kamera tetap di tepi perairan pedalaman Tiongkok | PNG semantik | lihat sumber | Latih (gabungan) |
| **RiSID** | 7.356 citra, 8.022 objek, 11 situs / 7 sungai Jepang | Poligon COCO, 3 granularitas | CC BY 4.0 | Survei / cadangan |
| LARS | — | — | **belum dipastikan** | Survei |
| USVInland | — | — | lihat sumber | Survei |
| `roboflow_river_trash` | — | — | lihat sumber | Survei |
| **OPSI** | Anotasi lokasi sendiri | Manusia | milik sendiri | **`[BELUM]` belum ada data** |

Katalog lengkap dengan DOI, ukuran unduh, dan verifikasi tautan ada di
[`../datasets.md`](../datasets.md).

### Pembagian, dan mengapa bukan pembagian acak

RIPTSeg dibagi **per lokasi**, bukan acak:

| Split | Lokasi | Citra |
|---|---|---|
| Latih | loc2, loc3, loc5, loc6 | 200 |
| Validasi | loc4 | 50 |
| **Uji** | **loc1** | 50 |

Validasi dan uji adalah lokasi yang **tidak pernah dilihat model**.

Ini jauh lebih sulit daripada pembagian acak, dan itu tujuannya: 300 bingkai
dari 6 kamera tetap membuat bingkai bersebelahan nyaris kembar. Pembagian acak
akan menaruh bingkai *n* di latih dan *n+1* di uji, sehingga yang terukur adalah
hafalan, bukan generalisasi. Harapkan angka di bawah **lebih rendah dan lebih
jujur** daripada publikasi yang memakai pembagian acak pada dataset yang sama.

### Sebaran kelas setelah konversi

Bagian dari piksel berlabel, RIPTSeg:

| Kelas | Bagian |
|---|---|
| `water` | 75,9% |
| `clump` | 14,9% |
| `background` | 6,8% |
| `debris` | **2,4%** |

Coverage dataset (`debris/(debris+water)`) = 18,5%.

---

## 6.3 Temuan yang paling mengubah proyek: skema 4-kelas menghasilkan kelas debris yang tidak berguna

`[TERUKUR]`

| Skema | test mIoU | test debris IoU |
|---|---|---|
| 4-kelas (`debris` dan `clump` terpisah) | 0,584 | **0,103** |
| 3-kelas (`clump` dilebur ke `debris`) | 0,726 | **0,419** |

**Empat kali lipat.** Dan penyebabnya bukan model.

`clump` **bukan anotasi** — ia heuristik komponen terhubung di
`src/data/clump.py`. Pada RIPTSeg, yaitu rekaman hamparan sampah padat yang
menumpuk di penghalang penangkap, heuristik itu menelan hampir seluruh
latar-depan (`clump` 14,9% piksel berlabel vs `debris` 2,4%). Yang tersisa untuk
`debris` adalah sisa tipis yang IoU-nya lebih banyak bercerita tentang ambang
luas daripada tentang model.

Bukti bahwa model sebenarnya baik sepanjang waktu: pada run 4-kelas yang sama,
`clump` IoU 0,417 sementara `debris` 0,103. Modelnya menemukan sampah; skemanya
yang membelah temuan itu jadi dua dan menilai separuhnya.

Peleburan adalah **LUT saat pemuatan**, jadi PNG di disk tidak tersentuh dan
keputusan ini bisa dibatalkan dengan menunjuk kembali ke `classes.yaml`.

### Akibat langsung untuk anotasi lapangan

Keputusan lokasi 2026-08-17: anotasi di bendungan hanya memakai **dua kelas**,
`water` dan `debris`. `clump` diturunkan setelahnya oleh `clump.py`. Alasannya
tercatat di `rencana_penelitian.md` §4.2: tidak ada eceng gondok di lokasi,
sebagian besar sampah berada di bawah ambang kewajaran 1%-dari-ROI di panduan
anotasi, dan kelas yang kelaparan data merugikan generalisasi — bukan sekadar
memakan waktu.

---

## 6.4 Tolok ukur tujuh arsitektur

Semua diukur, bukan diperkirakan. Biaya diukur di AMD64 (AMD Ryzen), torch CPU,
**1 utas**, 15 kali jalan setelah 4 pemanasan.

### Biaya

| Model | Param (juta) | Disk (MB) | GFLOPs@640 | ms@640 | ms@512 | ms@416 | Lisensi |
|---|---|---|---|---|---|---|---|
| `fast_scnn` | 1,14 | 4,7 | 2,6 | **84** | **61** | **33** | MIT |
| `lraspp_mnv3` | 3,22 | 13,1 | 6,1 | 189 | 164 | 74 | Apache-2.0 |
| `segformer_b0` | 3,72 | 14,9 | 26,1 | 1013 | 945 | 282 | MIT |
| `deeplabv3plus_mnv3` | 4,71 | 19,1 | 14,5 | 422 | 312 | 167 | MIT |
| `unet_effnet_lite` | 5,2 | 21,1 | 36,4 | 642 | 541 | 288 | MIT |
| `unet_mnv3` | 6,69 | 27,0 | 38,6 | 636 | 553 | 268 | MIT |
| `deeplabv3_mnv3` | 11,02 | 44,3 | 30,7 | 448 | 325 | 149 | Apache-2.0 |

### Akurasi pada lokasi uji yang tak pernah dilihat (loc1)

| Model | test mIoU@640 | test debris IoU@640 | ms@512 (CPU) | Param |
|---|---|---|---|---|
| **`segformer_b0`** | **0,747** | **0,474** | 945 | 3,72 M |
| `lraspp_mnv3` | 0,726 | 0,419 | **164** | 3,22 M |
| `unet_mnv3` | 0,718 | 0,385 | 553 | 6,69 M |
| `deeplabv3plus_mnv3` | 0,709 | 0,413 | 312 | 4,71 M |

Rincian SegFormer-B0 terbaik: debris presisi 0,533, debris recall 0,812,
water IoU 0,803.

### Empat kesimpulan yang bertahan setelah data akurasi masuk

**1. Jumlah parameter salah mengurutkan latensi.** SegFormer-B0 adalah model
ketiga terkecil dan yang **paling lambat** — 5,8× lebih lambat dari LR-ASPP di
512. Ia juga yang paling akurat, jadi salah-urut itu memotong dua arah.

**2. GFLOPs juga salah mengurutkannya.** SegFormer melakukan GFLOPs **lebih
sedikit** dari DeepLabv3-MNv3 (15,6 vs 19,6) dan makan waktu 2,9× lebih lama.

**3. SegFormer menskala 3,4× dari 416 ke 512** sementara setiap CNN menskala
1,9–2,2×, karena atensi kuadratik terhadap jumlah token. Akibat tajamnya:
keunggulan SegFormer **paling besar di 640** (+0,055 debris IoU atas LR-ASPP)
dan mengecil di 416 (+0,029) — satu-satunya resolusi yang latensi CPU-nya masih
bisa ditoleransi. **Ia menang di tempat ia tidak bisa berjalan, dan nyaris seri
di tempat ia bisa.**

**4. Objek kecil rusak 2–3× lebih cepat daripada mIoU.** IoU debris yang hilang
saat turun dari 640 ke 416, dibandingkan mIoU yang hilang:

| Model | debris IoU turun | mIoU turun | rasio |
|---|---|---|---|
| `lraspp_mnv3` | **7,6%** | 2,7% | 2,8× |
| `segformer_b0` | 12,2% | 6,2% | 2,0× |
| `unet_mnv3` | 12,3% | 4,0% | 3,1× |
| `deeplabv3plus_mnv3` | 14,6% | 4,5% | 3,2× |

Memilih resolusi berdasarkan mIoU akan **meremehkan kerusakannya tiga kali
lipat**. `lraspp_mnv3` juga paling tahan penurunan resolusi secara absolut
(7,6%), yang lebih berarti daripada kelihatannya: di Raspberry Pi, resolusi yang
terjangkau adalah kendala pengikat.

**Akurasi piksel tidak muncul di mana pun.** Air adalah 85–95% piksel; model
yang menebak "semua air" akan mendapat ~0,9 dan tidak mendeteksi apa pun. Bukti
langsungnya sudah dikutip: `pixel_acc` 0,93 bersamaan dengan `debris IoU` 0,10.

---

## 6.5 Semua run pelatihan yang pernah dijalankan

`[TERUKUR]` — dibaca langsung dari `runs/*/summary.json`. Skor adalah
`iou_debris` terbaik di set **validasi**.

| Run | Model | Best `iou_debris` | Epoch | Berhenti awal |
|---|---|---|---|---|
| **`combined_segformer_b0_640`** | segformer_b0 | **0,7313** | 40 | ya |
| `riptseg_segformer_b0_collapsed` | segformer_b0 | 0,6917 | 49 | ya |
| `riptseg_deeplabv3plus_mnv3_collapsed` | deeplabv3plus_mnv3 | 0,6832 | 58 | ya |
| `riptseg_unet_mnv3_collapsed` | unet_mnv3 | 0,6809 | 37 | ya |
| `combined_lraspp_collapsed` | lraspp_mnv3 | 0,6601 | 57 | ya |
| `riptseg_lraspp_collapsed` | lraspp_mnv3 | 0,6304 | 63 | ya |
| `riptseg_lraspp` (4-kelas) | lraspp_mnv3 | **0,1021** | 75 | ya |

Baris terakhir adalah run 4-kelas, dan ia satu-satunya bukti paling ringkas
untuk §6.3: arsitektur yang sama, data yang sama, hanya skemanya berbeda —
0,1021 melawan 0,6304.

### Tiga tuas yang ditumpuk untuk model produksi

`configs/train/combined_segformer_b0_640.yaml` menaikkan tiga hal sekaligus,
masing-masing dengan alasan berupa pengukuran yang sudah ada di repo:

1. **Arsitektur.** SegFormer-B0 di RIPTSeg saja (0,6917) sudah mengalahkan
   LR-ASPP gabungan (0,6601).
2. **Data.** Menambahkan IWHR mengangkat LR-ASPP dari 0,6304 ke 0,6601 (+4,7%)
   dalam run yang selain itu identik.
3. **Resolusi.** Test debris IoU SegFormer-B0: 0,4164 / 0,4586 / 0,4743 untuk
   416 / 512 / 640. Tambahan +2,7% dari 512 ke 640 mendarat tepat di tempat
   proyek ini membutuhkannya — sampah di lokasi berupa sachet dan serpihan kecil
   yang tersebar, dan resolusi rendah menghapus itu lebih dulu.

**Ketiganya tidak sekadar bertambah** — resolusi dan kapasitas sebagian
tumpang-tindih — jadi total apa pun harus diperlakukan sebagai batas atas, bukan
ramalan. Hasil sebenarnya: **0,7313**.

---

## 6.6 Protokol pelatihan model produksi

| Parameter | Nilai | Alasan |
|---|---|---|
| Model | `segformer_b0`, pra-latih | §6.4 |
| Kelas | `classes_collapsed.yaml` (3 kelas efektif) | §6.3 |
| Resolusi | 640 | Sampah kecil hilang lebih dulu saat diperkecil |
| Batch | **8** | SegFormer@640 menyimpan aktivasi jauh lebih banyak dari LR-ASPP@512; GPU 8 GB. Membelah batch = asuransi murah terhadap OOM tiga jam di tengah run tanpa penjaga |
| Workers | 8 | Lihat catatan Windows di bawah |
| `per_dataset_cap` | 400 | riptseg min(200, 400×1,0)=200; iwhr min(2510, 400×0,7)=280. Tanpa itu tiap epoch ~93% IWHR |
| Rugi | `dice+focal`, 0,5/0,5, `gamma=2,0` | Kelas debris ~3% piksel |
| Optimizer | AdamW, lr 6e-4, wd 1e-4 | |
| Scheduler | cosine | |
| Epoch maks | 120 | Berhenti di 40 |
| AMP | ya | |
| Grad clip | 1,0 | |
| Metrik pemilihan | `iou_debris` | **Bukan** mIoU, **tidak pernah** `pixel_acc` |
| Sabar berhenti-awal | 30 | |
| Seed | 0 | **Satu seed saja** — lihat §6.8 |

**Augmentasi** (tidak diubah dari run lain, supaya hasilnya bisa ditafsirkan):
affine 0,7 · brightness/contrast 0,9 · hsv 0,9 · gamma 0,5 · clahe 0,3 ·
sun_flare 0,25 · tone_curve 0,3 · rain 0,15 · fog 0,15 · low_light 0,2 ·
motion_blur 0,15.

> **Jebakan Windows yang tercatat.** `riptseg_segformer_b0_collapsed.yaml`
> menyetel `num_workers: 0` dan mendokumentasikan kegagalan spawn: worker
> ter-resolve ke interpreter conda base yang tidak punya torch CUDA, sehingga
> loader tidak pernah menghasilkan apa pun — pelatihan menggantung di epoch 0
> dengan GPU 2%. Worker yatim lalu bertahan hidup dan membuat run berikutnya
> kelaparan, yang membuatnya tampak seperti masalah model. Turunkan ke 0 kalau
> gejala itu kembali.

---

## 6.7 Fisika: mengubah keluaran model jadi akibat

Model menghasilkan `accumulation_frac`. Sendirian, angka itu hanya melaporkan
"pintu tertutup 24%" — yang sudah diketahui operator dengan melihat. Rantai
fisika mengubahnya jadi akibat.

```
BF = skala · accumulation_frac + bias        faktor penyumbatan (kalibrasi E2)
A  = A_bersih · (1 − BF)                     luas bukaan efektif
Q  = Cd · b · a · √(2 g h)                   debit aliran bebas lewat pintu
h  = Q² / (Cd² A² 2g)                        dibalik: tinggi tekan yang dibutuhkan

⇒  h ∝ 1/A²

⇒  h_tersumbat / h_bersih = 1 / (1 − BF)²
```

**Bentuk rasio itu yang penting, karena ia tanpa dimensi.** Tidak ada debit,
lebar pintu, atau faktor skala yang selamat masuk ke dalamnya — dan itulah
sebabnya akuarium 80 cm bisa memvalidasi hukum yang sama dengan bendung
sungguhan.

### Verifikasi ke literatur primer

| Pertanyaan | Jawaban | Sumber |
|---|---|---|
| `Q = Cd·A·√(2gh)` benar untuk pintu air? | Ya, pintu sorong = orifis persegi | USBR *Water Measurement Manual* Bab 9 |
| `Cd = 0,61` benar? | Ya, dan itu **hasil kali** `Cc·Cvf·Cva` | USBR WMM §9-5 |
| `h ∝ 1/A²` benar? | Ya, standar | USBR; Meusburger; ARR |
| Sampah **terapung** benar-benar menyumbat pintu **bawah**? | **Ya, terukur +15% muka air hulu** | Mohammed (2022) |
| Metode kami punya nama? | Ya: **Reduced Area Method (RAM)** | Ollett dkk. (2017) |
| RAM tepat untuk kasus kami? | **Tidak sepenuhnya — RAM melebih-lebihkan** | Ollett dkk. (2017) |

Baris keempat adalah pertanyaan paling menentukan seluruh proyek: kalau pintu
membuka dari **bawah** sementara sampah mengapung di **permukaan**, apakah
sampah benar-benar mengurangi luas bukaan? Mohammed (2022) menjawabnya dengan
percobaan flume: **penumpukan menaikkan kedalaman air hulu sebesar 15%,
terukur, bukan dimodelkan.** Premis proyek selamat.

Temuan lain dari percobaan yang sama, yang layak diketahui saat sidang: bonggol
akar lebih mudah menyumbat daripada batang lurus (bentuk tiga dimensi yang
menggumpal lebih menyumbat daripada benda memanjang), dan kayu yang tersangkut
di **bawah** pintu memicu gerusan.

### Tiga peringatan yang menempel pada setiap angka fisika

**1. Kuadrat memperbesar kesalahan.** Kamera yang melapor 24% padahal
sebenarnya 31% tidak memberi galat 7% pada afflux: `1/(0,76)² = 1,73` melawan
`1/(0,69)² = 2,10`, yaitu **18% terlalu rendah**. Kalibrasi kamera (eksperimen
E2) wajib dilakukan sebelum angka mana pun dipercaya.

**2. Model meledak saat BF → 1.** Pintu yang tersumbat penuh punya tinggi tekan
tak hingga dalam model ini, yang omong kosong — air sungguhan lewat atas, lewat
samping, atau strukturnya jebol. Di atas `BF_MAX_TRUSTED = 0,85` sistem
melaporkan "di luar jangkauan model", **tidak pernah** sebuah angka.

**3. Ini batas atas, bukan taksiran terbaik.** Mengecilkan luas adalah apa yang
disebut *Australian Rainfall and Runoff* sebagai Reduced Area Method, dan ARR
menyatakan RAM cocok untuk penyumbatan "dari bawah" (sedimentasi), sementara
penyumbatan **di mulut** — yang persis adalah rakit sampah terapung — masuk ke
Energy Loss Method mereka, karena RAM "can exaggerate energy losses". Contoh
terhitung ARR pada penyumbatan 50%: RAM 6,04 m tinggi hulu melawan ELM 4,71 m,
**28% lebih tinggi**.

Pembelaannya: alasan ARR adalah kecepatan yang menggelembung di sepanjang
**barrel** gorong-gorong, sementara pintu air adalah orifis tipis tanpa barrel,
sehingga sebagian besar mode kegagalan itu tidak sampai ke kami. Ia tetap sisi
konservatif, dan dasbor **mengatakannya**, bukan menyembunyikannya.

### Angka yang layak diramalkan di depan penguji

`critical_bf` — nilai BF saat muka air hulu mencapai jalan:

```
BF_kritis = 1 − √(h_bersih / z_jalan)
```

Dengan geometri saat ini (`h_bersih` 0,8 m, `z_jalan` 1,6 m): **BF kritis =
29%**. Menghitungnya dari pengukuran air-bersih saja, lalu **menunjukkan** jalan
tergenang tepat di nilai itu, adalah klaim yang jauh lebih kuat daripada
menarasikan muka air yang naik.

Semua ini `[ASUMSI]` sampai geometri lokasi diukur.

---

## 6.8 Batas yang harus diakui tentang model ini

- **Satu dataset utama, 300 citra, 4 lokasi latih.** Angka-angka ini
  menggambarkan RIPTSeg, **bukan sungai Indonesia**. Jurang domain di
  [`../datasets.md`](../datasets.md) §7 sama sekali belum tertutup: tidak ada
  air cokelat keruh, tidak ada sachet, tidak ada eceng gondok.
- **Set uji 50 citra dari satu lokasi.** Perlakukan selisih di bawah ~0,03
  debris IoU sebagai derau. Jarak SegFormer–LR-ASPP (0,055) mungkin nyata;
  jarak LR-ASPP–DeepLabv3+ (0,006) tidak.
- **Satu seed, ragam antar-run tidak diukur.** Pada 200 citra, ragam itu masuk
  akal sebanding dengan selisih-selisih kecil di atas.
- **Latensi masih x86, bukan Pi.** Angka Pi tetap ekstrapolasi. Jalankan
  `python -m bench.cost` di perangkatnya.
- **Tidak ada angka INT8**, dan kedua jalur penempatan tepi membutuhkannya.
- **`unet_effnet_lite` dan `fast_scnn` punya angka biaya tanpa akurasi**,
  sehingga rekomendasi jalur Hailo bersandar pada penalaran arsitektur, bukan
  pengukuran.
- **`clump` dilebur untuk setiap angka akurasi di sini.** Menghidupkannya
  kembali butuh anotasi sungguhan, bukan heuristik luas.
- **`[BELUM]` Belum ada satu pun citra dari lokasi sasaran** yang dianotasi dan
  dilatih. Anggaran anotasi Fase 2 akan menggerakkan akurasi lebih jauh
  daripada pilihan arsitektur mana pun di dokumen ini.

---

## 6.9 Rekomendasi model per perangkat

| Perangkat | Pilihan | Alasan ringkas |
|---|---|---|
| **GPU (sekarang)** | `segformer_b0` @640 | Paling akurat; 28 ms/bingkai terukur |
| **Raspberry Pi 5, CPU** | `lraspp_mnv3` @512, atau @416 bila anggaran bingkai menuntut | 5,8× lebih cepat untuk kerugian relatif 12% debris IoU; paling tahan penurunan resolusi |
| **Pi 5 + Hailo-8L** | `unet_effnet_lite` atau `lraspp_mnv3` | Keunggulan SegFormer terpusat di resolusi tinggi, tepat di tempat batas memori NPU paling menggigit; blok transformer sering gagal dipetakan ke toolchain NPU |
| **Jetson Orin Nano** | `segformer_b0` | Denda CPU-nya artefak CPU; atensi paralel dengan baik di GPU |
| **Tidak direkomendasikan** | `unet_mnv3` | Debris IoU terburuk, latensi terburuk kedua, parameter terbanyak, overfit paling awal (puncak epoch 6) |
| **Dikecualikan** | `yolo11n_seg` | AGPL-3.0, dan secara struktural tidak bisa menghasilkan coverage (tidak punya kelas air) |

Jangan membaca jarak 512-vs-640 sebagai akurasi gratis: ia memakan 1,8% debris
IoU untuk 40% latensi tambahan. Di 416 biayanya 7,6% — di situlah titik
keputusan yang sebenarnya.

---

## 6.10 Reproduksi

```powershell
$env:PYTHONPATH = "src"

# data
.venv\Scripts\python.exe scripts\download.py --dataset riptseg
.venv\Scripts\python.exe -m data.convert --dataset riptseg
.venv\Scripts\python.exe -m data.splits
.venv\Scripts\python.exe -m data.validate

# latih (model produksi)
.venv\Scripts\python.exe -m train.train --config configs/train/combined_segformer_b0_640.yaml

# ukur
.venv\Scripts\python.exe -m bench.cost
.venv\Scripts\python.exe -m bench.accuracy --config configs/bench_riptseg_all.yaml --split test
.venv\Scripts\python.exe -m bench.report      # menulis docs/model_comparison.md
```

---

[← Daftar isi](README.md) · [Berikutnya: Data pengujian →](07-data-pengujian.md)
