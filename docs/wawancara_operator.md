# Panduan wawancara operator pintu air

Satu jam bersama orang yang menjaga pintu air menentukan arah seluruh penelitian:
apakah proyek ini tentang **peringatan dini penyumbatan**, atau tentang
**pemantauan aliran sampah**. Jangan menganotasi 400 frame sebelum pertanyaan itu
terjawab.

Versi web untuk dibuka di HP saat di lokasi:
<https://claude.ai/code/artifact/94e6fe06-d406-4936-9e73-f36a8bfca277>

Bagian dari [`rencana_penelitian.md`](rencana_penelitian.md) Fase 0.

---

## Yang sedang diputuskan

Hipotesis proyek: sampah menumpuk di depan pintu air, mengurangi luas bukaan, muka
air hulu naik, dan itu berkontribusi pada banjir. Rantai fisikanya sahih —
`h ∝ 1/A²`, sehingga penyumbatan 30 % saja sudah melipatduakan head yang
dibutuhkan. Yang **belum terbukti** adalah apakah rantai itu benar-benar berjalan di
lokasi ini.

Operator satu-satunya orang yang punya jawabannya, karena dialah yang menyaksikannya
bertahun-tahun. Enam pertanyaan bertanda **[PENENTU]** mengubah arah proyek; sisanya
memperkaya, tapi tidak mengubah keputusan.

---

## 1. Sebelum berangkat

- [ ] **Surat pengantar sekolah** — pintu air umumnya aset pemerintah
- [ ] **Buku catatan fisik** — menulis di depan narasumber menunjukkan keseriusan
- [ ] **Perekam suara** — minta izin dulu; kalau ditolak jangan dipaksa
- [ ] **Kamera atau HP** — memotret pintu, logbook, titik penumpukan
- [ ] **Meteran** — ukur lebar dan jumlah bukaan pintu
- [ ] **Waktu minimal satu jam** — jawaban terbaik keluar setelah 20 menit pertama
- [ ] **Datang saat tidak sibuk** — hindari saat hujan atau pintu sedang dioperasikan

---

## 2. Cara bertanya

Empat yang pertama adalah beda antara data yang bisa dipakai dan kesan yang tidak
bisa diverifikasi.

1. **Tanya "kapan terakhir", bukan "sering tidak".** "Sering" itu relatif dan kabur.
   Tanggal kejadian bisa dicocokkan dengan data hujan BMKG — langsung jadi studi
   kasus di proposal.
2. **Minta cerita, bukan kesimpulan.** "Coba ceritakan kejadiannya, Pak" menghasilkan
   detail. "Apakah sering bermasalah?" hanya menghasilkan ya atau tidak.
3. **Jangan mengarahkan.** "Pasti sering macet ya, Pak?" membuat narasumber
   mengiyakan demi sopan santun. Netralkan: "Bagaimana kondisinya kalau musim hujan?"
4. **Diam setelah bertanya.** Jawaban paling berharga sering muncul setelah tiga
   detik hening.
5. **Pakai bahasa sehari-hari.** Jangan sebut "blockage", "segmentasi", atau "deep
   learning". Katakan "sampah numpuk", "kamera", "alat pemantau".
6. **Minta ditunjukkan langsung**, lalu foto. Satu foto lokasi menggantikan puluhan
   kalimat catatan.

---

## 3. Daftar pertanyaan

Kode pertanyaan dipakai supaya mudah dirujuk saat mencatat. Urutan blok dari ringan
ke inti — jangan langsung ke blok B sebelum suasana cair.

### A. Perkenalan & operasi harian

- **A1.** Sudah berapa lama Bapak bertugas di pintu air ini?
- **A2.** Pintunya ada berapa? Yang biasa dioperasikan yang mana saja?
- **A3.** Dalam seminggu, biasanya pintu dibuka-tutup berapa kali?
- **A4.** Yang memutuskan kapan pintu dibuka siapa — Bapak sendiri atau perintah kantor?
- **A5.** Kalau memutuskan buka pintu, dasarnya apa? Bapak lihat apa dulu?
  > "Lihat tinggi air" berarti sudah ada ukuran. "Lihat kondisi" berarti keputusannya
  > berbasis penilaian mata — di situlah sistem ini masuk.
- **A6.** Ada penjagaan malam tidak? Kalau hujan deras jam dua-tiga pagi, siapa yang memantau?
  > Jawaban "tidak ada" langsung jadi justifikasi pemantauan otomatis 24 jam.

### B. Kejadian sampah

Blok inti. Menentukan apakah proyek berjudul "peringatan dini penyumbatan" atau bukan.

- **B1. [PENENTU]** Pernah tidak pintunya jadi susah dibuka atau ditutup gara-gara sampah?
- **B2. [PENENTU]** Kalau pernah, kapan terakhir? Coba ceritakan waktu itu bagaimana.
  > Catat tanggal, atau minimal bulan dan tahun.
- **B3. [PENENTU]** Dalam setahun kira-kira berapa kali kejadian seperti itu?
- **B4.** Berapa lama sampai kembali normal? Siapa saja yang turun tangan?
- **B5.** Pernah sampai pintunya tidak bisa ditutup sama sekali?
  > Skenario terburuk — pelepasan air tak terkendali. Kalau pernah, gali sedetail mungkin.
- **B6.** Sampah yang paling merepotkan jenisnya apa?
- **B7.** Pernah ada yang besar-besar? Batang pohon, kasur, jerigen?
  > Benda besar sering jadi "jangkar" yang lalu menjaring sampah kecil.
- **B8.** Sampahnya menumpuk di bagian mana? Boleh minta tolong ditunjukkan?
  > Foto titik ini — inilah polygon `structure` di `site_bendungan.yaml`.

### C. Pembersihan

- **C1.** Yang membersihkan siapa? Berapa orang?
- **C2.** Seberapa sering? Ada jadwal rutin, atau kalau sudah banyak saja?
- **C3. [PENENTU]** Bapak tahu dari mana kalau sudah waktunya dibersihkan? Ukurannya apa?
  > Kalau jawabannya "dilihat saja" atau "perasaan", itu kutipan paling berharga dari
  > seluruh wawancara. Catat kata persisnya.
- **C4.** Sekali bersih-bersih makan waktu berapa lama? Pakai alat apa?
- **C5.** Pernah telat membersihkan lalu jadi masalah?

### D. Pencatatan & data

- **D1. [PENENTU]** Ada buku catatan harian tidak? Boleh saya lihat sebentar?
  > Kalau boleh, foto beberapa halaman.
- **D2.** Tinggi muka air dicatat tidak? Berapa kali sehari?
  > Pembanding untuk sensor level dan garis air dari kamera.
- **D3.** Kejadian sampah ikut dicatat, atau hanya diingat?
- **D4.** Catatan lama masih ada? Sampai berapa tahun ke belakang?
- **D5.** Untuk penelitian sekolah, boleh minta salinan datanya? Prosedurnya bagaimana?
  > Tanyakan kantor yang berwenang — biasanya Dinas PU atau Balai Besar Wilayah Sungai.

### E. Pola & musim

- **E1.** Musim apa yang paling banyak sampahnya?
- **E2.** Setelah hujan deras, berapa lama sampai sampahnya sampai ke sini?
  > Tebakan awal untuk `τ*` di `rencana_penelitian.md` §5.14.
- **E3.** Ada bedanya antara pagi dan sore?
- **E4.** Sampahnya datang dari mana? Pasar, permukiman, atau industri?
- **E5.** Dibanding lima tahun lalu, lebih banyak atau lebih sedikit?

### F. Banjir

- **F1.** Kapan terakhir di sini banjir?
- **F2.** Menurut Bapak penyebabnya apa?
  > Jangan sebut sampah lebih dulu. Kalau operator menyebutnya sendiri tanpa
  > dipancing, itu bukti jauh lebih kuat.
- **F3.** Sampah pernah jadi penyebabnya?
- **F4.** Kalau air mulai naik, berapa lama dari normal sampai betul-betul bahaya?
  > Menetapkan berapa lama waktu peringatan yang harus disediakan sistem.

### G. Kebutuhan mereka

- **G1.** Kalau ada alat yang memberi tahu kondisi sampah tanpa Bapak datang ke sini,
  berguna tidak?
- **G2.** Informasi apa yang paling Bapak butuhkan?
- **G3.** Enaknya diberi tahu lewat apa — HP/WhatsApp, layar di pos, atau alarm?
- **G4. [PENENTU]** Sampah seberapa banyak yang bikin Bapak harus turun tangan?
  > Ambang versi manusia. Bandingkan dengan `blockage.area_threshold`. Kalau
  > berdekatan, itu validasi kuat; kalau jauh, salah satunya perlu ditinjau.

### H. Izin & teknis lokasi

- **H1.** Kalau mau pasang kamera untuk penelitian, izinnya ke siapa?
- **H2.** Ada listrik yang bisa dipakai? Ada sinyal internet atau WiFi?
- **H3.** Sudah ada CCTV belum? Rekamannya bisa diakses?
  > CCTV yang sudah ada bisa memangkas seluruh tahap pemasangan — dan mungkin
  > menyimpan rekaman lama berisi kejadian penyumbatan.
- **H4.** Titik mana yang aman untuk kamera dan pandangannya bagus ke arah pintu?
- **H5.** Pernah ada kehilangan barang atau alat di sini?

---

## 4. Setelah wawancara: dua jalur

Baca ulang jawaban `B1`, `B3`, `C3`.

### Jalur A — Penyumbatan terbukti
*Kalau B1 = pernah dan B3 ≥ 1 kali per tahun.*

- Framing tetap: **peringatan dini penyumbatan**
- Kumpulkan tanggal semua kejadian, cocokkan dengan curah hujan BMKG hari itu
- Setiap kejadian jadi satu studi kasus
- Prioritaskan anotasi frame kondisi ekstrem
- Metrik utama: `accumulation_frac` dan `growth_per_min`

### Jalur B — Pemantauan aliran sampah
*Kalau B1 = tidak pernah.*

- Framing bergeser: **kuantifikasi beban sampah dan kaitannya dengan curah hujan**
- Tetap layak OPSI — data seperti ini belum ada untuk sungai ini
- Metrik utama: `coverage` per satuan waktu, pola musiman
- Pembanding literatur berpindah ke studi pemantauan plastik sungai (van Lieshout
  dkk., 2020), bukan studi penyumbatan gorong-gorong
- Sensor tinggi air jadi konteks hidrologi, bukan variabel yang diprediksi

### Kalau jawaban ragu atau tidak konsisten

Jangan putuskan dari satu narasumber. Cari sumber kedua: petugas shift lain, atasan,
atau Dinas PU / Balai Besar Wilayah Sungai. Menunda satu minggu jauh lebih murah
daripada menganotasi ratusan frame untuk pertanyaan yang salah.

---

## 5. Yang harus dibawa pulang

- [ ] Nama lengkap dan jabatan narasumber — untuk daftar pustaka
- [ ] Nomor kontak — pasti ada yang perlu dikonfirmasi belakangan
- [ ] Foto buku catatan atau logbook
- [ ] Foto pintu air dari minimal tiga sudut, termasuk dari posisi kamera rencana
- [ ] Foto kondisi sampah hari itu
- [ ] Foto titik penumpukan yang ditunjuk operator (jawaban `B8`)
- [ ] Jumlah dan lebar bukaan pintu — angka, bukan perkiraan
- [ ] Izin lisan atau tertulis memasang kamera, beserta nama pihak berwenang
- [ ] Sketsa denah: arah aliran, posisi pintu, posisi kamera, **arah matahari**

> **Arah matahari mudah terlupakan.** Air tenang di hulu bendungan memantul seperti
> cermin, dan silau adalah penyebab kesalahan model nomor satu di lokasi seperti ini
> (`annotation_guideline.md` §2.2). Catat jam berapa matahari menghadap kamera.

---

## 6. Lembar catatan ringkas

Isi di tempat. Ingatan tentang angka memudar dalam hitungan jam.

| Butir | Isian |
|---|---|
| Tanggal & jam wawancara | |
| Nama & jabatan narasumber | |
| Lama bertugas `A1` | |
| Jumlah pintu `A2` | |
| Ada jaga malam? `A6` | |
| **Pernah pintu macet karena sampah?** `B1` | |
| **Kejadian terakhir (tanggal/bulan)** `B2` | |
| **Frekuensi per tahun** `B3` | |
| Dasar memutuskan bersih-bersih `C3` | |
| Ada logbook? `D1` | |
| Jeda hujan → sampah datang `E2` | |
| Ambang bertindak versi operator `G4` | |
| Ada listrik / internet? `H2` | |
| Ada CCTV eksisting? `H3` | |
| Jalur yang diambil (A / B / perlu sumber kedua) | |

---

Kutipan narasumber jauh lebih kuat daripada argumen penulis. Kalau operator
mengatakan sesuatu yang tepat sasaran — terutama pada `C3` dan `G4` — catat
kalimatnya persis apa adanya, lalu minta izin mengutipnya di laporan.
