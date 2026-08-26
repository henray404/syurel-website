# PRD — Web Pemantauan Pintu Air

Tanggal: 2026-08-23 · Status: sebagian terbangun

Dokumen ini menjawab **apa yang dibangun, untuk siapa, dan kapan disebut
berhasil**. Cara membangunnya ada di dokumen terpisah:

- Desain teknis: [`superpowers/specs/2026-08-20-monitoring-web-design.md`](superpowers/specs/2026-08-20-monitoring-web-design.md)
- Rencana implementasi: [`superpowers/plans/2026-08-23-monitoring-web.md`](superpowers/plans/2026-08-23-monitoring-web.md)
- Konteks penelitian: [`rencana_penelitian.md`](rencana_penelitian.md)

**Penandaan angka** dipakai konsisten seperti di seluruh dokumen proyek:
`[UKUR]` hasil pengukuran nyata · `[LIT]` dari literatur · `[TEBAK]` penalaran
yang belum dikalibrasi.

---

## 1. Masalah

Sistem ini sudah menghasilkan data, tetapi **tidak ada tempat data itu
bertemu**.

Sensor ESP32 mencatat tinggi air dan curah hujan ke kartu SD tiap menit.
Inferensi kamera menulis 20 kolom metrik ke `out/timeseries.sqlite`. Keduanya
berjalan, keduanya benar, dan keduanya terpisah. Tidak ada satu pun tampilan
yang menyatukan keduanya.

Akibatnya tiga hal yang sudah mungkin secara teknis tetap tidak bisa dilakukan:

1. Operator tidak bisa melihat kondisi terkini tanpa datang ke lokasi.
2. Hubungan hujan → tinggi air → penumpukan tidak bisa diperiksa, padahal itu
   inti klaim ilmiah proyek ini.
3. Sistemnya tidak bisa ditunjukkan ke siapa pun — tidak ada yang bisa dibuka.

### Masalah yang lebih mendesak dari ketiganya

**Firmware ESP32 sudah menunggu server yang belum ada.**

`firmware/esp32/include/hw_upload.h` mengirim POST ke `INGEST_URL` dan hanya
memajukan kursor SD-nya setelah server membalas 2xx. Selama endpoint itu tidak
ada, ESP menumpuk baris di kartu tanpa pernah menyelesaikan pengiriman.

Ini menaikkan proyek dari "dashboard" menjadi subsistem: web ini **wajib**
punya sisi penerima, bukan hanya penampil.

---

## 2. Pengguna

Tiga pembaca dengan kebutuhan berbeda, satu aplikasi.

### Operator pintu air — halaman `/`

Melihat sekilas saat bertugas, sering dari jarak beberapa meter, kadang dalam
kondisi tergesa. Yang dibutuhkan bukan data, tapi **keputusan**: aman membuka
pintu, atau bersihkan dulu.

Kebutuhannya sempit dan tegas: angka besar, warna jelas, satu kalimat
kesimpulan, tanpa grafik.

### Peneliti (kamu) — halaman `/analisis`

Mengolah data untuk OPSI. Butuh deret waktu, hubungan antar-variabel, dan
ekspor. Historis jauh lebih penting daripada kondisi terkini.

### Juri dan penonton — halaman `/demo`

Dibuka saat sidang atau pameran. Harus meyakinkan dalam 30 detik, dengan alur
cerita: foto mentah → mask → angka → keputusan.

---

## 3. Ruang lingkup

### Yang dibangun

| # | Kemampuan | Untuk siapa | Status |
|---|---|---|---|
| F1 | Menerima dan menyimpan data ESP32 | sistem | ✅ selesai |
| F2 | Membaca hasil inferensi kamera | sistem | ✅ selesai |
| F3 | Menggabungkan keduanya pada sumbu waktu | sistem | ✅ selesai |
| F4 | Menyimpulkan status operasi | operator | ⏳ sedang dikerjakan |
| F5 | Halaman kondisi terkini | operator | ⏳ sedang dikerjakan |
| F6 | Grafik deret waktu | peneliti | ❌ rencana terpisah |
| F7 | Uji hubungan `h ∝ 1/A²` | peneliti | ❌ rencana terpisah |
| F8 | Ekspor CSV | peneliti | ❌ rencana terpisah |
| F9 | Halaman presentasi | juri | ❌ rencana terpisah |

### Yang sengaja tidak dibangun

| tidak dibangun | alasan |
|---|---|
| Autentikasi | jalan di laptop, jaringan lokal |
| Penempatan di Raspberry Pi | menunggu jawaban `H2` wawancara — listrik dan internet di lokasi |
| Peringatan WhatsApp/SMS | firmware sudah punya jalur SMS sendiri |
| Streaming video langsung | inferensi menulis metrik, bukan video |
| Dukungan banyak lokasi | satu bendungan |
| Menjalankan model dari web | GUI Gradio sudah melayani itu |

---

## 4. Persyaratan

### F1 — Menerima data ESP32 ✅

Endpoint `POST /api/ingest` menerima kiriman batch dari firmware.

**Aturan yang tidak boleh dilanggar**, karena firmware bergantung padanya:

- Balas **2xx hanya jika semua baris tersimpan**. Balasan 2xx membuat ESP
  memajukan kursor dan baris itu tidak akan dikirim ulang selamanya.
- Balas **non-2xx pada kegagalan apa pun**. ESP akan mengirim ulang — itu
  perilaku yang diinginkan, bukan masalah.
- **Idempoten.** Pengiriman ulang adalah kejadian normal (mati listrik saat
  menulis kursor, respons hilang di jaringan).
- **Satu baris cacat menolak seluruh batch.** Menerima sebagian lalu membalas
  2xx akan membuang baris yang gagal secara permanen.

**Terverifikasi** `[UKUR]` terhadap server yang berjalan: kiriman pertama
`inserted:1` HTTP 200; kiriman ulang `inserted:0` HTTP 200; baris pendek
HTTP 400.

### F2 — Membaca hasil kamera ✅

Membaca tabel `observations` yang ditulis `src/inference/sink.py`. Web **tidak
pernah menulis** tabel itu.

Database dibuka dalam mode WAL supaya pembacaan dari web tidak memblokir
penulisan inferensi.

### F3 — Penggabungan waktu ✅

ESP mencatat tiap menit, kamera tiap 30 detik, dan jam keduanya tidak
tersinkron. Pencocokan cap waktu persis akan membuang hampir semua pasangan,
jadi penggabungan memakai jendela toleransi ±60 detik.

Baris ESP tanpa pasangan kamera **tetap disimpan**: tinggi air dan curah hujan
tetap pengukuran nyata ketika kamera mati, dan membuangnya akan melubangi deret
hujan.

### F4 — Kesimpulan status ⏳

Empat keadaan:

| keadaan | kapan | yang dikatakan |
|---|---|---|
| `unknown` | penumpukan tidak terukur | "Belum ada pengukuran" |
| `clear` | di bawah ambang, tidak naik | "Aman membuka pintu" |
| `watch` | di bawah ambang tapi naik | "Penumpukan sedang bertambah" + perkiraan waktu |
| `blocked` | mencapai ambang, atau alarm menyala | "Bersihkan dulu sebelum membuka pintu" |

Ambang `0.18` `[TEBAK]` — diturunkan dari penalaran fisik di
`configs/inference/site_bendungan.yaml`, belum dikalibrasi data.

**Logika ini dipisah dari tampilan.** Alasannya bukan kerapian: rancangan
visual dikerjakan terpisah di Claude Design, dan pemisahan ini memastikan
mengubah tampilan **tidak bisa** diam-diam mengubah apa yang dikatakan kepada
operator.

### F5 — Halaman operator ⏳

Menampilkan tinggi air, curah hujan, persentase penumpukan, dan kesimpulan F4.
Menyegarkan tiap 30 detik.

---

## 5. Aturan yang tidak boleh dilanggar

Dua hal yang jika salah membuat sistem ini berbahaya, bukan sekadar kurang
baik.

### Nilai yang tidak terukur tidak boleh ditampilkan sebagai nol

`src/inference/metrics.py` sengaja mengembalikan `None`, bukan `0.0`, dengan
alasan yang tertulis di sana: nilai `0.0` terbaca **"sungai bersih"**, dan itu
justru salah fatal saat banjir.

Web harus menampilkan "tidak terukur". Menampilkan 0 akan mengulang persis
kesalahan yang sudah dicegah di sisi Python.

### Waktu selalu UTC

`ts_utc` ISO-8601 UTC di kedua sumber. Asia/Jakarta adalah UTC+7 — memakai
waktu lokal akan menggeser korelasi dengan data hujan **tujuh jam tanpa
ketahuan**.

---

## 6. Ukuran keberhasilan

Bukan target performa, melainkan pertanyaan yang harus bisa dijawab.

| # | Pertanyaan | Terpenuhi bila |
|---|---|---|
| S1 | Apakah data ESP sampai dan tersimpan? | ESP mengirim, kursor SD maju, baris ada di database |
| S2 | Apakah pengiriman ulang aman? | Batch yang sama dua kali tidak menambah baris |
| S3 | Apakah kegagalan aman? | Batch cacat ditolak, ESP mengirim ulang, tidak ada data hilang |
| S4 | Apakah operator tahu harus berbuat apa? | Satu kalimat yang bisa ditindak, bukan sekumpulan angka |
| S5 | Apakah data yang hilang terlihat sebagai hilang? | "tidak terukur", tidak pernah 0 |
| S6 | Apakah dua sumber bisa dibandingkan? | Tergabung pada sumbu waktu yang sama |

S1–S3, S5, S6 sudah terpenuhi `[UKUR]`. S4 menunggu F4–F5.

---

## 7. Yang sudah terbangun

Per 2026-08-23, lima dari delapan tahap rencana implementasi selesai:

| tahap | isi |
|---|---|
| 1 | Mode WAL pada penulis Python |
| 2 | Kerangka Next.js + modul database |
| 3 | Parser CSV ESP32 |
| 4 | **Endpoint ingest** — terverifikasi ujung ke ujung |
| 5 | Penggabungan deret waktu |

**41 pengujian lolos** `[UKUR]` — 21 Python, 20 TypeScript.

Tersisa: penyimpulan status, halaman operator, penyelarasan `INGEST_URL`
firmware.

---

## 8. Risiko

| risiko | dampak | penanganan |
|---|---|---|
| **Balasan 2xx pada penyimpanan yang gagal** | data ESP hilang permanen | diuji khusus; batch diparsing seluruhnya sebelum menyentuh database |
| **Data lokasi belum ada** | halaman kosong; `/demo` paling terdampak | dapat diisi data uji; tidak menghalangi pembangunan |
| **Ambang belum dikalibrasi** | status operasi bisa terlalu peka atau tumpul | ditandai `[TEBAK]`; kalibrasi menunggu data semusim |
| **Ketidakcocokan port dan path** | firmware tidak menemukan server | diselaraskan pada tahap terakhir rencana |
| **Model untuk Raspberry Pi** | belum tentu muat di perangkat sasaran | pertanyaan Fase 4, bukan penghalang web; `bench.cost` harus dijalankan di Pi sebelum mengunci pilihan |

---

## 9. Rancangan visual

Dikerjakan terpisah di Claude Design. Markup halaman operator sengaja dibuat
polos: yang menentukan **apa** yang dikatakan adalah modul kesimpulan, bukan
halaman — sehingga penataan ulang tampilan tidak dapat mengubah isi pesan.
