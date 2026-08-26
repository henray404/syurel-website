# 7. Data Mentah Seluruh Pengujian

[← Daftar isi](README.md) · [← Sebelumnya: Model AI](06-model-ai.md)

---

Berkas ini memuat **angka mentahnya**, bukan ringkasannya. Setiap tabel disertai
perintah yang menghasilkannya, sehingga siapa pun bisa mengulang dan
membandingkan.

Protokol dan tafsirannya ada di [08-protokol-uji.md](08-protokol-uji.md).

---

## 7.1 Inventaris basis data

`[TERUKUR]` 2026-08-25.

| Berkas | Ukuran | `observations` | `esp_readings` | `rainfall` |
|---|---|---|---|---|
| `out/webcam/timeseries.sqlite` | 72,1 MB | **419.433** | **25** | **306** |
| `out/video/timeseries.sqlite` | — | 145 | — | — |
| `out/riptseg_loc1/timeseries.sqlite` | — | 50 | — | — |
| `out/timeseries.sqlite` | 16 KB | (sisa jalur lama, tidak dipakai) | | |

```powershell
.venv\Scripts\python.exe -c "import sqlite3; c=sqlite3.connect('out/webcam/timeseries.sqlite'); print([(t[0], c.execute(f'select count(*) from \"{t[0]}\"').fetchone()[0]) for t in c.execute(\"select name from sqlite_master where type='table'\")])"
```

---

## 7.2 Pengujian ESP32 → server, 2026-08-25

**Ini pengujian integrasi paling penting dalam proyek**, dan ini data
lengkapnya. Semua 25 baris, tanpa dipilih.

Perangkat `esp32-01`, rentang `2026-08-25T00:17:05Z` s/d `2026-08-25T01:28:55Z`
(07:17–08:28 WIB), diterima lewat `POST /api/ingest` dari firmware yang berjalan
di papan sungguhan.

```powershell
.venv\Scripts\python.exe -c "import sqlite3; c=sqlite3.connect('out/webcam/timeseries.sqlite'); [print(r) for r in c.execute('select ts_utc,jarak_cm,tinggi_cm,valid,n_sampel,tip_total,mm_per_jam,rssi,time_src from esp_readings order by ts_utc')]"
```

| # | `ts_utc` | `jarak_cm` | `tinggi_cm` | `valid` | `n_sampel` | `tip_total` | `mm_per_jam` | `rssi` | `time_src` |
|---|---|---|---|---|---|---|---|---|---|
| 1 | 00:17:05Z | NULL | 0,0 | 0 | 0 | 0 | 0,0 | −78 | ntp |
| 2 | 00:29:50Z | NULL | 0,0 | 0 | 0 | 0 | 0,0 | −68 | **rtc** |
| 3 | 00:30:49Z | NULL | 0,0 | 0 | 0 | 0 | 0,0 | −70 | ntp |
| 4 | 00:31:49Z | NULL | 0,0 | 0 | 0 | 0 | 0,0 | −67 | ntp |
| 5 | 00:32:49Z | NULL | 0,0 | 0 | 0 | 0 | 0,0 | −67 | ntp |
| 6 | 00:33:49Z | NULL | 0,0 | 0 | 0 | 0 | 0,0 | −65 | ntp |
| 7 | 00:34:49Z | NULL | 0,0 | 0 | 0 | 0 | 0,0 | −66 | ntp |
| 8 | 00:35:49Z | NULL | 0,0 | 0 | 0 | 0 | 0,0 | −69 | ntp |
| 9 | 00:37:27Z | NULL | 0,0 | 0 | 0 | 0 | 0,0 | −64 | ntp |
| 10 | 00:38:27Z | NULL | 0,0 | 0 | 0 | 0 | 0,0 | −64 | ntp |
| 11 | 00:39:27Z | NULL | 0,0 | 0 | 0 | 0 | 0,0 | −67 | ntp |
| 12 | 00:50:02Z | NULL | 0,0 | 0 | 0 | **41** | **12,3** | −69 | ntp |
| 13 | 01:06:21Z | NULL | 0,0 | 0 | 0 | 59 | 17,7 | −63 | **rtc** |
| 14 | 01:07:21Z | NULL | 0,0 | 0 | 0 | 59 | 17,7 | −71 | ntp |
| 15 | 01:08:21Z | NULL | 0,0 | 0 | 0 | 59 | 17,7 | −67 | ntp |
| 16 | 01:09:21Z | NULL | 0,0 | 0 | 0 | 59 | 17,7 | −67 | ntp |
| 17 | 01:10:21Z | NULL | 0,0 | 0 | 0 | **114** | **34,2** | −64 | ntp |
| 18 | 01:11:21Z | NULL | 0,0 | 0 | 0 | 127 | 38,1 | −68 | ntp |
| 19 | 01:12:21Z | NULL | 0,0 | 0 | 0 | 128 | 38,4 | −66 | ntp |
| 20 | 01:13:21Z | NULL | 0,0 | 0 | 0 | **148** | **44,4** | −75 | ntp |
| 21 | 01:24:55Z | NULL | 0,0 | 0 | 0 | 0 | 0,0 | −63 | ntp |
| 22 | 01:25:55Z | NULL | 0,0 | 0 | 0 | 0 | 0,0 | −63 | ntp |
| 23 | 01:26:55Z | NULL | 0,0 | 0 | 0 | 6 | 1,8 | −61 | ntp |
| 24 | 01:27:55Z | NULL | 0,0 | 0 | 0 | 6 | 1,8 | −63 | ntp |
| 25 | 01:28:55Z | NULL | 0,0 | 0 | 0 | 6 | 1,8 | −63 | ntp |

### Yang dibuktikan data ini

**`[TERUKUR]` Rantai unggah bekerja utuh dari ujung ke ujung.** Sensor → ISR →
jendela hujan → CSV → kartu SD → WiFi → `POST /api/ingest` → urai → SQLite.
25 baris ada di sana. Tidak ada satu pun langkah dalam rantai itu yang masih
teoretis.

**`[TERUKUR]` Tipping bucket berfungsi.** `tip_total` menanjak 0 → 41 → 59 →
114 → 127 → 128 → 148 saat corong dimiringkan manual, dan `mm_per_jam` mengikuti
sesuai `MM_PER_TIP` = 0,30 mm: 41 tip × 0,30 = 12,3 mm ✓, 59 × 0,30 = 17,7 ✓,
148 × 0,30 = 44,4 ✓. **Penghitungan dan konversinya keduanya benar secara
aritmetika.**

**`[TERUKUR]` Jendela hujan bergulir bekerja, bukan ekstrapolasi.** Baris 21–22
menunjukkan `tip_total` kembali 0 setelah jeda — bin lama sudah berputar keluar.
Skema v1.4 akan melaporkan angka mengada-ada di titik ini.

**`[TERUKUR]` NTP dengan cadangan RTC bekerja.** 23 dari 25 baris `ntp`, dua
baris `rtc` (nomor 2 dan 13). Jalur cadangan benar-benar terpakai, bukan sekadar
ada di kode.

**`[TERUKUR]` WiFi stabil.** RSSI −61 s/d −78 dBm.

### Yang dibantah data ini

**`[BELUM]` Ultrasonik tidak menghasilkan satu pun bacaan sah.** `jarak_cm` NULL,
`tinggi_cm` 0,0, `valid` 0, dan **`n_sampel` 0 di seluruh 25 baris**.

`n_sampel = 0` adalah temuan yang paling menunjuk: dari 5 ping yang dipicu tiap
5 detik, **nol** yang lolos sebagai sampel sah. Bukan satu-dua yang tersaring
median — nol.

Ini bukan bug jaringan dan bukan bug server: baris yang sama membawa data hujan,
RSSI, dan cap waktu yang benar. Penyebabnya di hulu CSV. Langkah penelusuran ada
di [08-protokol-uji.md §8.6](08-protokol-uji.md).

**Konsekuensi yang harus dinyatakan terang-terangan:** tinggi muka air adalah
pengukuran utama proyek ini, dan sampai bug ini selesai, sistem **tidak
mengukurnya**.

---

## 7.3 Pengujian kamera — sesi webcam 2026-08-23/24

`[TERUKUR]`

| Butir | Nilai |
|---|---|
| Site | `webcam` |
| Baris | **419.433** |
| Rentang | `2026-08-23T11:27:12Z` – `2026-08-24T17:27:23Z` (~30 jam) |
| `coverage` min / rata / maks | 0,0000 / **0,1149** / 0,7153 |
| `accumulation_frac` min / maks | 0,0000 / 0,6552 |
| Baris dengan `alert = 1` | **95.669** (22,8%) |
| `is_metric` | 0 di seluruh baris |
| `flux_units` | `relative_index` (419.419), `n/a` (14) |

Contoh tiga baris terakhir, apa adanya:

| `ts_utc` | `frame_idx` | `coverage` | `cov_smoothed` | `debris_px` | `water_px` | `roi_px` | `accum_px` | `accum_frac` | `growth/min` | `alert` |
|---|---|---|---|---|---|---|---|---|---|---|
| 2026-08-24T17:27:23Z | 42929 | 0,2096 | 0,2059 | 77.200 | 291.168 | 849.776 | 8.652 | 0,0558 | 0,0193 | 0 |
| 2026-08-24T17:27:23Z | 42928 | 0,2063 | 0,2059 | 75.808 | 291.704 | 849.776 | 8.463 | 0,0546 | 0,0166 | 0 |
| 2026-08-24T17:27:23Z | 42927 | 0,2090 | 0,2051 | 76.984 | 291.334 | 849.776 | 8.561 | 0,0552 | 0,0095 | 0 |

Alasan peringatan yang tercatat (lima teratas):

| `alert_reason` | Jumlah baris |
|---|---|
| `area 0.18 >= 0.18` | 702 |
| `area 0.18 >= 0.18; growth 0.031/min >= 0.03` | 8 |
| `area 0.18 >= 0.18; growth 0.032/min >= 0.03` | 4 |
| `area 0.18 >= 0.18; growth 0.033/min >= 0.03` | 5 |
| `area 0.18 >= 0.18; growth 0.034/min >= 0.03` | 5 |

### Cara membaca data ini dengan jujur

**Ini pengujian meja, bukan pengukuran sungai.** Kamera diarahkan ke wadah air
dan bungkus plastik. Yang dibuktikan angka-angka ini persis tiga hal, sesuai
yang tertulis di `configs/inference/site_webcam.yaml` sendiri:

1. Checkpoint termuat dan berjalan pada kecepatan interaktif.
2. Poligon ROI dan struktur mendarat di tempat yang dimaksud.
3. Seluruh rantai — kamera → SQLite → halaman web — tersambung.

Ia **tidak mengatakan apa pun** tentang penumpukan di bendung gerak. Angka yang
ditulisnya adalah pengukuran nyata atas apa pun yang ada di bingkai; ia bukan
pengukuran sungai. Nama site `webcam` menjaga angka-angka ini di berkas basis
data sendiri supaya tidak pernah keliru dianggap data lokasi.

**22,8% baris ber-alert bukan temuan tentang sungai.** Ambang `area_threshold`
0,18 dipasang untuk zona pintu bendungan, lalu diterapkan ke poligon
persegi-tengah di atas meja. Angka itu mengukur seberapa banyak plastik kebetulan
ada di dalam kotak, bukan risiko banjir.

**`is_metric = 0` di seluruh baris.** Homografi tidak dikalibrasi, jadi
`area_flux` adalah indeks relatif, bukan m²/detik. Tidak ada angka yang
berpura-pura jadi besaran fisik.

---

## 7.4 Pengujian video dan RIPTSeg

| Site | Baris | Rentang | `coverage` rata | `accum_frac` min–maks | Baris ber-alert |
|---|---|---|---|---|---|
| `video` | 145 | 2026-08-24T02:26:53Z – 02:26:57Z | 0,0011 | 0,0071–0,0163 | 29 |
| `riptseg_loc1` | 50 | 2026-08-15T04:03:57Z – 04:04:22Z | **0,3115** | 0,0–0,0 | 0 |

**`riptseg_loc1` adalah jalur inferensi yang dijalankan atas 50 bingkai uji dari
lokasi yang tidak pernah dilihat model.** Hasilnya:

- 50 bingkai diproses, deret waktu 51 baris ditulis ke CSV + SQLite
- `coverage` terhaluskan **0,316**, cap waktu UTC siap digabung dengan hujan
- Kecepatan kosong dan `area_flux` bernilai `n/a` — **dan itu benar**: sumbernya
  adalah citra selang-waktu berjarak menit, jadi tidak ada korespondensi
  antar-bingkai untuk aliran optik
- `is_metric = 0`, fluks berlabel `relative_index`

Gelungnya bekerja. Coverage adalah rasio nyata; fluks belum laju fisik.

---

## 7.5 Data curah hujan eksternal

`[TERUKUR]` — tabel `rainfall`, 306 baris.

| `source` | `kind` | Baris | Rentang | Σ mm |
|---|---|---|---|---|
| `open-meteo-archive` | observed | 120 | 2026-08-19T00:00:00Z – 2026-08-23T23:00:00Z | 4,8 |
| `open-meteo-forecast` | forecast | 168 | 2026-08-24T00:00:00Z – 2026-08-30T23:00:00Z | 0,6 |
| `bmkg` | forecast | 18 | 2026-08-24T13:00:00Z – 2026-08-26T16:00:00Z | 0,2 |

Ketiga sumber terjangkau dan menulis dengan benar. **Angka-angkanya tidak boleh
dijumlahkan lintas baris** — `observed` dan `forecast` adalah hal berbeda, dan
`interval_s` berbeda antar-sumber.

Dan peringatan yang selalu menempel: petak Open-Meteo 9–25 km sementara sel
hujan konvektif tropis 2–5 km. Ini sinyal regional. Tipping bucket di §7.2
adalah satu-satunya hujan yang benar-benar terukur di titik pengukuran.

---

## 7.6 Latensi terukur

`[TERUKUR]`

| Pengukuran | Nilai | Perangkat | Sumber |
|---|---|---|---|
| SegFormer-B0 @640, satu forward pass | **28 ms** (~35 fps) | RTX 5050 Laptop | Diukur 2026-08-23, dicatat di `site_webcam.yaml` |
| SegFormer-B0 @640, CPU 1 utas | 1013 ms | AMD Ryzen | `bench.cost` |
| LR-ASPP @512, CPU 1 utas | 164 ms | AMD Ryzen | `bench.cost` |
| Fast-SCNN @416, CPU 1 utas | 33 ms | AMD Ryzen | `bench.cost` |

Tabel biaya lengkap tujuh arsitektur ada di
[06-model-ai.md §6.4](06-model-ai.md).

Laju kamera saat pengujian: webcam menyerahkan 30 fps, model sanggup ~35 fps,
sehingga **model bukan pembatas** — setiap bingkai bisa disegmentasi. Itulah
sebabnya `trash_interval_s: 0.0` di konfigurasi webcam.

---

## 7.7 Log yang tersimpan

| Berkas | Isi | Ukuran/baris |
|---|---|---|
| `webcam_run.log` | Log inferensi webcam, termasuk peringatan pertumbuhan | 30 baris |
| `web/dev.log`, `web/demo.log`, `web/video.log`, `web/webcam.log` | Log server pengembangan Next.js | — |
| `gui_out.log`, `gui_err.log` | Keluaran GUI Gradio | 0 (kosong) |
| `runs/*/train_stdout.log` | Log pelatihan tiap run | 5–7 KB |
| `runs/*/metrics.csv` | Metrik per-epoch tiap run | 15–21 KB |
| `runs/*/tb/` | Event TensorBoard | — |

Cuplikan `webcam_run.log`:

```
site=webcam device=cuda size=640 fps=30.0
water mode: single-model (cache only, no compute saved)
intervals: trash=0.0s water=0.5s
...
[ALERT] frame 6888: growth 0.049/min >= 0.03
[ALERT] frame 6897: growth 0.045/min >= 0.03
[ALERT] frame 6918: growth 0.072/min >= 0.03
[ALERT] frame 7104: growth 0.075/min >= 0.03
[ALERT] frame 7162: growth 0.049/min >= 0.03
```

Tiga baris peringatan DirectShow di awal berkas
(`VIDEOIO(DSHOW): backend is generally available but can't be used to capture by
index`) berasal dari penyelidikan indeks kamera, bukan kegagalan — indeks 1
kemudian terbuka dan berjalan.

---

## 7.8 Data yang BELUM ada

Daftar ini sama pentingnya dengan tabel-tabel di atas.

| Data | Status | Akibat |
|---|---|---|
| Citra dari bendung gerak sasaran | **`[BELUM]`** | Model belum pernah melihat domain sasaran |
| Anotasi lokasi sasaran (dataset OPSI) | **`[BELUM]`** | Tidak ada evaluasi in-domain |
| Pengukuran geometri pintu air | **`[BELUM]`** | Seluruh keluaran fisika `[ASUMSI]` |
| Kalibrasi `JARAK_DASAR` | **`[BELUM]`** | Tinggi air tidak punya datum |
| Kalibrasi `MM_PER_TIP` dengan gelas ukur | **`[BELUM]`** | mm/jam benar secara aritmetika, belum tentu benar secara fisik |
| Eksperimen miniatur E1 (validasi `1/(1−BF)²`) | **`[BELUM]`** | Hukumnya terverifikasi ke literatur, belum ke alat sendiri |
| Eksperimen kalibrasi kamera E2 | **`[BELUM]`** | `skala`/`bias` masih identitas; kuadrat memperbesar galatnya |
| Tolok ukur di Raspberry Pi | **`[BELUM]`** | Angka latensi Pi masih ekstrapolasi |
| Bacaan ultrasonik sah | **`[BELUM]`** | Lihat §7.2 |
| Uji ketahanan jangka panjang (>30 jam) | **`[BELUM]`** | Kebocoran memori/berkas belum teruji |
| Wawancara operator | **`[BELUM]`** | Panduan sudah ada di `docs/wawancara_operator.md`, pelaksanaannya belum |

---

## 7.9 Cara mengekspor ulang seluruh data ini

```powershell
# seluruh esp_readings ke CSV
.venv\Scripts\python.exe -c "import sqlite3,csv; c=sqlite3.connect('out/webcam/timeseries.sqlite'); cur=c.execute('select * from esp_readings order by ts_epoch'); w=csv.writer(open('esp_export.csv','w',newline='')); w.writerow([d[0] for d in cur.description]); w.writerows(cur)"
```

`src/inference/sink.py` menulis CSV **dan** SQLite sekaligus, jadi salinan
teks-polos setiap deret pengamatan sudah ada di samping basis datanya:

```
out/webcam/timeseries.csv
out/video/timeseries.csv
out/riptseg_loc1/timeseries.csv
```

---

[← Daftar isi](README.md) · [Berikutnya: Protokol uji →](08-protokol-uji.md)
