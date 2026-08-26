# Referensi fisika: dari mana rumus afflux berasal

Riset literatur 2026-08-24. Sebelum ini, rumus di `src/physics.py` diambil dari
`rencana_penelitian.md` tanpa verifikasi ke literatur primer. Dokumen ini
menutup lubang itu, dan **menemukan dua hal yang mengubah cara angka harus
dibaca**.

Setiap klaim di bawah punya sumber. Yang tidak terverifikasi ditandai begitu.

---

## Ringkasan untuk yang buru-buru

| Pertanyaan | Jawaban | Sumber |
|---|---|---|
| `Q = Cd·A·√(2gh)` benar untuk pintu air? | Ya, pintu sorong = orifis persegi | USBR WMM Bab 9 |
| `Cd = 0,61` benar? | Ya, dan itu **hasil kali** `Cc·Cvf·Cva` | USBR WMM 9-5 |
| `h ∝ 1/A²` benar? | Ya, standar | USBR; Meusburger; ARR |
| Sampah **terapung** benar-benar menyumbat pintu **bawah**? | **Ya, terukur +15% muka air hulu** | Mohammed (2022) |
| Metode kami punya nama? | Ya: **Reduced Area Method (RAM)** | Ollett dkk. (2017) |
| Apakah RAM tepat untuk kasus kami? | **Tidak sepenuhnya — RAM melebih-lebihkan** | Ollett dkk. (2017) |

---

## 1. Persamaan debit pintu — terverifikasi

**Sumber:** US Bureau of Reclamation, *Water Measurement Manual*, Bab 9
(Submerged Orifices), §5.

Persamaan yang dipakai USBR:

```
Q = Cd · A · √(2 g Δh)
```

- `Q` debit, `A` luas bukaan, `Δh = h₁ − h₂` beda tinggi tekan, `g` gravitasi
- `Cd = 0,61`

Yang **tidak** saya tahu sebelum riset ini, dan penting saat sidang:

> `Cd` bukan satu bilangan ajaib. USBR menyebut *the effective discharge
> coefficient, Cd, is the product CcCvfCva* — koefisien kontraksi × koefisien
> kecepatan (gesekan) × koreksi kecepatan pendekat.

Jadi kalau penguji bertanya "0,61 itu dari mana", jawabannya bukan "dari buku"
melainkan: `Cc ≈ 0,61` adalah **koefisien kontraksi** aliran yang menyempit di
bawah daun pintu (*vena contracta*), dan dua faktor lain mendekati 1 pada
kondisi standar.

**Syarat pakai** (USBR): kecepatan pendekat dapat diabaikan, dan beda tinggi
tekan > 0,2 ft ≈ 6 cm.

**Pintu sorong sebagai orifis:** USBR menyatakan persamaan 9-2 dapat dipakai
untuk pintu sorong karena pintu sorong pada dasarnya orifis persegi dengan
kontraksi dasar/samping tertekan dan luas bukaan yang bisa diubah. `[Medium]` —
dibaca dari ringkasan pencarian, halaman aslinya belum dibuka utuh.

### Aliran bebas vs tenggelam

Pembeda ini harus diperiksa di lapangan, karena `Cd` berbeda:

- **Henry (1950)** — diagram klasik `Cd` terhadap `h/a`; asumsi `Cc = 0,61`.
- **Swamee (1992)** — kriteria aliran bebas `H ≥ 0,81 · y₂ · (y₂/G)^0,72`;
  di luar itu aliran tenggelam.
- Praktik: **insinyur irigasi AS umumnya memakai `Cd` tetap 0,61–0,63** untuk
  semua pintu sorong tenggelam, tanpa memandang kondisi masuk dan ukuran pintu.
- Aliran bebas selalu punya `Cd` lebih besar daripada tenggelam. Aliran bebas
  bergantung pada tinggi hulu dan bukaan; tenggelam **juga** bergantung pada
  muka air hilir.

> **Konsekuensi:** kalau pintu di lokasi beroperasi tenggelam — kemungkinan
> besar, karena bendung gerak menahan air — `Cd` 0,61 masih layak, tapi **muka
> air hilir wajib dicatat** saat survei. Pertanyaan tambahan untuk operator.

---

## 2. `h ∝ 1/A²` — terverifikasi, lewat dua jalur

### Jalur pertama: orifis

Balikkan persamaan USBR:

```
h = Q² / (Cd² · A² · 2g)     →     h ∝ 1/A²
```

### Jalur kedua: kehilangan tinggi tekan (independen)

Literatur *trash rack* (saringan sampah PLTA) sampai ke bentuk yang sama lewat
kehilangan energi, bukan lewat orifis — jadi ini konfirmasi independen:

```
K_T = 2g · A_T² · (H₁ − H₂) / Q²      →      H₁ − H₂ = K_T · Q² / (2g · A_T²)
```

`A_T` = luas aliran bersih saringan. Sekali lagi **`Δh ∝ 1/A²`**.

- **Meusburger (2002)** — rumus kehilangan tinggi tekan saringan yang
  memperhitungkan jarak batang kecil, bentuk batang, kemiringan, dan **efek
  penyumbatan lewat rasio penghalang tambahan**. Kehilangan bergantung pada
  faktor bentuk batang `K_F`, rasio penghalang `p`, sudut kemiringan, kecepatan
  pendekat, dan `g`.
- **Raynal dkk.** (HAL hal-04086634) — memasukkan rasio penyumbatan ke dalam
  rasio penghalang memberi perkiraan koefisien kehilangan yang cukup baik untuk
  saringan tegak maupun miring; **selisih terhadap eksperimen kadang 25%**.

> Angka 25% itu penting dan jujur: bahkan di laboratorium, dengan geometri
> saringan yang diketahui persis, model penyumbatan meleset seperempatnya.
> Jangan menjanjikan ketelitian sentimeter di sidang.

---

## 3. Temuan yang mengubah sesuatu (1): metode kami punya nama, dan ada kritiknya

**Sumber:** Ollett, P., Syme, B., & Ryan, P. (2017). *Australian Rainfall and
Runoff guidance on blockage of hydraulic structures: numerical implementation
and three case studies.* Journal of Hydrology (New Zealand) **56**(2): 109–122.
Merangkum ARR 2016 Book 6 Chapter 6.

ARR membedakan **dua** cara memodelkan penyumbatan:

| | Reduced Area Method (RAM) | Energy Loss Method (ELM) |
|---|---|---|
| Caranya | Kecilkan luas: `A' = A · BR` | Luas tetap, naikkan koefisien kehilangan masuk `k'e` |
| Notasi ARR | `BR = A'/A`, rasio ruang bebas | `k'e` dari Pers. 11 |
| **Yang kita pakai** | ✅ | ❌ |

**`BF` kita = `1 − BR` ARR.** Hati-hati: ARR memakai singkatan `BF` untuk arti
yang berbeda (`Q'/Q`, rasio debit). Jangan tertukar saat mengutip.

### Kritik yang mengenai kita

Kutipan dari abstrak:

> "the alternative energy loss method produced more realistic headwater levels
> compared to those resulting from the common industry approach of reducing
> culvert area, which can exaggerate energy losses"

Contoh terhitung mereka (gorong-gorong D = 0,75 m, penyumbatan 50%, HW/D 2,5):

| Metode | Muka air hulu |
|---|---|
| RAM | **6,04 m** |
| ELM | **4,71 m** |

RAM **28% lebih tinggi**. Alasannya dinyatakan eksplisit: RAM mengecilkan luas
di **sepanjang barel**, sehingga kecepatan di dalam barel melonjak dan
kehilangan gesekan serta kehilangan keluaran ikut menggelembung.

### Aturan pemilihan ARR — dan di sinilah kita di sisi yang salah

> "the RAM should be applied to 'bottom up' blockage, caused, for example, by
> sedimentation. This is because the RAM reduces the culvert area along the
> entire length of the barrel... The ELM should be applied in cases where the
> blockage occurs at the entrance of the structure"

**Sampah terapung di muka pintu adalah penyumbatan di MULUT, bukan sedimentasi
dari dasar.** Menurut aturan ARR, kasus kita seharusnya ELM.

### Kenapa RAM tetap dipakai — pembelaan, bukan pengabaian

Alasan spesifik RAM melebih-lebihkan adalah **kecepatan barel yang menggelembung
menaikkan gesekan sepanjang barel**. Sebuah **pintu air tidak punya barel** —
pintu adalah orifis tipis. Mode kegagalan yang dituduhkan ARR sebagian besar
tidak berlaku di sini.

Tapi tidak seluruhnya hilang. Sikap yang jujur:

> **Angka afflux kami adalah BATAS ATAS (konservatif), bukan taksiran terbaik.**

Untuk peringatan dini banjir, batas atas adalah sisi yang benar untuk salah.
Tapi harus **dikatakan**, bukan disembunyikan. Karena itu label di web memakai
kata "batas atas".

### Dua angka lain yang berguna dari makalah ini

- "high blockage factors can lead to a four-fold increase in headwater level
  compared with low blockage factors" — persis non-linearitas `1/(1−BF)²` kita.
  `BF` 0,5 → faktor 4,0. Cocok.
- `BF = BR^(5/4)` (Witheridge 2009) — perkiraan pengurangan kapasitas debit
  untuk kendali masuk. Bukan yang kita hitung, tapi ada kalau ditanya.
- ARR **menganjurkan uji sensitivitas dengan kedua metode**. Kita baru punya
  satu. Lihat §6.

---

## 4. Temuan yang mengubah sesuatu (2): sampah terapung memang menyumbat pintu bawah

Ini pertanyaan paling menentukan untuk seluruh proyek, dan sebelum riset ini
tidak ada bukti untuk menjawabnya: kalau pintu membuka dari **bawah** sementara
sampah mengapung di **permukaan**, apakah sampah benar-benar mengurangi luas
bukaan?

**Sumber:** Mohammed, A. Y. (2022). *Driftwood blocking sensitivity on sluice
gate flow.* Open Engineering **12**: 384. DOI 10.1515/eng-2022-0384.

Percobaan flume dengan batang kayu dan bonggol akar berbagai panjang dan
diameter, pada beberapa bukaan pintu dan tinggi muka air hulu.

**Hasilnya:**

1. **Penumpukan menaikkan kedalaman air hulu sebesar 15%.** Terukur, bukan
   dimodelkan. Premis proyek selamat.
2. Bukaan pintu yang lebih besar **dan** tinggi hulu sekitar 50% dari maksimum
   → kemungkinan kayu tersangkut **turun**; kayu lolos ke bawah pintu.
3. **Bonggol akar lebih mudah menyumbat daripada batang.** Bentuk tiga dimensi
   yang menggumpal lebih menyumbat daripada benda memanjang.
4. Kayu yang tersangkut **di bawah** pintu memicu gerusan (*scour*).

Sumber pendukung menyatakan penumpukan kayu di hulu struktur hidraulik "may
block and reduce flow area for water passage downstream, which causes rising
upstream water level and reduced discharge through the hydraulic structure."

### Yang harus diakui dari temuan ini

Poin 2 dan 3 menampar asumsi pemetaan kamera → `BF` lebih keras daripada yang
tertulis sebelumnya.

Kamera mengukur `accumulation_frac`: **pecahan LUAS PERMUKAAN 2D** di dalam
poligon `structure`. Yang menentukan penyumbatan sebenarnya adalah **volume,
bentuk, dan kedalaman rendaman** benda — bonggol akar dan lembaran plastik
dengan luas permukaan sama sekali tidak setara.

Lebih jauh: peluang menyumbat **berubah dengan bukaan pintu dan tinggi hulu** —
dua besaran yang berubah-ubah sepanjang hari saat operator mengatur pintu.

Konsekuensinya untuk `configs/site_geometry.json`:

```
BF = skala · accumulation_frac + bias
```

Pemetaan linier dua parameter ini **bukan sekadar koreksi skala kamera**. Dia
menyerap seluruh fisika "luas permukaan 2D → luas bukaan 3D yang hilang", dan
fisika itu **bergantung pada bukaan pintu**. Kalibrasi E2 harus dilakukan
**per-bukaan-pintu**, atau `skala` harus dijadikan fungsi bukaan.

Ini bukan alasan membatalkan model. Ini alasan **tidak menyebut angkanya
terkalibrasi sebelum E1/E2 selesai** — yang memang sudah ditegakkan lencana
`BELUM DIKALIBRASI`.

---

## 5. Catatan tambahan yang layak dikutip

Dari literatur afflux jembatan: pembulatan pilar atau pemberian *cutwater* tajam
tidak hanya mengurangi afflux, tapi juga mengurangi kecenderungan pilar
mengumpulkan sampah — dan efek yang kedua **bisa lebih menentukan terhadap
afflux daripada bentuk pilarnya sendiri**.

Artinya: dalam hidraulika arus utama, sampah sudah diakui sebagai penyebab
afflux yang bisa melebihi geometri struktur. Argumen pembuka yang kuat untuk
proposal.

Untuk pintu air di daerah dingin, es terapung masuk ke celah pintu dan "can
paralyze the regulation functions of the gates" (MDPI *Hydrology* 13(3): 86).
Bukan kasus Indonesia, tapi mekanismenya sama: benda terapung melumpuhkan
pengaturan pintu, bukan sekadar mengurangi luas.

---

## 6. Yang belum dikerjakan

- [ ] **Implementasi ELM sebagai pembanding.** ARR menganjurkan uji sensitivitas
      dengan kedua metode. Persamaan 11 (`k'e`) ada di makalah tapi hasil OCR-nya
      ambigu dan **tidak berhasil dicocokkan dengan Tabel 2 makalah itu sendiri**,
      jadi tidak ditebak. Perlu PDF asli yang teksnya bisa diseleksi.
- [ ] **USBR Bab 9 §1** untuk pernyataan eksplisit "pintu sorong = orifis
      tertekan" — baru dari ringkasan pencarian. `[Medium]`
- [ ] **Makalah Mohammed (2022) utuh** — angka 15% dari abstrak; setup flume,
      rentang bukaan, dan sebaran datanya belum terbaca. Semua akses
      (De Gruyter, Academia, ADS) menolak pengambilan otomatis.
- [ ] **Muka air hilir** — untuk memastikan aliran bebas atau tenggelam. Tambah
      ke daftar survei dan wawancara operator.

---

## Daftar pustaka

1. **U.S. Bureau of Reclamation.** *Water Measurement Manual*, Chapter 9:
   Submerged Orifices, §5.
   <https://www.usbr.gov/tsc/techreferences/mands/wmm/chap09_05.html>
2. **Ollett, P., Syme, B., & Ryan, P. (2017).** Australian Rainfall and Runoff
   guidance on blockage of hydraulic structures: numerical implementation and
   three case studies. *Journal of Hydrology (New Zealand)* 56(2): 109–122.
   <https://www.hydralinc.com/wp-content/uploads/JoHNZ-V56-2-2017-ARR-Blockage-Ollett-Ryan-Syme.pdf>
3. **Mohammed, A. Y. (2022).** Driftwood blocking sensitivity on sluice gate
   flow. *Open Engineering* 12: 384. DOI 10.1515/eng-2022-0384.
   <https://www.degruyterbrill.com/document/doi/10.1515/eng-2022-0384/html>
4. **Meusburger, H. (2002).** Rumus kehilangan tinggi tekan saringan sampah
   dengan rasio penghalang. Dirujuk melalui (5).
5. **Raynal, S. dkk.** Fish-friendly trashracks: headloss formula and clogging
   effect for inclined racks. HAL hal-04086634.
   <https://hal.science/hal-04086634/document>
6. **Henry, H. R. (1950).** Diagram koefisien debit pintu sorong. Dirujuk melalui (8).
7. **Swamee, P. K. (1992).** Kriteria pembeda aliran bebas dan tenggelam di
   bawah pintu sorong. Dirujuk melalui (8).
8. **Nasehi Oskuyi, N. & Salmasi, F. (2012).** Vertical Sluice Gate Discharge
   Coefficient. *Journal of Civil Engineering and Urbanism* 2(3): 108–114.
   <https://www.ojceu.ir/main/attachments/article/17/JCEU-B20,%20108-114,%202012.pdf>
9. **Australian Rainfall and Runoff (2016).** Book 6, Chapter 6: Blockage of
   Hydraulic Structures. <http://www.arr-software.org/pdfs/ARR_190514_Book6.pdf>

Sumber (4), (6), (7) **dirujuk lewat sumber lain, bukan dibaca langsung**.
Jangan mengutipnya seolah sudah dibaca.
