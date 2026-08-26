# Survei Lapangan — Daftar Ambil Data

Dibuat 2026-08-26 untuk kunjungan **terakhir**. Diurutkan menurut seberapa
banyak pekerjaan yang tertahan tanpanya, bukan menurut seberapa mudah.

Buka ini di HP saat di lokasi. Centang sambil jalan.

---

## Aturan hari ini

**Satu hari data deret waktu tidak menghasilkan model peramalan apa pun** —
alasannya di [`prediksi_banjir.md`](prediksi_banjir.md) §4. Jadi jangan habiskan
hari untuk merekam angka berjam-jam.

Yang **benar-benar** membuka banyak pekerjaan hanya lima hal, dan semuanya bisa
selesai dalam beberapa jam:

1. Ukuran pintu air (meteran)
2. Titik pasang sensor + jarak ke dasar
3. Koordinat GPS
4. Video/foto untuk data latih
5. Wawancara operator

Empat dari lima itu diukur sekali dan berlaku selamanya.

---

## Bawa

- [ ] Meteran gulung ≥5 m (**yang paling penting**)
- [ ] Meteran laser kalau ada
- [ ] HP — GPS, kamera, perekam suara
- [ ] Kamera Insta360 Link + laptop, atau HP untuk video
- [ ] **Pelat/benda berukuran diketahui** — kardus/tripleks ukuran persis, untuk kalibrasi kamera
- [ ] Spidol permanen + lakban, untuk menandai titik ukur
- [ ] Buku catatan (baterai HP bisa habis)
- [ ] Payung/pelindung hujan untuk alat
- [ ] Surat izin / kontak operator

**Tidak perlu dibawa:** ESP32 rakitan lengkap. Ultrasonik masih rusak
([`laporan/08-protokol-uji.md`](laporan/08-protokol-uji.md) §8.6), dan
memperbaikinya di tepi sungai adalah cara terburuk menghabiskan hari terakhir.

---

## 1. Geometri pintu air — PRIORITAS TERTINGGI

**Kenapa duluan:** setiap keluaran fisika sekarang `[ASUMSI]`. Lima angka di
bawah mengubah seluruhnya jadi `[TERUKUR]` dalam 15 menit kerja. Tidak ada
tindakan lain hari ini yang mengubah sebanyak ini.

Isikan ke `configs/site_geometry.json`:

| Kunci | Yang diukur | Nilai tebakan sekarang | Hasil ukur |
|---|---|---|---|
| `b_m` | **Lebar bukaan pintu**, sisi dalam ke sisi dalam | 2,0 m | ______ |
| `a_m` | **Tinggi bukaan** saat pintu dibuka normal (tanya operator) | 1,0 m | ______ |
| `h_bersih_m` | **Tinggi muka air hulu di atas bukaan saat pintu bersih** | 0,8 m | ______ |
| `z_jalan_m` | **Tinggi muka air saat jalan mulai tergenang**, dari datum yang sama | 1,6 m | ______ |

**`h_bersih_m` dan `z_jalan_m` wajib dari datum yang sama.** Ini kesalahan
paling mudah terjadi dan paling merusak: kalau satu diukur dari dasar sungai dan
satunya dari permukaan jalan, `critical_bf` jadi omong kosong.

Cara aman: pilih **satu titik acuan tetap** yang tidak akan hilang — misalnya
bagian atas ambang beton pintu. Tandai dengan spidol. Ukur semuanya dari situ,
catat mana yang di atas dan mana yang di bawah acuan.

- [ ] `b_m` = ______ m
- [ ] `a_m` = ______ m (bukaan normal menurut operator: ______)
- [ ] Titik acuan dipilih dan ditandai: ________________________
- [ ] `h_bersih_m` = ______ m dari acuan
- [ ] `z_jalan_m` = ______ m dari acuan
- [ ] **Foto tiap pengukuran dengan meteran terlihat di bingkai**

> `Cd = 0,61` tidak perlu diukur — nilai literatur USBR. Kalibrasi yang lebih
> baik datang dari eksperimen miniatur, bukan dari lapangan.

---

## 2. Titik pasang sensor

**Kenapa penting:** `JARAK_DASAR` di `firmware/esp32/include/config.h` sekarang
100 cm, tebakan. Salah di sini membuat **setiap** pembacaan tinggi air salah.

- [ ] Tentukan titik pasang ultrasonik. Syarat: menghadap **lurus ke bawah** ke
      permukaan air, tidak terhalang, ada tempat mengikat, aman dari orang lewat
- [ ] Ukur **jarak muka sensor ke dasar sungai** = ______ cm → ini `JARAK_DASAR`
- [ ] Ukur jarak muka sensor ke **permukaan air saat ini** = ______ cm
- [ ] Catat kedalaman air saat ini = ______ cm (untuk memeriksa silang)
- [ ] Foto titik pasang dari dua sudut

**Periksa zona buta.** JSN-SR04T tidak bisa mengukur lebih dekat dari ~25 cm.
`JARAK_DASAR` harus dipilih supaya ambang BAHAYA terlampaui **sebelum** air masuk
zona itu — kalau tidak, sensor buta tepat saat banjir.

- [ ] `JARAK_DASAR` − 25 cm = ______ cm. Apakah ini di atas ambang BAHAYA (60 cm)?
      Ya / Tidak → kalau Tidak, sensor harus dipasang lebih tinggi

**Titik pasang kamera:**

- [ ] Tentukan posisi kamera. Harus melihat **zona pintu** dengan jelas
- [ ] Foto pemandangan dari titik itu — nanti jadi acuan menggambar poligon ROI
      dan zona pintu
- [ ] Catat apakah ada listrik / WiFi terjangkau di situ

---

## 3. Koordinat — 2 menit, membuka dua API

`configs/site_geometry.json` bagian `site` semuanya masih `null`, dan itu yang
membuat pengambil curah hujan tidak bisa dipakai untuk lokasi ini.

- [ ] GPS HP, berdiri di pintu air: lat = __________ lon = __________
- [ ] Nama desa/kelurahan: ________________________
- [ ] Nama kecamatan: ________________________
- [ ] Nama kabupaten: ________________________

Kode `adm4` (format seperti `00.00.00.0000`) dicocokkan belakangan dari kode
wilayah Kemendagri — cukup catat nama administratifnya di lapangan.

---

## 4. Data latih — video dan foto

**Kenapa penting:** dataset `opsi` **kosong**. Model sekarang tidak pernah
melihat satu pun citra dari lokasi ini, dan itu batasan terbesarnya
([`laporan/06-model-ai.md`](laporan/06-model-ai.md) §6.8).

Yang dicari: keragaman, bukan durasi. **20 menit video dari 5 kondisi berbeda
jauh lebih berharga daripada 3 jam dari satu sudut.**

- [ ] Video dari **titik pasang kamera yang direncanakan**, ≥5 menit
- [ ] Video dari 2–3 sudut lain
- [ ] Foto saat **ada** penumpukan sampah di pintu
- [ ] Foto saat pintu **relatif bersih** (contoh negatif — sama pentingnya)
- [ ] Foto dari dekat: jenis sampah yang benar-benar ada di sini (sachet?
      styrofoam? eceng gondok? kayu?)
- [ ] Kalau memungkinkan, ulangi di **jam berbeda** — pagi dan siang punya
      pantulan dan bayangan yang sangat berbeda
- [ ] Kalau hujan: **rekam.** Citra saat hujan paling langka dan paling berharga

Catat untuk tiap rekaman: jam, cuaca, posisi pintu (buka/tutup).

---

## 5. Kalibrasi kamera (eksperimen E2) — kalau sempat

`kalibrasi_kamera.skala` dan `bias` masih identitas. Kesalahan kamera
**dikuadratkan** oleh `1/(1−BF)²` — kamera yang melapor 24% padahal 31% membuat
afflux 18% terlalu rendah.

Cara paling sederhana:

- [ ] Ukur pelat/kardus yang dibawa: ______ cm × ______ cm = ______ m²
- [ ] Apungkan di zona pintu, dalam bingkai kamera
- [ ] Rekam video ≥30 detik
- [ ] Catat jam persisnya: ______

Nanti di rumah: jalankan inferensi atas video itu, bandingkan
`accumulation_frac` yang dilaporkan dengan luas sebenarnya dibagi luas zona
pintu. Selisihnya masuk ke `skala`/`bias`.

---

## 6. Wawancara operator

Panduan lengkap sudah ada di [`wawancara_operator.md`](wawancara_operator.md),
bagian A–H. Rekam suaranya (minta izin dulu).

**Tiga pertanyaan yang paling menentukan, tanyakan meski waktunya mepet:**

**a) Waktu respons DAS — pertanyaan paling berharga hari ini.**
> "Kalau hujan deras di hulu sana, kira-kira berapa lama sampai air di sini
> mulai naik?"

Jawaban operator adalah **waktu respons DAS hasil pengamatan bertahun-tahun**,
dan itu **satu-satunya cara** proyek ini bisa menyebut angka lead time secara
sah ([`prediksi_banjir.md`](prediksi_banjir.md) §1). Tidak ada di sensor mana
pun. Gratis, dan cuma bisa didapat hari ini.

- [ ] Jawaban: ________________________________

**b) Riwayat banjir.**
> "Kapan terakhir jalan ini tergenang? Berapa kali setahun? Waktu itu airnya
> setinggi apa?"

Ini bahan ambang hujan empiris, dan satu-satunya validasi eksternal untuk
`z_jalan_m`.

- [ ] Jawaban: ________________________________

**c) Penyumbatan sampah.**
> "Pernah pintu sampai tersumbat sampah? Seberapa sering dibersihkan? Waktu
> tersumbat, airnya naik berapa?"

**Kalau operator menjawab "air naik sekian cm waktu tersumbat" — itu validasi
lapangan untuk seluruh rantai afflux.** Nilai jawabannya sangat tinggi; kejar
angkanya, jangan puas dengan "naik banyak".

- [ ] Jawaban: ________________________________

---

## 7. Foto untuk laporan (poin 9)

Daftar lengkap di [`laporan/09-dokumentasi-visual.md`](laporan/09-dokumentasi-visual.md)
§9.7 bagian E. Ringkasnya:

- [ ] Bendung gerak dari beberapa sudut
- [ ] Pintu air dari dekat, **dengan meteran untuk skala**
- [ ] Jalan yang tergenang saat banjir (titik acuan `z_jalan_m`)
- [ ] Penumpukan sampah kondisi sungguhan
- [ ] Foto lebar yang memperlihatkan hubungan sungai–pintu–jalan

---

## Setelah pulang — urutan mengolah

1. Isi `configs/site_geometry.json`, ubah `status` jadi `CALIBRATED` **hanya
   kalau seluruh kolom `_sumber` sudah berbunyi "ukur"**. Ada uji otomatis yang
   akan gagal kalau status dinaikkan tanpa itu — itu memang disengaja.
2. Ubah `JARAK_DASAR` di `firmware/esp32/include/config.h`.
3. Jalankan `.venv\Scripts\python.exe -m physics` — lihat `critical_bf` yang
   baru. **Angka itu ramalan utama proyek**, sekarang dari ukuran sungguhan.
4. Jalankan inferensi atas video lokasi, simpan pratinjau — ini contoh keluaran
   sungguhan pertama, pengganti gambar uji meja di laporan §9.4.
5. Anotasi sebagian bingkai video → dataset `opsi` → latih ulang.
6. Perbarui tabel status di `laporan/README.md`.

---

## Kalau waktunya cuma satu jam

Kerjakan **bagian 1 dan 3**, plus pertanyaan **6a**.

Lima angka ukuran + koordinat + waktu respons DAS. Itu saja sudah memindahkan
seluruh bab fisika dari tebakan ke terukur, dan memberi satu-satunya dasar sah
untuk menyebut lead time.
