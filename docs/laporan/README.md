# Dokumentasi Final — Syurell

Sistem pemantauan penumpukan sampah terapung di pintu air bendung gerak.
Kamera + kecerdasan buatan + sensor + fisika hidraulika → peringatan dini banjir.

Disusun 2026-08-25. Setiap angka di sini berasal dari berkas di repositori ini
atau dari perintah yang benar-benar dijalankan — bukan dari perkiraan.

---

## Daftar isi

| # | Berkas | Isi |
|---|---|---|
| 1 | [01-repositori.md](01-repositori.md) | Struktur kode, riwayat commit, cara membangun dan menjalankan |
| 2 | [02-dokumentasi-teknis.md](02-dokumentasi-teknis.md) | Penjelasan tiap modul, alur kerja pengembangan |
| 3 | [03-arsitektur.md](03-arsitektur.md) | Arsitektur sistem, diagram alir, kontrak antar-komponen |
| 4 | [04-spesifikasi.md](04-spesifikasi.md) | Spesifikasi teknologi dan komponen perangkat keras/lunak |
| 5 | [05-database-api.md](05-database-api.md) | Skema basis data, dokumentasi seluruh endpoint API |
| 6 | [06-model-ai.md](06-model-ai.md) | Dokumentasi model, dataset, protokol latih, hasil evaluasi |
| 7 | [07-data-pengujian.md](07-data-pengujian.md) | Data mentah seluruh pengujian |
| 8 | [08-protokol-uji.md](08-protokol-uji.md) | Protokol pengujian dan hasilnya |
| 9 | [09-dokumentasi-visual.md](09-dokumentasi-visual.md) | Tangkapan layar, foto, video implementasi |
| 10 | [10-referensi-batasan-ai.md](10-referensi-batasan-ai.md) | Daftar pustaka, batasan sistem, dokumentasi penggunaan AI |

---

## Status kejujuran

Dokumen ini dibuat untuk diperiksa penguji. Karena itu tiga penanda dipakai
terus-menerus di seluruh berkas, dan **tidak boleh dihapus saat penyuntingan**:

**`[TERUKUR]`** — angka dari eksperimen atau perintah yang benar-benar
dijalankan, bisa diulang siapa pun dengan perintah yang dicantumkan.

**`[BELUM]`** — bagian yang memang belum ada. Ditulis apa adanya, bukan
disembunyikan atau diisi angka karangan.

**`[ASUMSI]`** — nilai yang dipakai sistem tapi belum diverifikasi di lapangan.
Terutama seluruh dimensi pintu air di `configs/site_geometry.json`.

Ringkas keadaan sekarang:

| Bagian | Status |
|---|---|
| Model segmentasi | **[TERUKUR]** val debris IoU 0,7313 |
| Perangkat lunak web | **[TERUKUR]** 70/70 uji lulus |
| Perangkat lunak Python | **[TERUKUR]** 93/93 uji lulus |
| Firmware ESP32 — logika | **[TERUKUR]** 47 pemeriksaan lulus |
| Firmware ESP32 — kirim ke server | **[TERUKUR]** 25 baris tersimpan, 2026-08-25 |
| Tipping bucket (curah hujan) | **[TERUKUR]** hitungan dan konversi benar |
| **Sensor ultrasonik (tinggi air)** | **[BELUM]** `n_sampel = 0` di seluruh baris |
| Fisika afflux — rumus | **[TERUKUR]** terverifikasi ke literatur primer |
| Fisika afflux — parameter | **[ASUMSI]** seluruh dimensi pintu masih tebakan |
| Kalibrasi lapangan | **[BELUM]** belum ada survei lokasi |
| Foto/video implementasi | **[BELUM]** belum diambil |

Jangan menaikkan status apa pun di tabel ini tanpa bukti yang bisa diulang.
Sistem ini mengeluarkan peringatan banjir; melebihkan kesiapannya bukan
kesalahan administratif, melainkan bahaya.

---

## Cara cepat menjalankan seluruh sistem

Dua terminal, dari akar repositori.

```powershell
# Terminal 1 — web
cd web
npm run dev                      # http://localhost:8000

# Terminal 2 — inference kamera
$env:PYTHONPATH = "src"
.venv\Scripts\python.exe -u -m inference.run `
    --config configs/inference/site_webcam.yaml --source 1
```

Rinciannya di [01-repositori.md](01-repositori.md).

---

## Dokumen pendukung di luar folder ini

Folder ini merangkum. Rincian teknis tetap tinggal di tempat asalnya:

- [`../rencana_penelitian.md`](../rencana_penelitian.md) — proposal penelitian lengkap
- [`../prediksi_banjir.md`](../prediksi_banjir.md) — deteksi vs prediksi, batas lead time, mengapa LSTM belum mungkin
- [`../survei_lapangan.md`](../survei_lapangan.md) — daftar data yang harus diambil di lokasi
- [`../pipeline_perhitungan.md`](../pipeline_perhitungan.md) — rantai perhitungan masukan→keluaran
- [`../referensi_fisika.md`](../referensi_fisika.md) — verifikasi literatur rumus hidraulika
- [`../data_eksternal.md`](../data_eksternal.md) — riset dan implementasi API curah hujan
- [`../model_comparison.md`](../model_comparison.md) — perbandingan tujuh arsitektur
- [`../datasets.md`](../datasets.md) — katalog dataset
- [`../wawancara_operator.md`](../wawancara_operator.md) — panduan wawancara operator pintu air
- [`../annotation_guideline.md`](../annotation_guideline.md) — panduan anotasi
