# Bisakah Sistem Ini Memprediksi Banjir?

Riset literatur 2026-08-26. Menjawab satu pertanyaan yang akan ditanya penguji
lebih dulu daripada pertanyaan lain: **apakah alat ini memprediksi banjir, atau
hanya mendeteksinya?**

Jawabannya berbeda untuk tiap jalur sensor, dan perbedaan itu adalah inti
kontribusi proyek.

---

## Ringkasan untuk yang buru-buru

| Jalur | Yang diukur | Lead time | Sifat |
|---|---|---|---|
| Ultrasonik (tinggi air) | Air yang **sudah** sampai | **0** | Deteksi |
| Tipping bucket (hujan) | Hujan **di titik itu** | = waktu konsentrasi DAS | Nowcasting lemah |
| Prakiraan Open-Meteo/BMKG | Hujan yang **akan** turun | jam | Prediksi (regional) |
| **Kamera → afflux** | **Sebab, bukan akibat** | **jam** | **Prediksi (lokal, kausal)** |

**Kesimpulan:** dari perangkat keras ESP32 saja, sistem ini **mendeteksi**,
bukan memprediksi. Kemampuan prediktifnya datang dari jalur kamera — dan justru
di situlah proyek ini berbeda dari puluhan penelitian ESP32 sejenis.

---

## 1. Mengapa sensor tinggi air tidak bisa memprediksi

Ultrasonik terpasang **di titik yang hendak dilindungi**. Saat ia membaca air
naik, airnya sudah ada di sana. Lead time nol menurut definisi.

Ini bukan kelemahan pemasangan yang bisa diperbaiki dengan sensor lebih baik.
Ini geometri: **lead time dibatasi waktu tempuh air dari titik ukur ke titik
yang dilindungi.** Jarak nol → lead time nol.

Literatur menyatakannya tanpa berputar: sebagian besar sistem peringatan dini
operasional untuk hujan ekstrem dan banjir bandang bersandar pada **observasi**
dari jaringan penakar hujan dan radar, bukan prakiraan, sehingga lead time-nya
terbatas beberapa jam dan **peringatan biasanya dikeluarkan saat kejadiannya
sudah berlangsung** [High — pernyataan berulang di Henao Salgado & Zambrano
Nájera (2022) dan tinjauan IWA (2024)].

### Waktu konsentrasi DAS adalah atapnya

Waktu konsentrasi (*time of concentration*) adalah waktu yang dibutuhkan
limpasan untuk mengalir dari titik terjauh secara hidraulik sampai ke keluaran
DAS. Ia langsung membatasi lead time peringatan, dan untuk DAS kecil nilainya
sangat pendek.

Angka dari literatur:

| Konteks | Lead time | Sumber |
|---|---|---|
| DAS pegunungan kecil dan curam | **~20 menit** | Henao Salgado & Zambrano Nájera (2022) |
| Skala perkotaan | median **22 menit**, maks 38 menit | studi EWS perkotaan |
| DAS kecil, sungai pendek | **70–120 menit** | *Sustainability* 15(10):8316 (2023) |
| Metode probabilistik, ambang keyakinan 50% | 1–3 jam | Henao Salgado & Zambrano Nájera (2022) |
| LSTM dengan masukan stasiun hulu | akurat ≤3 jam, rusak >4 jam | Kim (2025) |

**Yang harus dilakukan sebelum mengklaim lead time apa pun:** ukur atau
perkirakan waktu konsentrasi DAS bendung ini. Tanpa angka itu, klaim lead time
tidak punya dasar.

---

## 2. Mengapa penakar hujan hanya sedikit membantu

Tipping bucket memberi lead time sebesar waktu konsentrasi — tapi **hanya untuk
hujan yang jatuh di titik pengukuran**. Banjir di bendung disebabkan hujan di
**seluruh DAS hulu**, dan satu penakar tidak melihatnya.

Batasan yang dicatat literatur: penakar hujan akurat di titiknya tetapi
**cakupan ruangnya terbatas** dan tidak mencerminkan variasi hujan di wilayah
yang lebih luas. Kualitas ambang hujan dibatasi kerapatan, letak, akurasi, dan
panjang rekaman jaringan penakar setempat.

### Ambang hujan butuh sesuatu yang belum kita punya

Metode ambang hujan (*Flash Flood Guidance*, FFG) membandingkan hujan
terakumulasi dengan nilai kritis yang diturunkan dari karakteristik DAS. Sistem
yang serius memakai akumulasi 1, 3, 6, dan 12 jam **dikombinasikan dengan
derajat kejenuhan tanah** (0,25 / 0,5 / 0,75).

Alasannya sederhana dan menghancurkan versi naif: **50 mm hujan di tanah kering
bukan bahaya yang sama dengan 50 mm di tanah jenuh.** Ambang tanpa kondisi
antesenden akan salah di kedua arah — alarm palsu saat kering, terlambat saat
jenuh.

Empat pendekatan penetapan ambang menurut Henao Salgado & Zambrano Nájera
(2022):

1. **Empiris** — korelasikan rekaman banjir historis dengan data hujan
2. **Hidrologis/hidrodinamik** — model hujan-limpasan dan hidraulik
3. **Probabilistik** — tambahkan analisis ketidakpastian dan fungsi biaya-manfaat
4. **Gabungan**

Metode empiris **paling cocok untuk daerah bermodal data tipis** — yang berarti
itu pilihan realistis untuk proyek ini, tapi ia tetap menuntut rekaman banjir
historis yang saat ini belum ada. Ini bahan wawancara operator, bukan bahan
sensor.

---

## 3. Jalur kamera: satu-satunya prediksi sungguhan di sistem ini

Semua penelitian ESP32 pembanding (lihat §6) mengukur **akibat** — air sudah
naik. Sistem ini mengukur **sebab**, sebelum akibatnya muncul.

```
sampah menumpuk (jam)  →  BF naik  →  1/(1−BF)²  →  muka air naik  →  jalan tergenang
        ↑                                                    ↑
   kamera lihat di sini                        ultrasonik baru lihat di sini
```

Selisih waktu antara dua panah itu **adalah** lead time proyek ini, dan ia
berjam-jam: penumpukan sampah tumbuh perlahan sementara muka air naik cepat
begitu bukaan sudah menyempit.

### `critical_bf` adalah ramalan, bukan pengukuran

`src/physics.py` menghitung:

```
BF_kritis = 1 − √(h_bersih / z_jalan)
```

Dengan geometri sementara (0,8 m dan 1,6 m): **29%**. Artinya sistem dapat
menyatakan, **sebelum air naik sedikit pun**, bahwa jalan akan tergenang saat
penyumbatan mencapai 29%.

Ini prediksi dalam arti yang paling ketat: pernyataan tentang keadaan masa depan
yang diturunkan dari hukum fisika dan pengukuran saat ini, yang bisa salah dan
karena itu bisa diuji.

**Ini klaim terkuat yang dimiliki proyek, dan ia tidak membutuhkan satu pun deret
waktu historis.** Itulah alasan utama mengapa jalur ini, bukan LSTM, yang layak
jadi pusat laporan.

### Peringatannya tetap berlaku

Rantai ini masih `[ASUMSI]` sampai geometri pintu diukur, dan `1/(1−BF)²`
mengkuadratkan kesalahan kamera — lihat [`referensi_fisika.md`](referensi_fisika.md)
dan [`laporan/06-model-ai.md`](laporan/06-model-ai.md) §6.7.

---

## 4. LSTM: tidak mungkin, dan sebaiknya tidak dicoba

Ini jawaban langsung atas pertanyaan yang memicu dokumen ini.

### Apa yang dibutuhkan LSTM

Model LSTM peramalan muka air dilatih pada deret waktu berpasangan
hujan–muka-air yang mencakup **banyak kejadian banjir**. Literatur yang dikutip
di §8 melatih pada rekaman **bertahun-tahun** dari stasiun terpasang tetap.
Akurasinya menurun seiring lead time membesar, dan penelitian yang memperluas
matriks masukan menemukan **tidak ada perolehan akurasi, bahkan penurunan skill
di atas 4 jam**.

### Apa yang kita punya

| Kebutuhan | Punya kita |
|---|---|
| Deret waktu muka air | **0 bacaan sah** — `n_sampel = 0` di seluruh 25 baris |
| Kejadian banjir dalam data latih | **0** |
| Rentang waktu terekam | ~1 jam ESP + ~30 jam kamera (uji meja) |
| Stasiun hulu | tidak ada |
| Rekaman historis lokasi | tidak ada |

### Kalau besok mengambil data satu hari penuh

Anggap ultrasonik berhasil diperbaiki dan mencatat sepanjang hari: satu hari
pada 1 baris/menit = **1.440 baris, dan nol kejadian banjir** (kecuali kebetulan
banjir besok).

LSTM yang dilatih pada itu akan menghasilkan sesuatu — jaringan saraf selalu
menghasilkan sesuatu. Yang dihasilkannya adalah interpolasi fluktuasi normal
satu hari, dan ia **tidak pernah melihat satu pun contoh dari kelas kejadian
yang seharusnya diramalkan**.

### Pertanyaan yang akan menjatuhkannya

> "Berapa kejadian banjir yang ada di data latih Anda?"

Jawaban "nol" mengakhiri pembahasan, dan pertanyaan itu **pasti** ditanyakan.
Menampilkan LSTM dengan RMSE bagus di atas data tanpa banjir bukan sekadar
lemah — ia memberi kesan mampu yang tidak dimiliki sistem, pada alat yang
mengeluarkan peringatan banjir.

**Rekomendasi: jangan pakai LSTM di laporan ini.** Sebut sebagai pekerjaan
lanjutan dengan syarat eksplisit — misalnya "setelah satu musim hujan penuh
terekam dan mencakup minimal beberapa kejadian luapan". Itu justru terbaca
sebagai kematangan metodologis, bukan kekurangan.

### Yang bisa menggantikannya, dan sudah setengah jadi

**Ekstrapolasi linear laju perubahan.** Ini yang sebenarnya dilakukan LSTM pada
lead time pendek, tanpa perlu pelatihan sama sekali:

```
menit_ke_ambang = (ambang − nilai_sekarang) / laju_perubahan
```

Kode ini **sudah ada** di `web/lib/verdict.ts`, diterapkan pada penumpukan
sampah:

```ts
const minutes = (areaThreshold - frac) / growth;
```

Pola yang sama bisa langsung diterapkan pada `tinggi_cm` begitu ultrasonik
hidup. Ia jujur (jelas-jelas linear, tidak berpura-pura pintar), tidak butuh
data latih, dan bisa dijelaskan dalam satu baris di depan penguji.

Teori mendukung pendekatan ini: hidrograf difusi memprediksi kenaikan progresif
kedalaman air dan **laju kenaikan** untuk hujan berintensitas tetap, dan laju
kenaikan itu bergantung pada intensitas hujan dan kecepatan respons DAS.

---

## 5. Peringkat langkah nyata, termurah lebih dulu

**1. Gratis — masukkan prakiraan hujan ke logika peringatan.**
`src/external/rainfall.py` sudah menarik Open-Meteo (arsip + prakiraan) dan
BMKG. Itu **satu-satunya masukan prediktif hidrologis yang sudah dimiliki
sistem**, dan sekarang hanya ditampilkan sebagai kartu, belum masuk putusan.
Gabungkan: prakiraan hujan 3 jam + tinggi air sekarang + BF sekarang.

Batasannya wajib ikut ditampilkan: petak Open-Meteo 9–25 km sementara sel hujan
konvektif tropis 2–5 km. Ini sinyal regional, bukan hujan di bendung.

**2. Murah — satu ESP32 kedua di hulu.**
Waktu tempuh air dari hulu ke bendung adalah lead time gratis, dan besarnya
persis jarak dibagi kecepatan aliran. Ini rasio manfaat-biaya tertinggi dari
seluruh daftar. Literatur LSTM konsisten pada titik ini: menambah **stasiun
hulu** menaikkan skill, sementara menambah sensor lain di titik yang sama tidak.

**3. Sudah ada — jadikan jalur afflux sebagai pusat klaim.** Lihat §3.

**4. Butuh musim — kelembapan tanah dan ambang hujan terkalibrasi.** Perlu
rekaman historis; sebagian bisa digali dari wawancara operator.

**5. Butuh tahun — LSTM.** Lihat §4.

---

## 6. Posisi terhadap penelitian sejenis

Penelitian ESP32 + sensor ultrasonik untuk peringatan banjir di Indonesia sudah
banyak, dan klaimnya konsisten berupa **akurasi sensor dan keandalan
transmisi**, bukan lead time:

| Penelitian | Klaim utama |
|---|---|
| Jombang, ESP32 + HC-SR04 | 98,63% keberhasilan transmisi; akurasi sensor 97,69%, MAE 2,31% |
| Semarang, ESP32S2 + A01NYUB (banjir rob) | RMSE 0,08943 |
| JNEST, ESP32 + HC-SR04 + Blynk | akurasi hingga 99,7%; jeda notifikasi 1,2 detik |
| Deteksi level + ESP32 Camera + TinyML | klasifikasi level di perangkat |

Tidak satu pun mengklaim lead time, karena memang tidak ada.

**Implikasi untuk penyusunan laporan.** Kalau proyek ini diposisikan sebagai
"sistem peringatan banjir berbasis IoT", ia akan dibandingkan dengan kelompok di
atas, dan pembandingnya adalah akurasi sensor — pertandingan yang tidak menarik
dan tidak dimenangkan siapa pun.

Posisi yang benar: **prediksi kenaikan muka air (afflux) akibat penyumbatan
sampah pada pintu air, dengan segmentasi citra sebagai pengukur penyumbatan.**
Sensor tinggi air berperan sebagai **verifikasi** ramalan itu, bukan sebagai
sumber ramalan.

Dalam posisi itu, pembandingnya bukan lagi paper ESP32 melainkan Mohammed (2022)
dan pedoman penyumbatan ARR — dan di sana kontribusinya jelas: keduanya
mengukur penyumbatan secara manual di flume atau mengasumsikannya dalam model,
sementara proyek ini **mengukurnya terus-menerus dari kamera di lapangan**.

---

## 7. Kalimat yang aman dipakai di laporan dan sidang

**Boleh:**

- "Sistem memprediksi kenaikan muka air akibat penyumbatan, dengan lead time
  sebesar waktu tumbuh penumpukan sampah."
- "Sistem mendeteksi tinggi muka air dan curah hujan di titik pengukuran secara
  waktu-nyata."
- "Ekstrapolasi linear laju penumpukan memberi perkiraan waktu menuju ambang."
- "Prediksi hidrologis memerlukan stasiun hulu atau prakiraan hujan; keduanya
  tercatat sebagai pekerjaan lanjutan."

**Jangan:**

- "Sistem memprediksi banjir." — terlalu luas; jalur mana?
- "Sistem memberi peringatan dini X jam sebelum banjir." — belum ada satu pun
  kejadian yang mengujinya.
- "Menggunakan LSTM/deep learning untuk peramalan banjir." — tidak ada data
  latihnya. Segmentasi citranya memang deep learning; peramalannya tidak.
- Angka lead time apa pun sebelum waktu konsentrasi DAS diketahui.

---

## 8. Daftar pustaka

**P1.** Henao Salgado, M. J., & Zambrano Nájera, J. (2022). *Assessing Flood
Early Warning Systems for Flash Floods.* **Frontiers in Climate 4**: 787042.
DOI `10.3389/fclim.2022.787042`.
Dipakai untuk: empat metode penetapan ambang hujan; lead time ~20 menit untuk
DAS pegunungan kecil; 1–3 jam untuk metode probabilistik; ketidakcocokan skala
antara prakiraan cuaca numerik regional dan DAS kecil.

**P2.** *A literature review: rainfall thresholds as flash flood monitoring for
an early warning system.* **Water Practice & Technology 19**(11): 4486 (2024).
Dipakai untuk: batasan penakar hujan (cakupan ruang, kerapatan jaringan);
akumulasi 1/3/6/12 jam dikombinasikan derajat kejenuhan tanah; pernyataan bahwa
lead time sistem berbasis observasi terbatas beberapa jam.

**P3.** *Assessment of the Feasibility of Implementing a Flash Flood Early
Warning System in a Small Catchment Area.* **Sustainability 15**(10): 8316
(2023). Dipakai untuk: lead time 70–120 menit pada DAS kecil bersungai pendek.

**P4.** *Rates of River Level Rise: Observations and Theory.* **Hydrological
Processes**. DOI `10.1002/hyp.70516`.
Dipakai untuk: hidrograf difusi memprediksi laju kenaikan muka air dari
intensitas hujan dan kecepatan respons DAS — dasar teoretis ekstrapolasi laju.

**P5.** Kim (2025). *Prediction of Flood Level Using LSTM and Watershed
Hydrological Data.* **Journal of Flood Risk Management**.
Dipakai untuk: akurasi LSTM tinggi dalam lead time 3 jam, menurun setelahnya;
kebutuhan data hidrologi DAS.

**P6.** *Evaluation of rainfall-threshold methods for flash flood warnings based
on soil moisture conditions.* **Natural Hazards** (2025). DOI
`10.1007/s11069-025-07272-6`.
Dipakai untuk: perlunya kondisi kelembapan tanah antesenden dalam ambang hujan.

**P7.** *Does More Data Always Help? Input Configuration Impacts on LSTM-based
Water Level Prediction.* Research Square (praterbit).
Dipakai untuk: memperluas matriks masukan tidak menaikkan akurasi dan menurunkan
skill di atas lead time 4 jam. `[Praterbit — perlakukan sebagai indikatif]`

**P8.** Penelitian ESP32 pembanding:
- *Instrumentation for Monitoring and Early Warning of Tidal Flood Using ESP32S2
  and A01NYUB Ultrasonic Sensor in Tambakrejo, Semarang.* **IOP Conf. Ser.:
  Earth Environ. Sci. 1350**: 012046. DOI `10.1088/1755-1315/1350/1/012046`
- *Implementasi Sistem Peringatan Banjir Dini dengan Sensor HC-SR04 Berbasis
  ESP32 Internet of Things.* **Computer Journal** (studi lapangan di bendungan,
  Kabupaten Jombang)
- *IoT-Based Real-Time River Monitoring and Early Flood Warning Using ESP32 and
  HC-SR04.* **Journal of Novel Engineering Science and Technology**

Sumber fisika afflux (Mohammed 2022, Ollett dkk. 2017, USBR) ada di
[`referensi_fisika.md`](referensi_fisika.md).

---

## 9. Apa yang belum diverifikasi di dokumen ini

- **Waktu konsentrasi DAS bendung sasaran belum diketahui.** Seluruh angka lead
  time di §1 berasal dari DAS lain di literatur, dan **tidak boleh dikutip
  sebagai lead time proyek ini**.
- P2, P3, dan P4 diakses lewat ringkasan pencarian dan metadata; teks penuhnya
  terhalang akses berbayar saat riset ini dilakukan.
  `[Medium — angka utamanya konsisten di beberapa sumber, tapi belum dibaca dari
  terbitan aslinya halaman demi halaman]`
- P7 praterbit dan belum ditinjau sejawat.
- Belum ada perbandingan kuantitatif antara lead time jalur afflux dan jalur
  hidrologis di lokasi ini, karena keduanya belum terukur.

---

Lihat juga: [`survei_lapangan.md`](survei_lapangan.md) — daftar data yang harus
diambil di lokasi, diurutkan menurut seberapa banyak yang tertahan tanpanya.
