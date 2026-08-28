# Hasil wawancara operator pintu air

Catatan lapangan, bukan panduan. Pertanyaannya ada di
[`wawancara_operator.md`](wawancara_operator.md); di sini yang tercatat adalah
jawabannya, apa yang berubah karenanya, dan apa yang masih menggantung.

| | |
|---|---|
| Tanggal & jam wawancara | *belum dicatat — isi sebelum dikutip di laporan* |
| Nama & jabatan narasumber | *belum dicatat* |
| Nomor kontak | *belum dicatat* |
| Bentuk catatan | ringkasan tertulis, bukan transkrip verbatim |

> Tanpa tanggal dan nama, jawaban di bawah tidak bisa masuk daftar pustaka OPSI.
> Ini yang pertama harus dilengkapi, bukan yang terakhir.

---

## 1. Jawaban yang terekam

Kode mengikuti daftar pertanyaan di panduan. `—` berarti tidak terjawab.

### A. Operasi harian

| Kode | Pertanyaan | Jawaban |
|---|---|---|
| A1 | Lama bertugas | 3 tahun |
| A2 | Jumlah & jenis pintu | Dua kategori: **hidrolis** dan **balok manual**. Jumlah bukaan per kategori belum ditanyakan |
| A3 | Frekuensi buka-tutup | — |
| A4 | Siapa yang memutuskan | Operator sendiri, bukan perintah kantor |
| A5 | Dasar keputusan buka | Dua pemicu: **musim hujan** dan **"kebutuhan panitia"**. Kriteria terukurnya tidak sempat digali |
| A6 | Jaga malam | **Ada, dijaga penuh** — dan lebih ketat lagi saat hujan |

### B. Kejadian sampah

| Kode | Pertanyaan | Jawaban |
|---|---|---|
| B1 | Pernah pintu susah dibuka? | **Pernah, tapi "itu dulu"** |
| B1a | Sebabnya | Dua sebab berbeda: (1) pintu hidrolis macet karena **alat pembukanya rusak**; (2) **sampah menghalangi** |
| B2 | Kapan terakhir | — (hanya "dulu") |
| B3 | Frekuensi per tahun | — |
| B5 | Pernah tak bisa ditutup | — |
| B6 | Jenis sampah tersulit | Kangkung, eceng gondok, dan sampah lain |
| B8 | Titik penumpukan | — (belum ditunjuk/difoto) |

### C. Pembersihan

| Kode | Pertanyaan | Jawaban |
|---|---|---|
| C1 | Siapa yang membersihkan | Operator sendiri, dibantu rekan; bisa juga dari pengawas |
| C2 | Frekuensi | — |
| C3 | Ambang mulai bersih-bersih | — **(pertanyaan [PENENTU] yang tidak terjawab)** |
| C4 | Alat | Bambu, "belung" *(sebut ulang untuk konfirmasi ejaan dan artinya)* |
| C5 | Pernah telat lalu jadi masalah | **Belum pernah ada masalah berarti** akibat penumpukan sampah |

Aturan operasi yang keluar spontan, bukan jawaban pertanyaan langsung:

- Ada sampah di pintu → pintu **harus segera dibuka**
- Air naik di hulu → pintu **harus dibuka**
- Hujan dengan curah tinggi → **segera buka pintu**

Ketiganya konsisten: membuka pintu adalah respons tunggal untuk semua kondisi.
Artinya keputusan yang bisa dibantu sistem ini hanya satu — **kapan**, bukan **apa**.

### D. Pencatatan & data

| Kode | Pertanyaan | Jawaban |
|---|---|---|
| D1 | Buku catatan harian | **Tidak ada** |
| D2 | Alat ukur di lokasi | Ada **pengukur tinggi air** dan ada **pengukur curah hujan**. Apakah pembacaannya dicatat, dan ke mana, belum ditanyakan |
| D3–D5 | Riwayat catatan | Tidak berlaku — tidak ada catatan |

### E. Pola & musim

| Kode | Pertanyaan | Jawaban |
|---|---|---|
| E1 | Musim tersibuk | **Musim hujan**, karena air membawa sampah dari hulu |
| E2 | Jeda hujan → sampah tiba | — |
| E4 | Asal sampah | **Dari hulu**, bukan dari sekitar bendungan |

### F. Banjir

| Kode | Pertanyaan | Jawaban |
|---|---|---|
| F1 | Banjir terakhir | **2 tahun lalu** (≈ 2024 — konfirmasi bulannya) |
| F2 | Penyebab menurut operator | **Hulu mengirim terlalu banyak sampah, lalu tersumbat di sini** |
| F4 | Waktu naik air normal → bahaya | — |

`F2` dijawab **tanpa dipancing**. Panduan §3.F menandai justru itu sebagai bukti
terkuat yang bisa didapat dari satu wawancara: operator sendiri yang menyebut sampah
sebagai penyebab banjir, bukan pewawancara yang menyodorkannya.

### G. Kebutuhan operator — blok paling menentukan

| Kode | Pertanyaan | Jawaban |
|---|---|---|
| G1 | Alat pemantau jarak jauh berguna? | **"Tidak berguna"** — alasannya operator selalu datang sendiri ke bendungan |
| G2 | Informasi yang paling dibutuhkan | **Debit air** |
| G3 | Kanal penyampaian | **WhatsApp** |
| G4 | Ambang bertindak versi operator | — **(pertanyaan [PENENTU] yang tidak terjawab)** |

### H. Lokasi

| Kode | Pertanyaan | Jawaban |
|---|---|---|
| H3 | CCTV eksisting | **Ada**, dipantau dari dinas |
| H1, H2, H4, H5 | Izin, listrik, sinyal, titik pasang | — |

---

## 2. Tiga hal yang berubah karena wawancara ini

### 2.1 Keluaran utama sistem adalah debit, bukan fraksi sampah

`G2` menjawab pertanyaan yang selama ini dijawab sendiri oleh proyek. Operator tidak
meminta angka penyumbatan; yang diminta **debit air**. Fraksi tutupan sampah dari
kamera tetap dibutuhkan, tapi posisinya berpindah: dari *produk akhir* menjadi
*masukan* untuk menghitung debit.

Rantai perhitungannya sudah ada dan tidak perlu dirombak:
`accumulation_frac` → `blockage_factor` → `discharge_m3s`, di
[`src/physics.py`](../src/physics.py).

Padanan TypeScript-nya (`web/lib/fisika.ts`, yang menghitung `dischargeBersih`
dan `dischargeTersumbat`) **sudah dihapus** bersama kartu "Perkiraan kenaikan
muka air" pada 2026-08-27. Jadi sekarang debit tidak muncul di layar operator
sama sekali — padahal `G2` menyebutnya satu-satunya angka yang paling
dibutuhkan. Menampilkannya kembali berarti menarik hasil `src/physics.py` ke
dasbor, bukan menghidupkan lagi kartu afflux yang lama.

### 2.2 Kanal WhatsApp belum ada, dan itu satu-satunya kanal yang diminta

`G3` menjawab WhatsApp. Yang terpasang sekarang: rail notifikasi di dalam dashboard
([`web/lib/notifikasi.ts`](../web/lib/notifikasi.ts)) dan SMS lewat SIM800L di
firmware. Keduanya bukan WhatsApp. Ini celah nyata antara yang dibangun dan yang
diminta — bukan penyempurnaan, melainkan syarat agar alat ini dipakai sama sekali.

### 2.3 "Alat tidak berguna" harus dijawab, bukan diabaikan

`G1` adalah penolakan langsung terhadap premis pemantauan jarak jauh, dan alasannya
masuk akal: operator memang selalu datang, dan `A6` mengonfirmasi malam pun dijaga
penuh. Justifikasi "tidak ada yang memantau jam dua pagi" yang dibayangkan panduan
§3.A6 **gugur di lokasi ini**.

Yang tersisa sebagai nilai sistem — semuanya didukung jawaban lain di wawancara yang
sama, bukan karangan:

1. **Melihat hulu sebelum sampai lokasi.** `E4` dan `F2`: masalahnya datang dari
   hulu. Kehadiran di pintu tidak memberi tahu apa yang sedang dikirim hulu.
2. **Menjadi buku catatan yang tidak pernah ada.** `D1`: tidak ada catatan harian.
   Semua yang dijawab "dulu" dan "2 tahun lalu" tidak punya angka pendukung justru
   karena ini. Sistem yang mencatat sendiri mengubah ingatan menjadi data.
3. **Angka, bukan penilaian mata.** `A5` menyebut pemicu kualitatif; debit terhitung
   memberi ukuran yang bisa dibawa ke dinas.

Klaim "menggantikan kehadiran operator" harus dihapus dari proposal. Narasumbernya
sendiri sudah menolaknya.

---

## 3. Kontradiksi yang belum selesai

| Yang bertentangan | Kenapa penting |
|---|---|
| `C5` "belum pernah ada masalah berarti akibat sampah" **vs** `F2` "banjir 2 tahun lalu karena sampah dari hulu menyumbat" | Ini persis pertanyaan Jalur A vs Jalur B. Kemungkinan besar keduanya benar dengan lingkup berbeda: sampah harian tidak pernah jadi masalah, satu kejadian ekstrem iya. Perlu ditanyakan ulang secara eksplisit |
| `B1` "pintu pernah susah dibuka" bercampur dua sebab: **alat rusak** dan **sampah** | Kalau penyebab dominannya kerusakan mekanis, sebagian bukti untuk hipotesis penyumbatan hilang. Harus dipisahkan |
| `A5` "kebutuhan panitia" | Istilahnya belum jelas — panitia apa, dan pintu ini melayani siapa (irigasi, drainase kota, atau keduanya). Bisa mengubah pemahaman fungsi bendungan |

---

## 4. Yang wajib dibawa pulang dari kunjungan kedua

Diurutkan menurut dampaknya ke proyek, bukan menurut urutan wawancara.

1. **`G4` — berapa banyak sampah yang membuat Bapak turun tangan.** Ambang versi
   manusia, pembanding untuk `blockage.area_threshold`. Belum terjawab
2. **`C3` — dari mana tahu sudah waktunya dibersihkan.** Belum terjawab
3. **`B2`, `B3` — tanggal dan frekuensi kejadian.** Tanpa ini tidak ada satu pun
   studi kasus yang bisa dicocokkan dengan curah hujan BMKG
4. **Kontradiksi `C5` vs `F2`** — tanyakan langsung, dengan kalimat netral
5. **`D2` lanjutan** — pembacaan pengukur tinggi air dan curah hujan dicatat atau
   tidak, dan bisa diakses tidak. Dua alat ini pembanding kalibrasi yang sudah
   berdiri di lokasi; kalau ada catatannya, itu data validasi gratis
6. **`H3` lanjutan** — rekaman CCTV dinas bisa diminta tidak, dan disimpan berapa
   lama. Rekaman lama berpotensi memuat kejadian penyumbatan yang sudah lewat
7. **`B8`** — titik penumpukan ditunjuk dan difoto, untuk polygon `structure`
8. **`A2` lanjutan** — jumlah dan lebar bukaan tiap kategori pintu, dengan meteran.
   Angka ini masuk langsung ke `configs/site_geometry.json`
9. **`F4`, `E2`** — waktu naik air dan jeda hujan→sampah, untuk menentukan berapa
   lama peringatan harus tersedia
10. **Tanggal, nama, jabatan, kontak narasumber**
11. **`H1`, `H2`, `H4`** — izin, listrik, sinyal, titik pasang kamera

---

## 5. Keputusan jalur

**Belum bisa diputuskan dari wawancara ini saja.** Panduan §4 memakai `B1` dan `B3`
sebagai penentu: `B1` terjawab "pernah, tapi dulu" dengan sebab bercampur, dan `B3`
tidak terjawab sama sekali.

Bukti condong ke **Jalur A (peringatan dini penyumbatan)** karena `F2` — operator
menyebut sampah sebagai penyebab banjir tanpa dipancing, dan itu bukti yang jauh
lebih kuat daripada jawaban terpandu. Tapi `C5` menariknya ke arah sebaliknya.

Panduan §4 sudah menyiapkan jalannya: jangan putuskan dari satu narasumber. Sumber
kedua yang paling mungkin sudah teridentifikasi di wawancara ini juga — **dinas yang
memantau CCTV** (`H3`), yang kemungkinan punya rekaman dan catatan yang tidak
dimiliki operator.

Sampai itu selesai, kerjakan yang tidak bergantung pada keputusan jalur: rantai debit
sudah ada dan diminta secara eksplisit (`G2`), jadi menonjolkannya di dashboard aman
dikerjakan sekarang apa pun jalur yang nanti dipilih.
