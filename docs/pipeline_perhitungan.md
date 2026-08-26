# Pipeline perhitungan: masukan → proses → keluaran

Peta lengkap dari piksel dan pulsa sensor sampai kalimat di layar operator.
Setiap langkah menyebut berkas dan barisnya, supaya bisa dilacak saat sidang.

```
KAMERA ──┐
         ├─→ observations ──┐
ESP32 ───┘                  ├─→ FISIKA ──→ web ──→ layar operator
                            │
API hujan ─→ rainfall ──────┘
```

---

## Rantai A — Kamera → penumpukan

### Masukan

| | |
|---|---|
| Frame | `H×W×3` uint8 BGR dari `cv2` |
| Checkpoint | `runs/combined_segformer_b0_640/best.pt`, val debris IoU **0,7313** |
| Poligon `roi` | permukaan air yang diamati |
| Poligon `structure` | **zona muka pintu** — penentu alarm |

Poligon digambar operator lewat web (`web/components/PolygonEditor.tsx`),
disimpan sebagai **pecahan 0–1** di `live/polygons.json`, bukan piksel — tiga hal
mengubah ukuran gambar antara kamera dan klik: `preview.py` menyusutkan ke 960 px,
browser memuat ke lebar kolom, dan ganti kamera mengubah resolusi tangkapan.

### Proses

1. `infer()` → mask indeks kelas `H×W`, nilai 0–3 (background/water/debris/clump)
2. `run.py:201` — `combined`: debris menang saat tumpang tindih; botol di atas air dihitung debris
3. `metrics.py:51` `frame_metrics()` — dua penyebut berbeda:

```
coverage          = debris_px / (debris_px + water_px)      ← di dalam ROI
accumulation_frac = accum_px  / structure_pixels            ← di dalam zona pintu
```

4. `metrics.py:86` `Smoother` — median bergerak. `None` **dibuang, bukan diisi nol**
5. `metrics.py:114` `BlockageMonitor.update()` — dua ambang (luas & laju), plus `consecutive: 3` sampel berturut-turut

### Keluaran

Satu baris ke tabel `observations`, 20 kolom.

### Yang paling sering disalahpahami

**Dua angka itu berbeda, dan penyebutnya beda.**

`coverage` berpenyebut `debris + water` — luas permukaan basah, **bukan luas
frame**. Jadi langit dan tanggul tidak mengencerkan angkanya.

`accumulation_frac` berpenyebut piksel poligon `structure`. **Hanya angka inilah
yang memicu alarm.**

Konsekuensi penting: kesalahan segmentasi air — mode kegagalan nomor satu di
lokasi, yaitu pantulan — merusak `coverage`, tapi **tidak menyentuh
`accumulation_frac`**, karena penyebutnya geometris tetap, bukan hasil deteksi.

Syarat `consecutive: 3` yang mencegah satu kilatan pantulan matahari membunyikan
alarm.

---

## Rantai B — ESP32 → tinggi air & hujan lokal

**Masukan:** waktu pantul ultrasonik, pulsa tipping bucket, waktu NTP.

**Proses (firmware):** median dari `n_sampel` bacaan → `jarak_cm`;
`tinggi_cm` = referensi − jarak; hitungan jungkitan → `mm_per_jam`.

**Keluaran:** baris CSV 14 kolom → POST `/api/ingest` → tabel `esp_readings`.

Kontraknya: **2xx hanya kalau semua baris tersimpan**, karena firmware memajukan
kursor SD pada 2xx dan tak pernah mengirim ulang baris itu.

---

## Rantai C — Fisika (afflux)

Kode: [`src/physics.py`](../src/physics.py) ·
cermin: [`web/lib/fisika.ts`](../web/lib/fisika.ts) ·
parameter: [`configs/site_geometry.json`](../configs/site_geometry.json) ·
**sumber literatur: [`referensi_fisika.md`](referensi_fisika.md)**

### Rumus

```
BF   = skala · accumulation_frac + bias        (kalibrasi dari eksperimen E2)
A    = A_bersih · (1 − BF)
Q    = Cd · b · a · √(2 g h)                   debit aliran bebas
h    = Q² / (Cd² · A² · 2g)                    balik untuk cari head

→  h ∝ 1 / A²

h_tersumbat / h_bersih = 1 / (1 − BF)²
BF_kritis = 1 − √(h_bersih / z_jalan)
```

### Kenapa bentuk rasio yang dipakai

`h_tersumbat / h_bersih` **tak berdimensi**. Tidak ada debit, lebar pintu, atau
faktor skala yang bertahan di dalamnya — karena itu akuarium 80 cm bisa
memvalidasi hukum yang sama dengan bendung gerak sungguhan, **tanpa penskalaan
Froude**.

### Satu hal yang mengejutkan dan wajib dipahami

**Debit kekal.** Substitusikan:

```
Q = Cd·A₀(1−BF)·√(2g·h₀/(1−BF)²) = Cd·A₀·√(2gh₀) = Q₀
```

Muka air naik **tepat sebesar** yang diperlukan agar debit sungai yang sama tetap
lewat. Itulah definisi afflux. Kerusakannya bukan aliran yang hilang, melainkan
air yang menumpuk di hulu untuk memaksa aliran itu menembus lubang yang mengecil
— dan itulah yang menggenangi jalan.

Karena itu dashboard **tidak** menampilkan debit pada head afflux: nilainya
selalu sama persis dengan debit pintu bersih, jadi akan mencetak satu angka di
dua kolom. Yang ditampilkan adalah kapasitas pada **muka air tak berubah** —
kehilangan yang bisa ditindaklanjuti operator.

### Angka ini batas atas, bukan taksiran terbaik

Mengecilkan luas bukaan punya nama resmi di literatur: **Reduced Area Method**
(ARR 2016 Book 6 Ch. 6). Padanannya, **Energy Loss Method**, membiarkan luas
tetap dan menaikkan koefisien kehilangan di mulut.

Aturan ARR: RAM untuk penyumbatan **dari dasar** (sedimentasi), ELM untuk
penyumbatan **di mulut** — dan rakit sampah terapung adalah penyumbatan di
mulut. Pada contoh terhitung mereka (penyumbatan 50%), RAM memberi muka air
hulu 6,04 m lawan ELM 4,71 m: **RAM 28% lebih tinggi**.

Pembelaannya: alasan ARR menyalahkan RAM adalah kecepatan yang melonjak di
sepanjang **barel** gorong-gorong. Pintu air tidak punya barel — pintu itu
orifis tipis, jadi mode kegagalan itu sebagian besar tidak mengenai kita.

Tetap saja: **angka afflux di dashboard adalah sisi konservatif.** Untuk
peringatan dini itu sisi yang benar untuk salah, tapi harus dikatakan. Kartu
web menulis "batas atas". Rinciannya di [`referensi_fisika.md`](referensi_fisika.md) §3.

### Yang diukur kamera bukan yang menyumbat pintu

Mohammed (2022) mengukur di flume: penumpukan kayu apung menaikkan kedalaman
hulu **15%** — jadi premisnya selamat, sampah terapung memang menyumbat pintu
bawah. Tapi dua hasil lain dari percobaan yang sama menampar asumsi pemetaan:

- Peluang tersangkut **turun** saat bukaan pintu diperbesar — dan operator
  mengubah bukaan sepanjang hari.
- **Bonggol akar lebih menyumbat daripada batang** pada luas yang sebanding:
  yang menentukan adalah volume dan kedalaman rendaman, bukan luas permukaan.

Kamera hanya melihat **luas permukaan 2D**. Karena itu `skala` dan `bias` di
`site_geometry.json` bukan sekadar koreksi kamera — keduanya menyerap seluruh
fisika "luas 2D → luas bukaan 3D yang hilang", dan fisika itu bergantung pada
bukaan pintu. **Kalibrasi E2 harus per-bukaan-pintu.**

### Dua batas yang dijaga kode

**Kuadrat memperbesar galat.** Kamera membaca 24% saat sebenarnya 31% bukan galat
7%: `1/(0,76)² = 1,73` lawan `1/(0,69)² = 2,10` — meleset 18%. Kalibrasi kamera
(eksperimen E2) wajib sebelum angka ini dipercaya.

**Meledak saat BF → 1.** Pintu tertutup penuh memberi head tak hingga, yang
omong kosong: air sungguhan melimpas ke atas, ke samping, atau strukturnya jebol.
Di atas `BF_MAX_TRUSTED = 0,85` dilaporkan "Di luar model", **tidak pernah**
sebagai angka.

### Status sekarang

`configs/site_geometry.json` bertanda **`UNCALIBRATED`**. Semua ukuran pintu
masih tebakan, jadi web menempelkan lencana **BELUM DIKALIBRASI** pada kartu
fisika. Yang perlu diukur saat survei:

| | dari mana |
|---|---|
| `b_m` lebar bukaan | meteran |
| `a_m` tinggi bukaan | meteran + tanya operator |
| `Cd` | 0,61 `[LIT]`, lebih baik dikalibrasi dari miniatur (E1) |
| `h_bersih_m` | garis dasar saat pintu bersih |
| `z_jalan_m` | tinggi muka air saat jalan mulai tergenang |

---

## Rantai D — Hujan eksternal

Lihat [`data_eksternal.md`](data_eksternal.md). Ringkas: tiga API publik tanpa
kunci → tabel `rainfall` → kartu "Hujan regional".

**Selalu ditandai sebagai sinyal regional**, karena petaknya 9–25 km sementara
sel hujan tropis 2–5 km.

---

## Penggabungan di web

`readLatest()` mengambil baris terbaru dari `esp_readings` dan `observations`;
`readRainfall()` meringkas `rainfall`; `fisika()` menghitung afflux. Semuanya
digabung di `/api/latest`.

**Setiap blok gagal sendiri-sendiri.** Config lokasi hilang atau tabel hujan
belum ada tidak boleh menjatuhkan tinggi air dan kesimpulan penyumbatan — dua hal
yang benar-benar ditindaklanjuti operator.

### Satu hal yang perlu kamu sadari

`verdict()` **hanya membaca `obs`** (kamera). `tinggi_cm` dari ESP32 sama sekali
tidak memengaruhi kesimpulan — hanya ditampilkan sebagai angka. Jadi kalimat
"bersihkan dulu" murni dari citra, bukan dari air yang naik.

Menggabungkan keduanya — misal menaikkan tingkat kewaspadaan kalau tinggi air
naik **dan** penumpukan bertambah — adalah langkah berikutnya yang masuk akal,
tapi belum dibangun, dan tidak boleh dibangun sebelum fisika dikalibrasi.

---

## Aturan yang tidak boleh dilanggar

Dua hal yang membuat sistem ini berbahaya, bukan sekadar kurang sempurna, kalau
dilanggar:

**1. `/api/ingest` menjawab 2xx hanya kalau semua baris tersimpan.** Firmware
memajukan kursor SD pada 2xx. Menerima sebagian lalu menjawab 2xx = data hilang
selamanya.

**2. Nilai yang tak terukur tidak pernah dirender sebagai 0.** `metrics.py`
mengembalikan `None`, bukan `0.0`, dengan sengaja: `0.0` terbaca sebagai "sungai
bersih", yang persis salah saat banjir. Web menulis "tidak terukur".

Aturan yang sama berlaku untuk hujan: jendela tanpa data → `null`, hari kering →
`0`. Keduanya **tidak boleh** terlihat sama.
