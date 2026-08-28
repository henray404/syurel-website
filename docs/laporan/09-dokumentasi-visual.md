# 9. Dokumentasi Visual — Tangkapan Layar, Foto, Video

[← Daftar isi](README.md) · [← Sebelumnya: Protokol uji](08-protokol-uji.md)

---

Bagian ini **paling tipis** di seluruh laporan, dan itu ditulis terang-terangan
di sini alih-alih ditutup dengan gambar seadanya. Yang ada dicatat lengkap; yang
belum ada diberi daftar pengambilan agar bisa dilengkapi dalam satu sesi.

---

## 9.1 Aset visual yang sudah ada

`[TERUKUR]` — inventaris berkas per 2026-08-25.

| Berkas | Piksel | Ukuran | Dibuat | Isi |
|---|---|---|---|---|
| `image.png` | 2038×1092 | 2,5 MB | 2026-08-16 | **Foto lokasi sasaran** di dalam alat anotasi |
| `firmware/esp32/image.png` | 1297×1153 | 372 KB | 2026-08-23 | **Tabel pemasangan kabel** ESP32 |
| `out/webcam/live/frame.jpg` | 960×540 | 66 KB | 2026-08-25 | Bingkai pratinjau langsung terakhir |
| `out/webcam/live/mask.jpg` | 960×540 | 70 KB | 2026-08-25 | Mask segmentasi bertumpuk + poligon |
| `out/video/live/frame.jpg` | 960×540 | 51 KB | 2026-08-24 | Pratinjau dari sumber berkas video |
| `out/video/live/mask.jpg` | 960×540 | 71 KB | 2026-08-24 | Mask untuk sumber yang sama |
| `Web Pemantauan Pintu Air.dc.html` | — | 17 KB | 2026-08-23 | **Berkas desain kanvas** halaman operator |

---

## 9.2 Foto lokasi sasaran — `image.png`

Satu-satunya citra lokasi yang ada, dan ia memuat lebih banyak informasi
daripada yang tampak sekilas.

**Yang terlihat di bingkai:**

- Kolam air tenang berwarna cokelat-abu, khas air terbendung, dengan pantulan
  langit dan bangunan
- **Struktur bendung gerak** berwarna biru di kejauhan, lengkap dengan
  jembatan/jalur layan di atasnya
- **Sampah terapung** tersebar di permukaan: potongan styrofoam putih, serpihan
  daun, dan benda kecil memanjang
- **Vegetasi terapung** menumpuk di tepi kanan, menempel di tanggul
- Tanggul beton dengan pagar besi, dan **jalan paving di sebelah kanan** —
  inilah jalan yang menjadi `z_jalan_m` di dalam fisika
- Permukiman padat di seberang
- Bendera dan tiang di sisi kanan bingkai
- Bilah alat anotasi di tepi kanan layar

**Nilainya untuk laporan ini, dalam tiga hal:**

1. **Membenarkan premis proyek secara visual.** Sampah terapung memang ada di
   kolam hulu bendung, dan jalan memang berada tepat di sebelah muka air. Dua
   fakta itulah yang membuat rantai afflux di [06 §6.7](06-model-ai.md) punya
   arti praktis.
2. **Memperlihatkan sulitnya domain.** Air cokelat keruh dengan pantulan langit
   yang kuat, sampah kecil dan tipis, dan vegetasi yang menyatu dengan tanggul.
   Tidak satu pun dari kondisi ini terwakili di RIPTSeg — inilah jurang domain
   yang dicatat di [06 §6.8](06-model-ai.md), sekarang bisa dilihat langsung.
3. **Menandai apa yang harus diukur saat survei.** Dari foto ini bisa
   direncanakan: titik pasang kamera, titik pasang ultrasonik, dan beda tinggi
   antara muka air dan permukaan jalan.

> **Yang foto ini BUKAN.** Ia bukan bukti sistem bekerja, bukan hasil
> pengukuran, dan bukan pengganti survei. Belum ada satu pun anotasi dari citra
> ini yang masuk ke pelatihan — dataset `opsi` masih kosong.

---

## 9.3 Tabel pemasangan — `firmware/esp32/image.png`

Tabel tiga kolom: **Perangkat / Pin modul / ESP32 38-pin**. Isinya sama dengan
[04 §4.2](04-spesifikasi.md), dengan satu selisih yang layak diperiksa terhadap
kode:

| Perangkat | Pin modul | Menurut tabel | Menurut `config.h` |
|---|---|---|---|
| Tipping bucket | Sinyal reed switch | GPIO27 | **GPIO13** ← kabel sebenarnya |
| JSN-SR04T-V3.3 | RX/TRIG | GPIO5 | GPIO5 ✓ |
| JSN-SR04T-V3.3 | TX/ECHO | GPIO18 | GPIO18 ✓ |
| Sensor hujan | DO/D0 | GPIO34 | GPIO34 ✓ |
| Sensor hujan | AO/A0 (opsional) | GPIO35 | tidak dipakai |
| Relay pompa | IN | GPIO26 | GPIO26 ✓ |
| SIM800L | TX | GPIO16 (RX2 ESP32) | UART2 ✓ |
| SIM800L | RX | GPIO17 (TX2 ESP32) | UART2 ✓ |
| MicroSD | CS | GPIO33 | GPIO33 ✓ |
| MicroSD | SCK/CLK | GPIO14 | GPIO14 ✓ |
| MicroSD | MISO | GPIO19 | GPIO19 ✓ |
| MicroSD | MOSI | GPIO23 | GPIO23 ✓ |
| DS3231 | SDA | GPIO21 | GPIO21 ✓ |
| DS3231 | SCL | GPIO22 | GPIO22 ✓ |

Satu-satunya selisih adalah tipping bucket, dan selisih itu sudah tercatat di
komentar `config.h`. **Yang berlaku adalah kabelnya (GPIO13), bukan tabelnya.**

Tabel ini juga menegaskan varian sensor: **JSN-SR04T-V3.3** — informasi yang
langsung mengubah urutan pemeriksaan bug ultrasonik di
[08 §8.6](08-protokol-uji.md), karena varian itu dirancang untuk logika 3,3 V.

---

## 9.4 Pratinjau segmentasi langsung — `mask.jpg`

Ini keluaran visual sistem yang sesungguhnya: bingkai kamera dengan mask model
ditumpuk separuh-tembus, plus poligon.

**Konvensi warna dan garis:**

| Elemen | Tampilan |
|---|---|
| Kelas `water` | Bidang biru |
| Kelas `debris` / `clump` | Bidang merah muda |
| Poligon **ROI** | Garis **putih** |
| Poligon **struktur** (zona pintu) | Garis **kuning** |

**Isi berkas yang tersimpan sekarang** — dan ini perlu dicatat apa adanya:
kamera diarahkan ke **benda rumah tangga**, bukan sungai. Terlihat permukaan
hitam mengilap, selimut berbulu, dan kain merah. Model melabeli permukaan gelap
mengilap sebagai `water` (biru) dan kain merah sebagai `debris` (merah muda).

**Ini justru berguna, dan bukan aib:**

1. Ia membuktikan rantai visual utuh — kamera → segmentasi → penumpukan mask →
   penggambaran poligon → JPEG → halaman web.
2. Ia memperlihatkan **jurang domain secara konkret**: model yang dilatih pada
   citra sungai menyamakan plastik hitam mengilap dengan air, karena itulah
   isyarat visual yang ia pelajari. Tidak ada tabel angka yang menyampaikan hal
   ini securam satu gambar.
3. Ia menunjukkan poligon mendarat persis di tempat yang digambar operator.

> **Jangan pernah memakai gambar ini sebagai contoh hasil sistem** di
> presentasi tanpa keterangan bahwa itu uji meja atas benda rumah tangga.
> Menampilkannya polos akan menyesatkan.

---

## 9.5 Berkas desain antarmuka

`Web Pemantauan Pintu Air.dc.html` (17 KB) memuat rancangan kanvas halaman
operator: susunan kartu putusan, tinggi air, curah hujan, fisika, dan rel
notifikasi.

> Rancangan ini **mendahului** penghapusan kartu "Perkiraan kenaikan muka air"
> dan "Hujan regional". Kartu fisika masih tergambar di sana; di halaman yang
> berjalan sekarang sudah tidak ada.

Bagian desain yang **sengaja tidak diikuti** saat implementasi, karena
implementasinya harus jujur:

| Di desain | Di implementasi | Alasan |
|---|---|---|
| "diperbarui 12 detik lalu" ditanam keras | Dihitung dari `ts_utc` sungguhan | Baris itu satu-satunya petunjuk bahwa sumber sudah sunyi |
| Tiga notifikasi contoh ("Batch ESP32 tersimpan — 60 baris") | Diturunkan dari baris yang sama dengan kartu | Notifikasi karangan lebih buruk daripada rel kosong |
| Angka contoh di setiap kartu | `"tidak terukur"` bila `null` | `0%` terbaca sebagai "sungai bersih" |

---

## 9.6 Satu-satunya aset visual yang sudah ada

**`image.png`** di akar repositori — foto lokasi sasaran. Ini satu-satunya bukti
visual yang benar-benar dimiliki proyek sekarang, dan ia memuat lebih banyak
daripada yang terlihat sekilas:

| Yang terlihat | Kenapa berarti untuk laporan |
|---|---|
| Struktur pintu air biru di latar | Objek yang dipantau, dari sudut pandang jalan |
| Sampah terapung di permukaan | Kangkung dan eceng gondok — persis jenis yang disebut operator di [`../hasil_wawancara_operator.md`](../hasil_wawancara_operator.md) `B6` |
| Jalan beton di sisi kanan | Inilah `z_jalan_m` di dalam fisika. Ketinggiannya belum diukur — lihat `[ASUMSI]` di [04](04-spesifikasi.md) |
| Pantulan cermin di air tenang | Bahaya anotasi nomor satu di lokasi ini (`annotation_guideline.md §2.2`). Foto ini membuktikan bahayanya nyata, bukan teoretis |
| Permukiman rapat di seberang | Konteks risiko: siapa yang terdampak bila jalan tergenang |

**Yang perlu diperbaiki sebelum dipakai di laporan:** berkasnya tangkapan layar,
bukan foto langsung — ada bilah alat penyunting gambar menempel di tepi kanan
yang harus dipotong. Sertakan tanggal dan arah pengambilan bila masih diingat;
tanpa itu ia tidak bisa dirujuk sebagai bukti survei.

`firmware/esp32/image.png` **bukan** foto: itu tangkapan tabel pinout, dan isinya
sudah tersalin sebagai tabel di §9.3 berkas ini. Ia tidak menambah bukti apa pun.

---

## 9.6b Yang BELUM ada

`[BELUM]` — seluruh baris di bawah.

| Aset | Untuk apa |
|---|---|
| Tangkapan layar halaman operator `/` | Bukti antarmuka utama |
| Tangkapan layar halaman demo `/demo` | Bukti kamera langsung + penyunting poligon |
| Tangkapan layar penyunting poligon saat dipakai | Bukti alur kendali lewat berkas |
| Tangkapan layar panel "Deteksi model" | Bukti model bekerja pada adegan nyata |
| Foto rangkaian ESP32 terpasang | Bukti perangkat keras nyata |
| Foto Raspberry Pi + Insta360 Link terpasang | Bukti unit kamera lapangan ada wujudnya |
| Foto tiap sensor terpasang di lokasi | Bukti pemasangan lapangan |
| Foto kamera terpasang menghadap pintu air | Bukti sudut pandang |
| Video demonstrasi ujung-ke-ujung | Bukti sistem hidup |
| Video eksperimen miniatur E1 | Bukti validasi fisika |
| Grafik kurva pelatihan | Datanya ada di `runs/*/tb/`, gambarnya belum diekspor |
| Contoh keluaran segmentasi pada **citra sungai** | Sekarang hanya ada contoh benda rumah tangga |

**Taruh semuanya di `docs/gambar/`** dengan nama yang menjelaskan isinya
(`operator-banner-bahaya.png`, `esp32-rangkaian.jpg`, `pi-kamera-terpasang.jpg`),
lalu rujuk dari tabel di atas. Nama berkas yang deskriptif sudah separuh
keterangan gambar.

Catatan: kurva pelatihan **bukan** `[BELUM]` dalam arti datanya hilang — event
TensorBoard ada di `runs/*/tb/` dan metrik per-epoch ada di `runs/*/metrics.csv`.
Yang belum dilakukan hanya mengekspornya jadi gambar.

---

## 9.7 Daftar pengambilan — bisa diselesaikan dalam satu sesi

### A. Tangkapan layar (~15 menit, tanpa perangkat keras)

```powershell
# Terminal 1
cd web; npm run dev

# Terminal 2
$env:PYTHONPATH = "src"
.venv\Scripts\python.exe -u -m inference.run --config configs/inference/site_webcam.yaml --source 1
```

Lalu ambil:

1. `http://localhost:8000/` — halaman operator dengan data hidup
2. Halaman yang sama saat **tidak ada data** (matikan inferensi) — memperlihatkan
   keadaan "Belum ada pengukuran"; ini justru layak dipamerkan
3. `http://localhost:8000/demo` — kamera langsung
4. Penyunting poligon saat titik sedang ditarik
5. Kartu Penumpukan, diperbesar, dengan bilah dan ambang terlihat jelas

### B. Foto perangkat keras (~15 menit)

6. Seluruh rangkaian ESP32, tampak atas, komponen terlihat
7. Detail sambungan ultrasonik JSN-SR04T-V3.3 — **sekalian untuk penelusuran
   bug di [08 §8.6](08-protokol-uji.md)**
8. Tipping bucket, corong terlihat
9. Kartu SD dan modul RTC
10. Monitor serial saat firmware berjalan, angka terbaca

### C. Kurva pelatihan (~5 menit)

```powershell
tensorboard --logdir runs/
```

11. Kurva `val/iou_debris` untuk `combined_segformer_b0_640` — puncaknya di
    0,7313 pada epoch 40
12. Perbandingan beberapa run dalam satu grafik

### D. Video (~30 menit)

13. Perekaman layar 60–90 detik: sampah dijatuhkan di depan kamera →
    `accumulation_frac` naik di halaman → putusan berubah jadi "watch" lalu
    "blocked"
14. Perekaman ESP32: corong tipping bucket dimiringkan → baris baru muncul di
    basis data

### E. Lokasi (butuh kunjungan)

15. Bendung gerak dari beberapa sudut
16. Pintu air dari dekat, dengan meteran untuk skala
17. Jalan yang tergenang saat banjir — titik acuan `z_jalan_m`
18. Penumpukan sampah dalam kondisi sungguhan

---

## 9.8 Cara menyimpan aset visual

Agar tidak tercecer, dan agar berkas biner tidak membengkakkan repo:

```
docs/laporan/gambar/
├── ui-operator.png
├── ui-operator-kosong.png
├── ui-demo.png
├── ui-poligon.png
├── hw-rangkaian.jpg
├── hw-ultrasonik.jpg
├── hw-tipping-bucket.jpg
├── kurva-latih-segformer.png
├── lokasi-*.jpg
└── README.md          ← keterangan tiap berkas: kapan, di mana, apa yang terlihat
```

Aturan yang berlaku sama seperti sisa laporan ini: **setiap gambar diberi
keterangan tentang apa yang sebenarnya ditunjukkan.** Tangkapan layar uji meja
diberi label uji meja. Gambar tanpa keterangan pada akhirnya akan dibaca sebagai
bukti sesuatu yang tidak pernah diklaim.

Video besar sebaiknya tidak masuk git; taruh di penyimpanan terpisah dan tulis
tautannya di `docs/laporan/gambar/README.md`.

---

[← Daftar isi](README.md) · [Berikutnya: Referensi, batasan, penggunaan AI →](10-referensi-batasan-ai.md)
