# Rencana penelitian — pemantauan penyumbatan sampah di pintu air

Dokumen induk. Menjelaskan apa yang dibangun, kenapa, dengan rumus apa, lewat
tahapan apa, dan apa saja yang harus disiapkan.

**Konvensi penandaan angka** dipakai konsisten di seluruh dokumen:

| tanda | arti |
|---|---|
| `[UKUR]` | hasil pengukuran nyata di mesin atau lokasi ini |
| `[LIT]` | dari literatur, ada sitasi |
| `[TEBAK]` | penalaran fisik, **belum** dikalibrasi data |

Jangan pernah melaporkan `[TEBAK]` seolah `[UKUR]`. Itu kesalahan yang paling cepat
meruntuhkan proposal saat sidang.

Dokumen terkait:
[`annotation_guideline.md`](annotation_guideline.md) ·
[`datasets.md`](datasets.md) ·
[`../configs/classes.yaml`](../configs/classes.yaml) ·
[`../configs/inference/site_bendungan.yaml`](../configs/inference/site_bendungan.yaml)

---

## 1. Ringkasan

Kamera tetap diarahkan ke kolam hulu sebuah **bendung gerak (pintu air)**. Model
segmentasi memberi label tiap piksel sebagai `water` atau `debris`. Dari mask itu
diturunkan persentase penumpukan sampah di depan pintu, lalu digabung dengan sensor
tinggi air dan curah hujan.

**Pertanyaan yang dijawab sistem ini**, dan tidak bisa dijawab sensor mana pun
sendirian:

> Air naik ini karena hujan di hulu, atau karena pintu tersumbat sampah?

Bedanya penting secara operasional. Yang pertama tidak bisa ditindak. Yang kedua
bisa: kirim petugas, bersihkan, pintu berfungsi lagi.

### Klaim ilmiah

Prediksi tinggi muka air dari curah hujan sudah mapan `[LIT]`, jadi itu **bukan**
kebaruan. Yang belum digarap: **blockage terukur-kamera sebagai variabel masukan**
untuk model tersebut.

```
Model A:  tinggi_air = f(hujan, waktu)                   <- baseline hidrologi
Model B:  tinggi_air = f(hujan, waktu, blockage_kamera)  <- kontribusi penelitian
```

Diuji dengan **studi ablasi**: latih keduanya pada data yang sama, bandingkan
galatnya. Dua kemungkinan hasil, dua-duanya sah dan dilaporkan apa adanya.

---

## 2. Latar belakang

### 2.1 Masalahnya nyata dan terukur

| fakta | angka | sumber |
|---|---|---|
| Dominasi plastik di sungai Jakarta | 74–87 % dari total sampah | `[LIT]` |
| Beban makroplastik Citarum | 6.043 ± 567 item/hari; 1,01 ± 0,19 ton/hari | `[LIT]` |
| Penumpukan sampah | pemicu utama banjir di titik aliran | `[LIT]` |
| Riset debris sungai Asia Tenggara | Indonesia terbanyak, 79 publikasi | `[LIT]` |

### 2.2 Mekanisme fisik penyumbatan

Sungai punya titik sempit — di sini pintu air. Sampah menumpuk di muka pintu, luas
bukaan efektif mengecil, debit yang bisa lewat berkurang, muka air di hulu naik.
Kenaikan itu disebut **afflux**.

Di bendungan (berbeda dari trash rack), air hulu menggenang sehingga sampah
membentuk **rakit permukaan** yang menempel ke muka pintu. Ini justru **lebih
terlihat kamera** daripada sumbatan di jeruji.

Tiga mode kegagalan di lokasi bergerbang:

1. Rakit menutup bukaan → kapasitas limpasan turun → muka air hulu naik
2. Sampah menjepit pintu → pintu tidak bisa dibuka atau ditutup penuh →
   **operator kehilangan kendali debit**
3. Pintu dibuka saat rakit tebal → sampah menyerbu bukaan → macet

Mode ke-2 dan ke-3 adalah kegagalan operasional serius, dan tidak terdeteksi sensor
tinggi air sama sekali.

### 2.3 Posisi terhadap literatur

Yang **sudah** dikerjakan orang:

- Deteksi blockage gorong-gorong dari citra, diklasifikasi ke 4 kelas persentase `[LIT]`
- Pemantauan plastik sungai dari kamera jembatan — **termasuk di Jakarta**, presisi
  68,7 % `[LIT]` (van Lieshout dkk., 2020)
- Prediksi muka air dengan LSTM dari hujan + muka air hulu `[LIT]`
- Prediksi blockage **dari** data hidraulik, arah kebalikan `[LIT]`

Yang **belum** ditemukan di pencarian literatur:

- Blockage terukur-kamera dipakai sebagai **fitur masukan** model prediksi muka air
- Peramalan **kedatangan sampah** dari ramalan hujan
- Konteks bendung gerak Indonesia dengan aliran sampah didominasi sachet

Catatan jujur soal presisi: van Lieshout dkk. mencapai 68,7 % dan menyebut
**pantulan permukaan air** sebagai tantangan utama — persis kondisi kolam tenang di
lokasi ini. Target realistis proyek ini ada di kisaran itu, bukan 95 %.

---

## 3. Lokasi dan kondisi

| aspek | kondisi | implikasi |
|---|---|---|
| Struktur | bendung gerak, pintu bisa dibuka-tutup | ada operator berwenang → alarm punya penerima |
| Posisi kamera | hulu, air menggenang | zona penumpukan terlihat langsung |
| Eceng gondok | **tidak ada** | mekanisme utama gumpalan absen → kelas `clump` dibuang |
| Jenis sampah | kecil, tersebar (plastik, sachet, ranting) | masalah objek kecil; anotasi butuh bantuan model |
| Permukaan air | tenang, memantul seperti cermin | **mode kegagalan model nomor satu** |
| Kecepatan arus | ≈ 0 di hulu | metrik fluks tidak bermakna di sisi ini |

---

## 4. Skema kelas

### 4.1 Yang dianotasi

**Dua kelas saja: `water` dan `debris`.** `background` tidak digambar — ketiadaan
shape sudah berarti background.

```yaml
# configs/classes.yaml
classes:
  - { id: 0, name: background }
  - { id: 1, name: water }
  - { id: 2, name: debris }
  - { id: 3, name: clump }     # tetap terdefinisi, tapi TIDAK dianotasi
ignore_index: 255
collapse:
  clump: debris                # diterapkan saat load, bukan di-bake ke PNG
```

### 4.2 Kenapa `clump` dibuang

1. Lokasi tanpa eceng gondok — mekanisme utama pembentuk agregat tak terpisahkan
2. Sanity floor 1 % ROI di `annotation_guideline.md` §4 sudah melarang menyebut
   objek kecil sebagai clump; sampah di sini mayoritas di bawah ambang itu
3. Kelas dengan sedikit contoh **menurunkan generalisasi model** — kelas langka
   overfit ke konteks sekitar `[LIT]`
4. Setiap penilaian clump/debris adalah potensi ketidaksepakatan antar-anotator

**Reversibel:** id 3 tetap ada, mask di disk tidak tersentuh, hapus dua baris
`collapse` untuk kembali ke 4 kelas tanpa konversi ulang.

### 4.3 Kenapa `debris`, bukan `trash`

Asal-usul sengaja di luar skema. Dari kamera 20 m, membedakan kantong cokelat dari
daun menghasilkan lemparan koin. Dan ranting kayu menyumbat sama efektifnya dengan
sachet.

### 4.4 Kenapa segmentasi, bukan object detection

Konversi hanya satu arah:

```
mask  ---->  bounding box     mudah, tanpa kehilangan informasi
box   --X->  mask             tidak bisa
```

Lima dari tujuh metrik inti butuh **luas piksel**, yang tidak bisa diberikan kotak:
`coverage`, `accumulation_frac`, `area_flux`, `debris_area`, distribusi ukuran.

Alasan historis memilih kotak adalah biaya anotasi — mask manual ~150 jam per 100
gambar Cityscapes vs 1,2 jam untuk titik `[LIT]`. **SAM2 menghapus alasan itu:**
0,025 detik per objek `[UKUR]`.

---

## 5. Rumus lengkap

Notasi: `|X|` = jumlah piksel dalam himpunan X. Semua dihitung di dalam ROI.

### 5.1 Coverage — seberapa kotor permukaan air

```
coverage = |debris| / ( |debris| + |water| )
```

`src/inference/metrics.py:64`

Penyebutnya **air**, bukan luas frame. Kalau dibagi luas frame, angkanya berubah
begitu ada yang menggeser kamera dan porsi langit/tebing yang terlihat berubah.
Dibagi air, angkanya jadi milik sungai.

Kalau `|debris| + |water| = 0` → hasilnya **`None`, bukan 0,0**. Nilai 0,0 terbaca
"sungai bersih", dan itu justru salah fatal kalau yang terjadi adalah ROI tertutup
total saat banjir.

### 5.2 Accumulation — angka blockage

```
accumulation_frac = |debris ∩ structure| / |structure|
```

`src/inference/metrics.py:69`

`structure` = polygon permukaan air tepat di hulu bukaan pintu, tempat rakit
terbentuk. **Bukan** beton bendungannya.

### 5.3 Laju pertumbuhan

```
growth_per_min = ( f₁ − f₀ ) / Δt_menit
```

dengan `f₀`, `f₁` = `accumulation_frac` di awal dan akhir jendela
`growth_window_s`. `src/inference/metrics.py:125`

### 5.4 Logika alarm

```
over_area   = accumulation_frac ≥ area_threshold
over_growth = growth_per_min    ≥ growth_threshold_per_min
triggered   = over_area OR over_growth

streak = streak + 1  bila triggered, else 0
alert  = streak ≥ consecutive
```

`src/inference/metrics.py:127-134`

Dua pemicu, dan yang kedua adalah peringatan dini sesungguhnya: penumpukan cepat
membunyikan alarm **sebelum** ambang luas tercapai. `consecutive` mencegah satu
frame silau mengirim regu pembersih.

Nilai sekarang `[TEBAK]`, di `site_bendungan.yaml`:

```yaml
area_threshold: 0.18
growth_threshold_per_min: 0.03
growth_window_s: 900.0
consecutive: 3
```

### 5.5 Prediksi waktu-ke-kritis

```
t_kritis = ( area_threshold − accumulation_frac ) / growth_per_min
```

Satuan menit. Inilah keluaran "peringatan dini" yang bisa dipakai operator.

### 5.6 Fluks luas

```
area_flux = coverage × velocity × cross_section_width
```

`src/inference/metrics.py:172`

**Tidak bermakna di lokasi ini** selama kamera menghadap kolam tenang
(velocity ≈ 0). Dipertahankan karena gratis, tapi jangan dilaporkan sebagai metrik
utama.

### 5.7 Blockage factor → luas efektif

```
A_efektif = A_bersih × ( 1 − BF )
```

`BF` = blockage factor, diestimasi dari `accumulation_frac`. Metodologi baku ada di
Australian Rainfall and Runoff 2019, Book 6 Chapter 6 `[LIT]`.

### 5.8 Debit lewat pintu (aliran bebas)

```
Q = Cd · b · a · √( 2 · g · h )
```

| simbol | arti | satuan |
|---|---|---|
| `Q` | debit | m³/s |
| `Cd` | koefisien debit, ≈ 0,61 untuk aliran bebas `[LIT]` | — |
| `b` | lebar pintu | m |
| `a` | tinggi bukaan | m |
| `g` | percepatan gravitasi, 9,81 | m/s² |
| `h` | tinggi muka air hulu di atas bukaan | m |

### 5.9 Afflux — inti argumen proyek

Balik persamaan 5.8 untuk mencari head yang dibutuhkan agar debit yang sama tetap
lewat lubang yang lebih kecil:

```
h = Q² / ( Cd² · A² · 2g )       dengan A = b · a

→  h ∝ 1 / A²
```

Rasio terhadap kondisi bersih:

```
h_tersumbat / h_bersih = ( A_bersih / A_tersumbat )² = 1 / (1 − BF)²
```

Karena kuadratik, efeknya **non-linear dan tajam**:

| BF (blockage) | luas tersisa | head yang dibutuhkan |
|---|---|---|
| 10 % | 90 % | 1,23× |
| 20 % | 80 % | 1,56× |
| **30 %** | 70 % | **2,04×** |
| 50 % | 50 % | 4,00× |

**Penyumbatan 30 % sudah melipatduakan kebutuhan head.** Turunan aljabar langsung
dari persamaan orifis. Idealisasi (aliran bebas, debit tetap, perubahan rezim
aliran diabaikan), tapi arah dan besarannya sahih.

Ini juga argumen terkuat kenapa butuh alat ukur, bukan mata: intuisi manusia
membaca hubungan ini sebagai linear, padahal kuadratik.

Pendukung empiris: penumpukan sampah di pintu air dilaporkan menaikkan muka air
14 % `[LIT]` — satu konteks uji, jangan digeneralisasi mentah.

### 5.10 Head loss saringan (Kirschmer) — tidak dipakai di sini

```
Δh = β · (s/e)^(4/3) · sin(α) · v² / (2g)
```

Berlaku untuk trash rack berjeruji. Lokasi ini pintu, bukan jeruji, jadi rantai
orifis (5.8–5.9) yang dipakai. Dicantumkan supaya tidak salah pilih rumus.

### 5.11 Kalibrasi kamera — pose, dan kenapa homografi bergantung tinggi air

Model proyeksi kamera lubang jarum:

```
s · [u, v, 1]ᵀ = K · [ R | t ] · [X, Y, Z, 1]ᵀ
```

| simbol | arti |
|---|---|
| `K` | matriks intrinsik (fokus, titik utama) — dari kalibrasi checkerboard |
| `R`, `t` | rotasi dan translasi kamera terhadap dunia — dari PnP |
| `(u,v)` | koordinat piksel |
| `(X,Y,Z)` | koordinat dunia, meter |

Untuk **bidang air pada ketinggian h** (`Z = h`), dengan `R = [r₁ r₂ r₃]`:

```
H(h) = K · [ r₁ | r₂ | r₃·h + t ]
```

**Inilah alasan homografi tunggal tidak cukup.** `H` bergantung pada `h`. Kalibrasi
saat muka air `h₀` hanya sahih di `h₀`; begitu air naik, sampah mengapung di bidang
lain dan koordinat dunianya meleset — galat terbesar justru saat banjir, momen
paling penting.

Dengan pose kamera `(K, R, t)` diketahui, `H(h)` dihitung untuk tinggi berapa pun,
dan **survei cukup sekali**. Syaratnya: titik acuan **3D dan tidak sebidang** —
titik koplanar membuat solusi pose ambigu.

Alat: `cv2.calibrateCamera` (checkerboard), lalu `cv2.solvePnP`.

### 5.12 Piksel → meter persegi

**Bukan satu faktor skala.** Pada pandangan miring, satu piksel dekat kamera
mewakili luas jauh lebih kecil daripada piksel di kejauhan.

Cara yang benar:

1. Warp mask ke pandangan tegak lurus (ortorektifikasi) dengan `H(h)⁻¹`
2. Hitung piksel di citra hasil warp
3. Kalikan dengan `GSD²`, dengan GSD = ukuran tanah per piksel (meter/piksel)

```
Luas = N_piksel_warp × GSD²
```

### 5.13 Kurva stage–area dan tampungan

```
A(h) = luas permukaan air pada tinggi h      <- dari mask `water` + 5.12
V(h) = ∫ A(h) dh                              <- volume tampungan
```

Normalnya butuh survei batimetri. Di sini diperoleh otomatis dari kamera + sensor
level. **Batas jujur:** kamera hanya melihat sebagian kolam, jadi `A(h)` adalah
bagian yang terlihat, bukan seluruh waduk.

### 5.14 Jeda hujan → kedatangan sampah

Korelasi silang antara deret hujan dan deret coverage:

```
r(τ) = corr( hujan(t), coverage(t + τ) )
τ*   = argmax_τ  r(τ)
```

`τ*` = jeda waktu khas dari hujan sampai sampah tiba. Dipakai untuk meramalkan
lonjakan sampah dari ramalan BMKG. Pertanyaan `E2` di panduan wawancara meminta
tebakan operator soal ini, nanti dibandingkan dengan hasil ukur.

### 5.15 Evaluasi model segmentasi

```
IoU_kelas = |pred ∩ gt| / |pred ∪ gt|
mIoU      = rata-rata IoU seluruh kelas
```

Perhatikan: `src/bench/accuracy.py` membandingkan terhadap skema yang dipakai saat
**melatih**. Checkpoint yang dilatih dengan `collapse` aktif harus dinilai dengan
`collapse` aktif juga, kalau tidak confusion matrix-nya tidak bermakna.

### 5.16 Metrik studi ablasi

```
RMSE = √( Σ(ŷᵢ − yᵢ)² / n )
MAE  = Σ|ŷᵢ − yᵢ| / n

perbaikan(%) = ( RMSE_A − RMSE_B ) / RMSE_A × 100
```

`ŷ` = tinggi air prediksi, `y` = tinggi air terukur sensor. Model A tanpa blockage,
Model B dengan blockage.

---

## 6. Tahapan, langkah demi langkah

### Fase 0 — Menentukan arah (belum butuh alat)

1. Wawancara operator pintu air memakai panduan wawancara
2. Perhatikan jawaban `B1`, `B3`, `C3`
3. Tetapkan jalur:
   - **Jalur A** (pernah macet, ≥ 1×/tahun) → judul: peringatan dini penyumbatan
   - **Jalur B** (tidak pernah) → judul: pemantauan beban sampah vs curah hujan
4. Kalau ragu, cari sumber kedua sebelum memutuskan

> Anotasi **aman dimulai sebelum fase ini selesai** — jalur mana pun butuh label
> yang sama persis. Yang berubah analisisnya, bukan labelnya.

### Fase 1 — Menyiapkan perangkat

1. Pasang kamera menghadap hulu pintu; pastikan zona penumpukan masuk frame
2. Pasang sensor tinggi air dan tipping bucket (ESP32)
3. Pastikan catu daya dan penyimpanan cukup untuk perekaman berkelanjutan
4. Tentukan titik acuan tetap yang selalu terlihat, untuk mendeteksi kamera bergeser
5. Kalau memungkinkan, pasang papan duga air di dalam frame

### Fase 2 — Survei kalibrasi (sekali seumur pemasangan)

1. Ukur **6–8 titik acuan 3D** (X, Y, Z meter) — sebar tinggi, jarak, dan
   kiri-kanan; **jangan sebidang**
2. Catat **tinggi muka air saat survei**
3. Catat **Z sensor level** dalam datum yang sama
4. Ukur **lebar dan tinggi bukaan pintu**
5. Foto checkerboard 15–20 kali dari sudut berbeda, kamera dan fokus yang sama
6. Jalankan `cv2.calibrateCamera` → simpan `K` dan koefisien distorsi
7. Jalankan `cv2.solvePnP` → simpan `R`, `t`

### Fase 3 — Anotasi

1. Jalankan CVAT (`docker compose up -d` di folder `cvat`)
2. Buat project `OPSI` dengan `cvat_labels.json` (2 kelas)
3. Jalankan agent SAM2 (`sam2_interactor.py`, `facebook/sam2.1-hiera-large`)
4. Ambil sampel frame sesuai `annotation_guideline.md` §5:
   - jarak minimal 5 menit antar frame, lebih baik beda hari
   - sebar: waktu, cuaca, tinggi air, kepadatan sampah, kondisi permukaan
   - **15–20 % frame sengaja kosong** — kalau semua frame berisi sampah, model
     belajar bahwa sampah selalu ada
5. **Kalibrasi anotator:** anotasi 10 frame, minta orang kedua menganotasi 10 frame
   yang sama secara terpisah, bandingkan. Beda > 10 % piksel foreground berarti ada
   aturan yang perlu diperjelas — perbaiki dulu sebelum lanjut
6. Anotasi bertahap ~100 frame, latih, lalu pilih frame paling tidak pasti untuk
   100 berikutnya (active learning). Target total 300–500
7. Ekspor **COCO 1.0** segmentation

Cara memakai SAM2 saat menganotasi: **tarik kotak** mengelilingi objek, atau **klik
positif + 1–2 klik negatif** di air sekitarnya. Jangan klik positif tunggal — itu
ambigu, dan pada uji `[UKUR]` justru menangkap seluruh permukaan air.

### Fase 4 — Melatih dan menilai model

1. Konversi ekspor ke skema internal (`adapter: coco_polygon`)
2. Split group-aware (`src/data/splits.py`) — frame dari satu sesi rekaman tidak
   boleh terpisah antara train dan val, kalau tidak metriknya menggelembung
3. Latih beberapa kandidat dari `src/models/registry.py`
4. Nilai dengan mIoU dan IoU per kelas; perhatikan khusus IoU `debris`
5. Periksa manual kasus gagal: pantulan, silau, vegetasi tepi

### Fase 5 — Menjalankan dan mengumpulkan data

1. Jalankan `python -m inference.run --config configs/inference/site_bendungan.yaml`
2. Biarkan merekam sepanjang musim; keluaran ke `out/timeseries.{csv,sqlite}`
3. Gabungkan dengan data hujan dan tinggi air lewat `ts_utc`
4. Kalibrasi ulang `area_threshold` dari data nyata — ubah `[TEBAK]` jadi `[UKUR]`

### Fase 6 — Analisis

1. **Validasi rantai afflux:** plot tinggi air terukur terhadap `1/A²`, cek
   linearitas (5.9)
2. **Studi ablasi:** latih Model A dan B, hitung perbaikan RMSE (5.16)
3. **Jeda hujan–sampah:** korelasi silang, cari `τ*` (5.14)
4. **Distribusi ukuran objek:** komponen terhubung pada mask debris
5. **Validasi tinggi air dari kamera:** bandingkan garis air hasil segmentasi
   dengan sensor level

---

## 7. Yang perlu disiapkan

### 7.1 Perangkat keras

| barang | keterangan |
|---|---|
| Kamera tetap | menghadap hulu pintu, sudut menangkap zona penumpukan |
| Sensor tinggi air | sudah ada di ESP32 (`logic_level.h`) |
| Tipping bucket | curah hujan lokal (`logic_rain.h`) |
| Catu daya + penyimpanan | untuk perekaman berkelanjutan |
| Papan checkerboard | cetak, tempel di papan kaku, untuk kalibrasi intrinsik |
| Meteran / alat ukur | survei titik acuan; ukur dua kali |
| Papan duga air | opsional tapi sangat membantu |

### 7.2 Perangkat lunak

Sudah terpasang dan teruji `[UKUR]`. Rincian di `opsi-annotate/SETUP.md` dan
`opsi-annotate/requirements.txt`:

| komponen | versi | status |
|---|---|---|
| Docker + WSL2 | — | jalan, 18 container CVAT |
| CVAT | 2.73 | jalan di `localhost:8080` |
| torch | 2.13.0+cu130 | CUDA aktif di RTX 5050 |
| cvat-sdk / cvat-cli | 2.73.0 | tervalidasi |
| SAM2 interactor | transformers 5.15 | **teruji inferensi nyata** |
| SAM3 teacher | sam3 0.1.0 | import OK, checkpoint menunggu akses |

### 7.3 Perizinan dan administrasi

- [ ] Surat pengantar sekolah
- [ ] Izin memasang kamera — tanyakan pihak berwenang (pertanyaan `H1`)
- [ ] Izin mengakses data historis operator (pertanyaan `D5`)
- [ ] Nama, jabatan, dan kontak narasumber untuk daftar pustaka
- [ ] Izin mengutip pernyataan narasumber di laporan

### 7.4 Data eksternal

- [ ] Curah hujan BMKG untuk lokasi terdekat — pembanding sekaligus sumber ramalan
- [ ] Catatan historis operator kalau ada (logbook)

---

## 8. Keputusan yang sengaja ditolak

Bagian ini penting saat sidang. Penguji akan menanyakan alternatif; jawabannya
harus sudah siap.

| ditolak | alasan |
|---|---|
| **Membuat model prediksi hujan** | BMKG punya radar, satelit, model numerik, data puluhan tahun. Kelembapan, tekanan, suhu, angin, tutupan awan hanyalah proksi dari yang sudah dimodelkan benar di sana. Hasil realistis terbaik: sedikit lebih buruk dari BMKG. Tipping bucket tetap dipasang, tapi perannya **kebenaran lapangan di titik ini**, bukan prediktor |
| **10 variabel masukan** | Satu musim = banyak baris, sedikit **kejadian** independen. Sepuluh masukan atas puluhan kejadian menghasilkan hafalan, bukan pembelajaran. Pakai empat: hujan, tinggi air, blockage, waktu |
| **LSTM sejak awal** | LSTM di literatur dilatih pada data bertahun-tahun dari jaringan stasiun. Di sini satu musim, satu titik. Model fisik dua parameter berbasis `h ∝ 1/A²` lebih akurat **dan** lebih bisa dipertahankan |
| **Object detection** | Kotak tidak bisa memberi luas; lima dari tujuh metrik inti mati |
| **Klaim "prediksi banjir"** | Sampah datang bersama gelombang banjir → nowcasting, bukan peramalan. Klaim yang bertahan: deteksi penyumbatan dan atribusi penyebab |
| **Roboflow** | Berbayar untuk skala ini, data di pihak ketiga. CVAT swakelola + GPU lokal setara dan gratis |
| **Menunggu SAM3** | Checkpoint digerbang manual. SAM2 tidak digerbang dan sudah teruji jalan |

---

## 9. Risiko dan mitigasi

| risiko | dampak | mitigasi |
|---|---|---|
| **Pantulan dan silau dibaca sebagai sampah** | angka blockage ngawur terus-menerus | banyak frame berpantulan berat dalam set latih; aturan §2.2 ditegakkan; periksa kasus gagal manual |
| Penyumbatan tidak pernah terjadi di lokasi | premis Jalur A runtuh | wawancara operator **sebelum** investasi besar; Jalur B sudah disiapkan |
| Kejadian penting sangat jarang | data sangat tidak seimbang | rekam sepanjang musim, arsipkan agresif; frame ekstrem diprioritaskan saat anotasi |
| Kamera bergeser | kalibrasi dan polygon batal | titik acuan tetap dalam frame; periksa berkala |
| Anotasi melenceng di tengah jalan | label tidak konsisten dan tidak terdeteksi metrik | kalibrasi 20 frame di awal; baca ulang §2 setelah 50 frame |
| Ambang `[TEBAK]` dianggap terukur | proposal runtuh saat ditanya | penandaan `[UKUR]` / `[LIT]` / `[TEBAK]` dipakai konsisten |
| Akses SAM3 tidak turun | percepatan anotasi hilang | SAM2 sudah jalan; SAM3 bonus, bukan syarat |

---

## 10. Referensi

Semua sudah diperiksa keberadaannya, bukan kutipan dari ingatan.

**Sampah sungai Indonesia**
- Mongabay Indonesia — pencemaran Ciliwung, dominasi plastik 74–87 %, beban Citarum
- Tirto — pencemaran Ciliwung, dari tinja hingga popok

**Pemantauan sampah dari kamera**
- van Lieshout dkk. (2020), *Automated River Plastic Monitoring Using Deep Learning
  and Cameras*, Earth and Space Science — kamera jembatan di Jakarta, presisi 68,7 %
- *Quantification of visual blockage at culverts using deep learning based computer
  vision models*, Urban Water Journal (2023)
- *Prediction of hydraulic blockage at culverts from a single image using deep
  learning*, Neural Computing and Applications (2022)

**Hidraulika penyumbatan**
- Australian Rainfall and Runoff 2019, Book 6 Chapter 6 — metodologi blockage factor
- Persamaan debit pintu air, `Cd` ≈ 0,61 untuk aliran bebas

**Prediksi muka air**
- LSTM untuk muka air: studi Nam Ngum (Laos), Tisza (Eropa Tengah), flood level
  forecasting
- Estimasi muka air dari kamera: korelasi 0,93, deviasi < 4 cm

**Kecepatan permukaan**
- LSPIV — Tauro dkk., *Water Resources Research* (2017)

---

## 11. Langkah paling mendesak

Satu hal, dan tidak butuh alat apa pun:

> **Wawancara operator pintu air.**

Jawaban `B1` menentukan judul penelitianmu. Semua persiapan lain bisa jalan
paralel, tapi arah proyek belum terkunci sampai pertanyaan itu terjawab.
