# Data eksternal: curah hujan

Hasil riset dan implementasi, 2026-08-23/24.

Setiap angka di bawah berasal dari **panggilan HTTP nyata**, bukan dari membaca
dokumentasi. Klaim yang tidak diuji ditandai begitu.

Kode: [`src/external/rainfall.py`](../src/external/rainfall.py) ·
Tampilan: **tidak ada lagi** — kartu "Hujan regional" sudah dihapus dari halaman
operator. Data tetap diambil dan tersimpan di tabel `rainfall`; yang hilang hanya
jalurnya ke layar. Baca §4 soal akibatnya pada atribusi.

---

## 1. Ringkasan tiga sumber

| | BMKG | Open-Meteo arsip | Open-Meteo prakiraan |
|---|---|---|---|
| Endpoint | `api.bmkg.go.id/publik/prakiraan-cuaca` | `archive-api.open-meteo.com/v1/archive` | `api.open-meteo.com/v1/forecast` |
| Jenis | prakiraan | reanalisis (historis) | prakiraan |
| Rentang | ~3 hari ke depan | 1990 → kemarin | 7 hari ke depan |
| Resolusi waktu | 3 jam (18 titik) | 1 jam | 1 jam (168 titik) |
| Jeda data | — | **~1 hari** | — |
| Kunci API | tidak perlu | tidak perlu | tidak perlu |
| Alamat | kode `adm4` desa | lat/lon | lat/lon |
| Field hujan | `tp` (mm) | `precipitation` (mm) | `precipitation` (mm) |
| Status uji | HTTP 200 ✓ | HTTP 200 ✓ | HTTP 200 ✓ |

Batas laju Open-Meteo gratis: 600/menit, 5.000/jam, 10.000/hari, 300.000/bulan.
Kebutuhan proyek ini sekitar **24 panggilan/hari** — jauh di bawah batas.
`[High]` — dibaca dari halaman harga resmi.

---

## 2. Peringatan yang paling penting

**Open-Meteo bukan pengukuran. Itu model, dan petaknya 9–25 km.**

Sumbernya reanalisis: ERA5 0,25° ≈ 25 km, ERA5-Land 0,1° ≈ 11 km, ECMWF IFS 9 km
untuk data terbaru. Sementara **sel hujan konvektif tropis lebarnya 2–5 km** —
jenis yang menyebabkan lonjakan sampah di Indonesia.

Konsekuensinya tegas: satu sel badai bisa mengguyur bendungan habis-habisan
sementara petak 25 km melaporkan hujan ringan, atau sebaliknya. Angka ini
**sinyal regional**, bukan curah hujan di bendunganmu.

Karena itu kartu di web selalu memuat kalimat peringatan itu, dan tipping bucket
tetap disebut sebagai sumber lokal yang sahih.

> Kalau `τ*` (jeda hujan → sampah, `rencana_penelitian.md` §5.14) dihitung dari
> Open-Meteo lalu dilaporkan sebagai "jeda di lokasi ini", penguji yang paham
> meteorologi bisa membongkarnya. Hitung dari tipping bucket.

---

## 3. Pembagian peran

| Peran | Sumber | Alasan |
|---|---|---|
| **Kebenaran lapangan** | tipping bucket ESP32 | Satu-satunya hujan yang benar-benar terukur di bendungan |
| **Hitung `τ*`** | tipping bucket | `coverage` baru ada sejak kamera terpasang, jadi arsip panjang tak menambah pasangan data |
| **Tambal lubang** | Open-Meteo arsip | Saat tipping bucket mampet, kehabisan daya, atau ESP32 mati — pasti terjadi dalam satu musim |
| **Pembanding** | Open-Meteo arsip | Bukti independen bahwa tipping bucket membaca waras |
| **Peringatan dini** | BMKG | Sumber resmi Indonesia; jauh lebih kuat dipertahankan di sidang daripada layanan asing |

Web dulu memilih BMKG lebih dulu untuk prakiraan dan jatuh ke Open-Meteo kalau
BMKG tidak tersedia; logika itu ada di `web/lib/hujan.ts`, yang ikut terhapus
bersama kartunya. Urutan prioritas yang sama masih berlaku di sisi pengambilan
data, [`src/external/rainfall.py`](../src/external/rainfall.py).

---

## 4. Kewajiban atribusi

BMKG **mewajibkan** namanya ditampilkan di aplikasi yang memakai datanya — itu
syarat pemakaian, bukan sopan santun. Repositori resmi `infoBMKG/data-cuaca`
menyatakan bahwa BMKG wajib dicantumkan sebagai sumber data dan ditampilkan pada
aplikasi atau sistem yang memakainya.

Dulu dipenuhi di kaki kartu "Hujan regional". Kartu itu sudah dihapus, jadi
**saat ini tidak ada atribusi BMKG yang tampil di mana pun di aplikasi.**

Selama tidak ada layar yang menampilkan data BMKG, tidak ada yang dilanggar —
kewajibannya melekat pada aplikasi yang *memakai dan menampilkan* datanya. Dua
hal yang tetap wajib:

1. **Begitu angka BMKG muncul lagi di layar mana pun**, atribusinya ikut muncul
   di layar itu. Ini syarat pemakaian, bukan sopan santun.
2. **Data BMKG tetap masuk tabel `rainfall`** dan bisa dipakai di analisis
   laporan. Kalau angkanya dikutip di laporan, BMKG dicantumkan di daftar
   pustaka — sudah terdaftar sebagai sumber D2 di
   [`laporan/10-referensi-batasan-ai.md`](laporan/10-referensi-batasan-ai.md).

Open-Meteo meminta sitasi `Zippenfenig, P. (2023). Open-Meteo.com Weather API`
beserta sumber dasarnya (ECMWF, Copernicus). Masukkan ke daftar pustaka laporan.

---

## 5. Cara pakai

Isi dulu koordinat di [`configs/site_geometry.json`](../configs/site_geometry.json):

```json
"site": { "lat": -7.55, "lon": 112.23, "adm4": "35.15.09.2003" }
```

Lalu:

```bash
PYTHONPATH=src python -m external.rainfall --db out/webcam/timeseries.sqlite --days 7
```

Bisa juga tanpa mengisi berkas: `--lat -7.55 --lon 112.23 --adm4 35.15.09.2003`.

Terverifikasi 2026-08-24 dengan koordinat contoh:

```
open-meteo archive :  120 titik disimpan (16 berhujan)
open-meteo forecast:  168 titik disimpan (4 berhujan)
bmkg forecast      :   18 titik disimpan (2 berhujan)
```

Layak dijadwalkan sekali sejam (Task Scheduler / cron). Tidak fatal kalau gagal —
setiap sumber ditangkap sendiri-sendiri lalu dilewati; tipping bucket tetap jalan.

---

## 6. Bentuk data

Tabel `rainfall`, di berkas SQLite yang sama dengan `observations` dan
`esp_readings`:

| kolom | isi |
|---|---|
| `source` | `open-meteo-archive` / `open-meteo-forecast` / `bmkg` |
| `ts_utc` | `2026-08-24T06:00:00Z` — format sama dengan seluruh proyek |
| `ts_epoch` | detik epoch, dipakai indeks |
| `mm` | curah hujan dalam interval itu; `NULL` = tidak terukur |
| `interval_s` | 3600 (jam-jaman) atau 10800 (BMKG 3-jaman) |
| `kind` | `observed` (reanalisis) atau `forecast` |
| `fetched_epoch` | kapan baris ini ditarik |

Kunci utama `(source, ts_epoch)`.

**`INSERT OR REPLACE`, berbeda dari ingest ESP32 yang memakai `INSERT OR IGNORE`.**
Prakiraan untuk jam tertentu direvisi saat jam itu mendekat, dan yang terbaru yang
layak disimpan. Sebaliknya, bacaan sensor untuk waktu lampau adalah fakta yang
tidak boleh ditimpa.

**`NULL` ≠ `0`.** Jendela tanpa data mengembalikan `null`, hari kering sungguhan
mengembalikan `0`. Kalau keduanya dirender sama, dashboard berbohong saat API mati.

---

## 7. Yang masih kosong

- [ ] **Koordinat lokasi** — `site.lat` / `site.lon` masih `null`. Ambil dengan GPS HP saat survei. Tanpa ini Open-Meteo tak bisa dipanggil.
- [ ] **Kode `adm4`** — format kode wilayah Kemendagri empat tingkat (`31.71.01.1001` = provinsi.kabupaten.kecamatan.desa). Format terverifikasi berfungsi, tapi repositori resmi BMKG **tidak mendokumentasikan cara mencarinya** dan tidak ditemukan endpoint pencarian. Perlu ditelusuri setelah lokasi diketahui. `[Medium]`
- [ ] **Logbook historis operator** — `rencana_penelitian.md:549`, butuh izin (pertanyaan `D5` di panduan wawancara).

---

## 8. Yang sengaja tidak dipakai

Sudah terkunci di `rencana_penelitian.md` §8; penguji kemungkinan menanyakannya.

| Ditolak | Alasan |
|---|---|
| **Model prediksi hujan sendiri** | BMKG punya radar, satelit, model numerik, data puluhan tahun. Kelembapan/tekanan/suhu/angin hanya proksi dari yang sudah dimodelkan benar di sana. Hasil terbaik yang realistis: sedikit lebih buruk dari BMKG |
| **10 variabel masukan** | Satu musim = banyak baris tapi sedikit *kejadian* independen. Sepuluh masukan atas puluhan kejadian menghasilkan hafalan, bukan pembelajaran |
| **Mengganti tipping bucket dengan API** | Petak 9–25 km vs sel hujan 2–5 km. API tidak bisa mengukur hujan di satu titik |

---

## Sumber

- [Data Prakiraan Cuaca Terbuka BMKG](https://data.bmkg.go.id/prakiraan-cuaca/)
- [infoBMKG/data-cuaca](https://github.com/infoBMKG/data-cuaca)
- [Open-Meteo Historical Weather API](https://open-meteo.com/en/docs/historical-weather-api)
- [Open-Meteo Pricing](https://open-meteo.com/en/pricing)
