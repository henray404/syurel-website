# 8. Protokol Pengujian dan Hasilnya

[← Daftar isi](README.md) · [← Sebelumnya: Data pengujian](07-data-pengujian.md)

---

## 8.1 Ringkasan hasil

`[TERUKUR]` — seluruh perintah di bawah dijalankan 2026-08-25, dan keluarannya
disalin apa adanya.

| Rangkaian | Perintah | Hasil |
|---|---|---|
| Python | `pytest tests/ -q` | **93 lulus, 0 gagal** (12,06 detik) |
| Web | `npx vitest run` | **70 lulus, 0 gagal** |
| Firmware (logika) | `powershell tests\firmware\run_tests.ps1` | **47 pemeriksaan, 0 gagal** |
| Periksa mandiri fisika | `python -m physics` | `physics ok` |
| Periksa mandiri kendali | `python -m inference.control` | `control ok` |
| Periksa mandiri metrik | `python -m inference.metrics` | `metrics self-check OK` |

**Total 210 pemeriksaan otomatis, semuanya lulus.**

Angka itu harus dibaca bersama batasannya di §8.7: pengujian mencakup logika
perangkat lunak dengan baik dan **tidak mencakup perangkat keras sama sekali**.

---

## 8.2 Rangkaian Python — 93 uji

```powershell
$env:PYTHONPATH = "src"
.venv\Scripts\python.exe -m pytest tests/ -q
```

```
........................................................................ [ 77%]
.....................                                                    [100%]
93 passed in 12.06s
```

| Berkas | Fungsi uji | Cakupan |
|---|---|---|
| `tests/test_inference.py` | 32 | Metrik, geometri, poligon, penghalusan, monitor penyumbatan, sink, kendali |
| `tests/test_data_pipeline.py` | 22 | Adapter dataset, konversi, pembagian sadar-grup, validasi |
| `tests/test_train.py` | 16 | Dataset latih, sampler seimbang, fungsi rugi |
| `tests/test_bench.py` | 10 | Pengukuran biaya dan akurasi |
| `tests/test_physics.py` | 10 | Rantai afflux |

(Kolom kedua adalah jumlah `def test_*`; 93 adalah jumlah yang benar-benar
dikumpulkan pytest — selisihnya dari parametrisasi.)

### Sepuluh uji fisika, apa adanya

Nama uji di proyek ini sengaja berupa kalimat pernyataan, sehingga daftarnya
sekaligus jadi daftar sifat yang dijamin:

```
test_afflux_matches_the_web_contract
test_a_missing_measurement_never_becomes_a_clear_gate
test_calibration_from_experiment_e2_is_applied
test_critical_bf_predicts_the_road_flooding
test_critical_bf_is_none_when_the_road_is_below_the_clear_level
test_summary_reports_capacity_lost_at_an_unchanged_level
test_site_json_is_uncalibrated_unless_it_says_otherwise
test_the_shipped_site_config_is_still_marked_uncalibrated
test_rainfall_timestamps_use_the_projects_one_format
test_a_revised_forecast_replaces_rather_than_duplicates
```

Dua di antaranya layak disorot:

**`test_a_missing_measurement_never_becomes_a_clear_gate`** menjaga Aturan 1
dari [02 §2.1](02-dokumentasi-teknis.md): `None` masuk, `None` keluar. Nilai
`0.0` berarti "pintu bersih" — hal paling berbahaya yang bisa dikarang modul ini.

**`test_the_shipped_site_config_is_still_marked_uncalibrated`** adalah uji yang
akan **gagal dengan sengaja** kalau seseorang menaikkan status
`site_geometry.json` jadi `CALIBRATED` tanpa benar-benar mensurvei lokasi. Uji
yang menjaga kejujuran, bukan menjaga kode.

---

## 8.3 Rangkaian web — 70 uji

```powershell
cd web
npx vitest run
```

```
PASS (72) FAIL (0)
```

| Berkas | Uji | Cakupan |
|---|---|---|
| `web/tests/polygons.test.ts` | 10 | Validasi poligon — **kasus yang sama dengan `control.py`** |
| `web/tests/live.test.ts` | 9 | Nama pratinjau (himpunan tertutup), unggah JPEG, tulis atomik |
| `web/tests/verdict.test.ts` | 9 | Putusan operator, keempat state |
| `web/tests/waktu.test.ts` | 9 | Format waktu relatif Indonesia |
| `web/tests/join.test.ts` | 7 | Penggabungan jendela waktu, toleransi 60 detik |
| `web/tests/esp-csv.test.ts` | 6 | Urai CSV, termasuk `nan` dan jumlah kolom salah |
| `web/tests/ingest.test.ts` | 5 | Batch, `INSERT OR IGNORE`, idempotensi |
| `web/tests/notifikasi.test.ts` | 5 | Rel notifikasi, ambang sunyi |
| `web/tests/bmkg.test.ts` | 5 | Urai prakiraan BMKG, ambang, penentuan waktu |
| `web/tests/latest.test.ts` | 4 | Baris terbaru, `null` saat kosong |
| `web/tests/db.test.ts` | 3 | Buka basis data, buat tabel |

**Yang paling penting dari tabel ini adalah baris teratas.** `polygons.test.ts`
menguji implementasi kembar dengan kasus yang sama seperti sisi Python. Itulah
harga yang dibayar karena validasi poligon ditulis dua kali — dan harga itu
**dibayar**, bukan diabaikan.

Dulu ada baris kedua sejenis, `fisika.test.ts` (12 uji), pasangan dari
`test_physics.py`. Berkas itu hilang bersama `web/lib/fisika.ts` saat kartu
"Perkiraan kenaikan muka air" dihapus. Fisika afflux sekarang hanya diuji di
sisi Python, dan tidak ada lagi yang perlu disinkronkan.

Jumlah bergerak dari 70 → 58 karena penghapusan itu, lalu naik ke **72** setelah
`bmkg.test.ts` (5) dan `live.test.ts` (9) masuk. Yang terakhir menjaga jalur
unggah pratinjau: nama yang tidak dikenal ditolak tanpa menyentuh disk, badan
non-JPEG tidak pernah menimpa bingkai terakhir yang bagus, dan tidak ada berkas
`.tmp` tertinggal.

---

## 8.4 Rangkaian firmware — 47 pemeriksaan

```powershell
powershell tests\firmware\run_tests.ps1
```

```
47 checks, 0 failures
```

> **Angka ini pernah salah, dan itu layak dicatat.** Pada revisi 25 Agustus
> berkas ini juga menulis "47 checks, 0 failures" — padahal saat itu **18 di
> antaranya gagal**. Penyebabnya bukan logika firmware, melainkan uji yang
> tertinggal: ambang `WASPADA_ENTER`/`BAHAYA_ENTER` pernah diskalakan ulang dari
> skala sungai (30/60 cm) ke rig meja (3,0/4,5 cm), dan `RAIN_WINDOW_MIN` dari
> 60 menit jadi 10, tanpa nilai di `test_logic.cpp` ikut menyesuaikan.
>
> Uji-nya lulus saat ditulis, lalu diam-diam basi. Klaim `[TERUKUR]` bertahan di
> laporan karena tidak ada yang menjalankan ulang perintahnya.
>
> **Perbaikannya bukan menyetel ulang angkanya, melainkan menghapus angkanya.**
> Setiap tinggi dan panjang jendela di `test_logic.cpp` kini **diturunkan dari
> konstanta `config.h`** — `WASPADA_ENTER + 0,5`, `(BAHAYA_ENTER + BAHAYA_EXIT)
> / 2`, `RAIN_WINDOW_MIN − 1` — sehingga penskalaan berikutnya membawa uji-nya
> serta alih-alih meninggalkannya.
>
> Uji-nya diperiksa tidak menjadi tautologi: mutasi `>` → `>=` disuntikkan ke
> `logic_level.h:75`, dan pemeriksaan batas menangkapnya (`exactly at
> WASPADA_ENTER does not escalate`). Angka 47/47 berarti perilakunya benar,
> bukan sekadar uji yang menyetujui dirinya sendiri.

Skripnya mengompilasi `tests/firmware/test_logic.cpp` dengan g++ langsung ke
biner host:

```powershell
g++ -std=c++11 -O0 -Wall -Wextra -I firmware\esp32\include -o test_logic.exe test_logic.cpp
```

**Tanpa Arduino, tanpa perangkat keras.** Ini mungkin karena berkas `logic_*.h`
memang C++ murni — pemisahan `logic_` vs `hw_` di
[02 §2.4](02-dokumentasi-teknis.md) ada persis untuk ini.

### Sifat yang dijamin uji-uji ini

**Median, bukan rata-rata.** Satu echo buruk tidak boleh menggeser jawaban. Uji
bahkan memaku perilaku panjang-genap: `v[n/2]` adalah nilai tengah **atas** dari
dua nilai tengah (bawah 2, atas 10, rata-rata 6 — ketiganya berbeda di kasus
itu). Ujinya mendokumentasikan perilaku yang disetujui, bukan mengubahnya.

**Jendela hujan mengeluarkan bin lama tepat waktu.** Hitungan yang diketahui
ditaruh di bin 0; ia harus bertahan melewati `RAIN_WINDOW_MIN − 1` rotasi (masih
di dalam jendela) dan **dibersihkan pada rotasi berikutnya**, saat `head_`
melingkar kembali ke bin 0. Uji ini memaku bin mana yang dibuang dan kapan
persisnya.

**Bug v1.4 yang digantikan diuji secara eksplisit:** tip yang tersebar di
sepanjang jendela **dijumlahkan**, lalu diskalakan sekali ke laju per jam. Skema
lama mengekstrapolasi satu menit dan melaporkan 36 mm/jam hanya dari 2 tip.

**Naik segera, turun butuh dua syarat.** De-eskalasi menuntut ambang keluar
**dan** waktu dwell. Kasus ketak-ketik relai — riak di sekitar ambang — diuji
langsung.

**Bacaan tidak valid tidak boleh menurunkan status.** Dan ujinya lebih teliti
dari yang terlihat, dengan alasan yang ditulis di berkasnya:

> Satu tik tepat setelah eskalasi belum cukup membuktikan ini: pewaktu dwell
> belum habis, jadi implementasi yang keliru sekalipun — yang membiarkan bacaan
> tidak valid menurunkan status — tetap akan menunjukkan BAHAYA pada tik itu.
> Dorong tik tidak-valid kedua jauh melewati `DWELL_DOWN_MS` dan pastikan ia
> **masih** BAHAYA. Inilah asersi yang menurut pengujian mutasi paling penting.

**Hujan sendiri bisa menaikkan level** meski sungai rendah, dan hujan yang
berada **tegas di antara** `RAIN_WASPADA` (10) dan `RAIN_BAHAYA` (30) harus
mendarat di WASPADA — tidak melompat ke BAHAYA, tidak jatuh ke AMAN.

---

## 8.5 Uji integrasi — ESP32 ke server

Ini pengujian dengan perangkat keras sungguhan, dan **protokolnya perlu ditulis
karena akan diulang** setelah bug ultrasonik selesai.

### Prasyarat

1. Mesin dan ESP32 di jaringan WiFi/MiFi yang sama.
2. Cari alamat LAN mesin: `ipconfig`.
3. Isi `firmware/esp32/include/config_secrets.h`:
   `WIFI_SSID`, `WIFI_PASS`, `INGEST_URL = http://<IP-LAN>:8000/api/ingest`,
   `DEVICE_ID`, `NOMOR_TUJUAN`.
4. Firewall Windows: izinkan TCP 8000 masuk di profil jaringan **privat**.

### Langkah

```powershell
# 1. Nyalakan server
cd web
npm run dev                       # http://<IP-LAN>:8000

# 2. Unggah firmware, buka monitor
pio run -t upload -d firmware/esp32
pio device monitor -d firmware/esp32

# 3. Tunggu satu siklus unggah (UPLOAD_PERIOD_MS = 5 menit)

# 4. Periksa apa yang masuk
.venv\Scripts\python.exe -c "import sqlite3; c=sqlite3.connect('out/webcam/timeseries.sqlite'); print(c.execute('select ts_utc,jarak_cm,tinggi_cm,valid,n_sampel,tip_total,mm_per_jam from esp_readings order by ts_utc desc limit 5').fetchall())"
```

### Kriteria lulus

| # | Kriteria | Hasil 2026-08-25 |
|---|---|---|
| 1 | Baris muncul di `esp_readings` | **LULUS** — 25 baris |
| 2 | `ts_utc` masuk akal, `time_src` = `ntp` atau `rtc` | **LULUS** — 23 ntp, 2 rtc |
| 3 | `rssi` terisi | **LULUS** — −61…−78 dBm |
| 4 | Tip bertambah saat corong dimiringkan | **LULUS** — 0→41→59→114→148 |
| 5 | `mm_per_jam` = `tip_total × 0,30` | **LULUS** — 12,3 / 17,7 / 44,4 ✓ |
| 6 | Pengiriman ulang tidak menggandakan baris | **LULUS** — tidak ada duplikat |
| 7 | **`valid` = 1 dan `n_sampel` > 0** | **GAGAL** — 0 di seluruh 25 baris |
| 8 | `tinggi_cm` berubah saat sensor digerakkan | **GAGAL** — tetap 0,0 |

Enam dari delapan lulus. Dua yang gagal adalah jalur ultrasonik, dan keduanya
gagal karena satu sebab yang sama.

---

## 8.6 Protokol penelusuran bug ultrasonik — belum dijalankan

**Ini langkah berikutnya proyek.** Ditulis di sini supaya siapa pun bisa
melanjutkan.

### Yang sudah diketahui

| Fakta | Sumber |
|---|---|
| `n_sampel = 0` di seluruh 25 baris | §7.2 |
| Semua bidang lain di baris yang sama benar | §7.2 |
| Tabrakan pin SD/ECHO **sudah** dihindari (`SD_SCK_PIN` 14, bukan 18) | `config.h` |
| Logika median lulus 47 pemeriksaan di host | §8.4 |

Tiga fakta pertama mengecualikan jaringan, server, dan penguraian. Fakta keempat
mengecualikan logika median. **Yang tersisa hanyalah antara pin dan sensor.**

### Langkah 1 — isolasi sensor

Unggah sketsa minimal yang hanya memicu TRIG dan mencetak mikrodetik mentah:

```cpp
#include <Arduino.h>
#define TRIG 5
#define ECHO 18

void setup() {
  Serial.begin(115200);
  pinMode(TRIG, OUTPUT);
  pinMode(ECHO, INPUT);
}

void loop() {
  digitalWrite(TRIG, LOW);  delayMicroseconds(2);
  digitalWrite(TRIG, HIGH); delayMicroseconds(10);
  digitalWrite(TRIG, LOW);
  unsigned long us = pulseIn(ECHO, HIGH, 30000);  // 0 = timeout
  Serial.println(us);
  delay(500);
}
```

Baca monitor serial pada 115200 baud. Arahkan sensor ke dinding sekitar 20 cm.

### Langkah 2 — bercabang berdasarkan hasilnya

> **Varian sensornya penting.** Tabel pemasangan
> ([09 §9.3](09-dokumentasi-visual.md)) menyebut **JSN-SR04T-V3.3**, bukan
> JSN-SR04T biasa. Varian itu memang dirancang untuk logika 3,3 V, sehingga
> dugaan "kurang pembagi tegangan" **turun prioritas** — tapi catu dayanya tetap
> perlu diperiksa, karena beberapa papan V3.3 tetap menuntut VCC 5 V meski
> logikanya 3,3 V.

| Bacaan | Artinya | Yang diperiksa |
|---|---|---|
| **0 terus** | Timeout — echo tidak pernah tinggi | (a) **Tegangan VCC sensor** — ukur dengan multimeter; papan JSN-SR04T umumnya butuh 5 V pada VCC walau jalur logikanya 3,3 V. (b) **Mode papan.** Sebagian papan JSN-SR04T punya resistor/jumper pemilih mode; dalam mode serial, TRIG/ECHO tidak berperilaku seperti HC-SR04 sama sekali, dan `pulseIn()` akan selalu timeout. Periksa apakah ada resistor mode terpasang. (c) Kabel TRIG/ECHO tertukar. (d) Transduser tidak terpasang ke papan |
| **~1160 µs** untuk sasaran 20 cm | Sensor sehat | Bugnya di gerbang keabsahan `logic_level.h`. `n_sampel = 0` berarti **setiap** sampel ditolak — periksa batas jangkauan wajar; kalau disetel untuk sungai sementara pengujian di atas meja 20 cm, penolakan itu justru benar |
| Angka acak melompat-lompat | Derau / catu daya | Kapasitor decoupling, kabel lebih pendek, catu terpisah |

### Langkah 3 — setelah lolos

Kembalikan firmware penuh, ulangi §8.5, dan kriteria 7–8 harus berubah jadi
LULUS. Baru setelah itu `JARAK_DASAR` dikalibrasi di lokasi.

**Jangan menguji ulang jalur jaringan.** Ia sudah terbukti.

---

## 8.7 Apa yang TIDAK diuji

Bagian ini yang paling menentukan seberapa jauh angka "210 pemeriksaan lulus"
boleh dipercaya.

| Area | Status | Akibat |
|---|---|---|
| Perangkat keras sensor | **Tidak diuji otomatis** | Bug ultrasonik lolos ke lapangan |
| `hw_time.h`, `hw_logger.h`, `hw_upload.h` | **Tidak diuji otomatis** | Butuh papan; hanya diverifikasi manual lewat §8.5 |
| Komponen React | **Tidak ada uji** | Tidak ada uji render/interaksi |
| Uji ujung-ke-ujung peramban | **Tidak ada** | Alur `/demo` diverifikasi manual |
| Handler rute API | **Tidak diuji langsung** | Yang diuji modul `lib/` di bawahnya |
| Beban / ketahanan | **Tidak diuji** | Sesi terpanjang 30 jam; kebocoran belum teruji |
| Kualitas model di domain sasaran | **Tidak diuji** | Belum ada citra lokasi |
| Sirkuit SIM800L / SMS | **Tidak diuji otomatis** | `sms_status` tercatat, isinya belum diverifikasi |
| Relai pompa | **Tidak diuji otomatis** | Logika FSM teruji; sirkuitnya tidak |
| Keamanan | **Tidak diuji** | Tidak ada autentikasi untuk diuji |

Ringkasnya: **logika perangkat lunak tercakup baik; perangkat keras tidak
tercakup sama sekali.** Untuk sistem yang setengah nilainya ada di sensor
lapangan, itu jurang yang harus dinyatakan, bukan disamarkan di balik angka 210.

---

## 8.8 Menjalankan seluruh rangkaian

```powershell
# Python
$env:PYTHONPATH = "src"
.venv\Scripts\python.exe -m pytest tests/ -q

# Web
cd web; npx vitest run; cd ..

# Firmware (butuh g++ di PATH)
powershell tests\firmware\run_tests.ps1

# Periksa mandiri modul
.venv\Scripts\python.exe -m physics
.venv\Scripts\python.exe -m inference.control
.venv\Scripts\python.exe -m inference.metrics
```

Setiap modul dengan logika non-sepele punya `demo()` yang bisa dijalankan
mandiri lewat `python -m <modul>` — pemeriksaan terkecil yang gagal kalau
logikanya rusak, tanpa kerangka uji apa pun.

---

## 8.9 Empat bug yang ditemukan pengujian, dan ujinya sekarang

Dari [`../phase1_results.md`](../phase1_results.md) §6. **Keempatnya gagal
secara senyap**, dan tidak satu pun tertangkap uji asap sintetis — masing-masing
kini punya uji regresi.

1. **Jalur citra hanya basename.** COCO RIPTSeg menyimpan `frame.jpg` sementara
   citranya ada di `loc1/`…`loc6/`, sehingga penyelesaian jalur tidak menemukan
   apa pun dan **seluruh 300 citra dilewati sementara konverter melaporkan
   sukses**.
2. **Tak-berlabel ≠ background.** Hanya ~20,6% tiap bingkai yang beranotasi.
   Memetakan 80% sisanya ke `background` membuat air tampak 15% piksel, dan akan
   mengajari model bahwa air sungai adalah background. Sekarang
   `unlabelled: ignore`.
3. **Poligon struktur yang absen berarti "seluruh bingkai".** Peringatan
   penyumbatan menyala di bingkai 14 demo padahal tidak ada struktur
   dikonfigurasi — di produksi itu alarm palsu yang mengirim regu pembersih.
4. **Worker dataloader lahir dengan interpreter salah**, sehingga pelatihan
   menggantung di epoch 0 dengan GPU 2%. Worker yatim lalu bertahan dan membuat
   run berikutnya kelaparan, yang membuatnya tampak seperti masalah model.

Pola yang sama muncul empat kali: **kegagalan yang senyap dan tampak sukses**.
Itulah sebabnya `n_sampel` disimpan, `is_metric` disimpan, `coverage` boleh
bernilai `None`, dan status `UNCALIBRATED` punya ujinya sendiri.

---

[← Daftar isi](README.md) · [Berikutnya: Dokumentasi visual →](09-dokumentasi-visual.md)
