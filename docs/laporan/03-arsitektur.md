# 3. Arsitektur Sistem dan Diagram Alir

[← Daftar isi](README.md) · [← Sebelumnya: Dokumentasi teknis](02-dokumentasi-teknis.md)

---

## 3.1 Gambaran satu layar

Tiga proses yang berdiri sendiri, satu berkas basis data sebagai titik temu.

```mermaid
graph TB
    subgraph LAPANGAN["Di lokasi"]
        US["Ultrasonik JSN-SR04T<br/>tinggi muka air"]
        TB["Tipping bucket<br/>curah hujan"]
        RTC["DS3231 RTC"]
        ESP["ESP32<br/>firmware v2.0"]
        SD[("Kartu SD<br/>sumber kebenaran")]
        SIM["SIM800L<br/>SMS"]
        RLY["Relai pompa"]
        CAM["Kamera<br/>Insta360 Link / webcam"]
    end

    subgraph KOMPUTER["Komputer pemantau"]
        INF["inference.run<br/>proses Python"]
        DB[("timeseries.sqlite<br/>mode WAL")]
        LIVE["out/webcam/live/<br/>frame.jpg · mask.jpg<br/>status.json · control.json<br/>polygons.json"]
        WEB["Next.js<br/>port 8000"]
    end

    subgraph LUAR["Di luar"]
        OM["Open-Meteo"]
        BMKG["BMKG"]
    end

    OPR(["Operator pintu air"])

    US --> ESP
    TB --> ESP
    RTC --> ESP
    ESP --> SD
    ESP --> SIM
    ESP --> RLY
    SIM -.SMS.-> OPR

    SD -->|"HTTP POST /api/ingest<br/>tiap 5 menit"| WEB
    CAM -->|"bingkai"| INF
    INF -->|"tulis observations"| DB
    INF -->|"tulis pratinjau"| LIVE
    WEB -->|"tulis esp_readings"| DB
    WEB -->|"baca"| DB
    WEB -->|"baca"| LIVE
    WEB -->|"tulis permintaan"| LIVE
    LIVE -->|"dibaca gelung"| INF
    OM --> RAIN["external.rainfall"]
    BMKG --> RAIN
    RAIN -->|"tulis rainfall"| DB
    WEB --> OPR
```

**Yang perlu diperhatikan dari gambar ini:** tidak ada satu pun panah dari web
ke proses inferensi selain lewat berkas. Itu disengaja, dan alasannya di §3.5.

---

## 3.2 Kontrak antar-komponen

Ada empat batas dalam sistem ini. Tiap batas punya satu kontrak, dan tiap
kontrak punya berkas yang memilikinya.

| # | Batas | Bentuk kontrak | Pemilik |
|---|---|---|---|
| 1 | ESP32 → web | CSV 14 kolom di dalam amplop JSON | `logic_csv.h` ↔ `web/lib/esp-csv.ts` |
| 2 | Inferensi → web | Tabel `observations` di SQLite | `src/inference/sink.py` |
| 3 | Web → inferensi | Berkas JSON di `live/`, ditulis atomik | `control.py` ↔ `api/camera`, `api/polygons` |
| 4 | Pengambil hujan → web | Tabel `rainfall` di SQLite | `src/external/rainfall.py` |

Semua kontrak searah kecuali #3, dan #3 pun bukan panggilan — ia titipan berkas.

**Kontrak #1 bersifat posisional, bukan bernama.** Firmware menulis dengan satu
`snprintf`:

```c
"%s,%lu,%.1f,%.1f,%d,%u,%lu,%u,%.1f,%s,%u,%s,%d,%s\n"
```

Urutan kolom **adalah** kontraknya. Menyisipkan kolom di tengah `logic_csv.h`
tanpa mengubah `ESP_COLUMNS` di `esp-csv.ts` akan menggeser setiap nilai
sesudahnya, dan tidak ada yang melempar galat — angka salah masuk kolom yang
salah tanpa suara. Kalau kolom harus ditambah, **tambahkan di akhir**, lalu
naikkan panjang yang diharapkan di kedua sisi.

---

## 3.3 Alur data — dari sensor sampai putusan

```mermaid
flowchart LR
    subgraph A["Jalur ESP32 — tiap 5 detik"]
        A1["pulseIn(ECHO)"] --> A2["5 sampel<br/>logic_median"]
        A2 --> A3["jarak_cm"]
        A3 --> A4["tinggi = JARAK_DASAR − jarak"]
        A5["ISR tip<br/>debounce 250 ms"] --> A6["60 bin 1 menit<br/>logic_rain"]
        A6 --> A7["mm_per_jam"]
        A4 --> A8["LevelFsm<br/>histeresis + dwell"]
        A7 --> A8
        A8 --> A9["AMAN / WASPADA / BAHAYA"]
    end

    subgraph B["Jalur kamera — tiap bingkai"]
        B1["bingkai BGR"] --> B2["segmentasi<br/>SegFormer-B0 640px"]
        B2 --> B3["mask 4 kelas"]
        B3 --> B4["coverage = debris/(debris+air)<br/>di ROI"]
        B3 --> B5["accumulation_frac<br/>di zona pintu"]
        B4 --> B6["penghalusan median"]
        B5 --> B7["BlockageMonitor<br/>ambang + laju tumbuh"]
        B7 --> B8["alert 0/1"]
    end

    subgraph C["Gabungan di web"]
        C1["verdict()"]
        C2["fisika()<br/>1/(1−BF)²"]
    end

    A9 --> C1
    B8 --> C1
    B5 --> C2
    C1 --> D(["Putusan operator"])
    C2 --> D
```

### Empat angka yang keluar dari rantai ini

| Angka | Dari | Arti |
|---|---|---|
| `tinggi_cm` | ESP32 | Tinggi muka air terhadap dasar, **satu titik** |
| `mm_per_jam` | ESP32 | Hujan satu jam terakhir, **di titik itu** |
| `accumulation_frac` | Kamera | Fraksi zona pintu yang tertutup sampah |
| `afflux_m` | Fisika | Berapa cm muka air hulu **akan** naik akibat penyumbatan itu |

Angka keempat itu yang membuat proyek ini berarti. Tanpa dia sistem hanya
melaporkan "pintu tertutup 24%", yang sudah diketahui operator dengan melihat.
Dengan dia sistem melaporkan "air akan duduk 59 cm lebih tinggi, dan jalan
tergenang di 29%" — sebuah akibat, cukup awal untuk ditindaklanjuti.

---

## 3.4 Urutan waktu — pengiriman ESP32 ke server

```mermaid
sequenceDiagram
    participant S as Sensor
    participant E as ESP32
    participant SD as Kartu SD
    participant W as Next.js /api/ingest
    participant DB as SQLite

    loop tiap 5 detik
        E->>S: picu TRIG, baca ECHO 5x
        S-->>E: 5 jarak (atau timeout)
        Note over E: median lalu simpan ke penyangga menit
    end

    loop tiap 60 detik
        Note over E: median penyangga menit jadi satu LogRow
        E->>SD: tulis 1 baris CSV
        E->>E: RainWindow.advanceMinute()
    end

    loop tiap 5 menit
        E->>SD: baca kursor /upload.cur
        SD-->>E: posisi byte
        E->>SD: baca baris belum terkirim
        E->>W: POST {device, rows:[{csv}, ...]}

        alt semua baris terurai
            W->>DB: INSERT OR IGNORE (satu transaksi)
            DB-->>W: jumlah baris baru
            W-->>E: 200 {received, inserted}
            E->>SD: majukan kursor
        else satu baris rusak
            W-->>E: 400 {error}
            Note over E: kursor TIDAK maju, batch diulang
        else basis data gagal
            W-->>E: 503 {error}
            Note over E: kursor TIDAK maju, batch diulang
        end
    end
```

### Tiga sifat yang lahir dari urutan ini

**SD adalah sumber kebenaran, unggah hanya kemudahan.** Kursor maju **hanya**
setelah server memastikan. Kegagalan jaringan tidak pernah bisa menghilangkan
baris — baris menumpuk di kartu dan berangkat belakangan. Ini tertulis di
`hw_upload.h` sebagai komentar pertama berkas.

**2xx adalah janji.** Komentar di `api/ingest/route.ts` menyatakannya: firmware
memajukan kursor SD hanya pada 2xx, jadi 2xx dari server adalah janji bahwa
**setiap** baris sudah tersimpan permanen. Apa pun yang kurang dari itu wajib
membalas non-2xx. Karena itu pula seluruh batch diurai **sebelum** menyentuh
basis data: satu baris rusak menolak seluruh batch, dan kita tidak boleh sudah
menulis separuhnya saat itu ketahuan.

**Kirim ulang aman.** `INSERT OR IGNORE` dengan kunci utama gabungan
`(device, ts_epoch)` membuat pengiriman ulang tidak berefek. Ini penting karena
firmware mengirim ulang setiap kali tanggapan hilang di jalan — dan tanggapan
yang hilang tidak bisa dibedakan dari permintaan yang tidak pernah sampai.

---

## 3.5 Kendali lewat berkas, bukan lewat proses

Dua endpoint (`/api/camera`, `/api/polygons`) mengubah perilaku gelung inferensi
yang **sedang berjalan**. Keduanya melakukannya dengan menulis satu berkas JSON
kecil.

```mermaid
sequenceDiagram
    participant U as Operator (/demo)
    participant W as Next.js
    participant F as out/webcam/live/
    participant I as inference.run

    U->>W: POST /api/polygons {roi, structure}
    W->>W: validatePolygons()
    alt tidak valid
        W-->>U: 400 {error}
    else valid
        W->>F: tulis .polygons.json.tmp
        W->>F: rename jadi polygons.json
        W-->>U: 202 {saved:true}
    end

    loop tiap ~0,5 detik
        I->>F: baca polygons.json
        I->>I: valid_polygon() dengan aturan yang sama
        I->>I: bangun ulang mask, lanjut mengukur
        I->>F: tulis status.json
    end

    U->>W: GET /api/camera
    W->>F: baca status.json
    W-->>U: {active, devices, running}
```

**Handler ini tidak pernah menjalankan program.** Ditulis eksplisit di
`api/camera/route.ts`:

> Memberi endpoint HTTP kuasa memanggil program adalah lubang yang layak
> diserang, dan setiap muat-ulang server pengembangan akan meninggalkan anak
> proses yatim yang masih memegang kamera.

Konsekuensinya: `202 Accepted`, bukan `200 OK`. Permintaan **diterima**, bukan
**diterapkan**. Gelung mengambilnya dalam sekitar setengah detik dan melaporkan
lewat `status.json` apakah perangkatnya benar-benar terbuka.

Validasi indeks kamera pun sengaja sempit — satu digit `/^[0-9]$/`. Nilai itu
diserahkan ke `cv2.VideoCapture` di proses lain; string bebas yang sampai ke
lapisan penangkapan adalah cara sebuah jalur berkas atau URL berubah jadi
sesuatu yang tidak diinginkan siapa pun.

---

## 3.6 Mengapa satu berkas SQLite, bukan basis data server

| Pertimbangan | SQLite | Postgres/MySQL |
|---|---|---|
| Layanan yang harus hidup | 0 | 1 |
| Penulis serentak | Python + Node, lewat WAL | mudah |
| Salinan cadangan | salin satu berkas | dump |
| Jalan tanpa jaringan | ya | perlu soket |
| Beban tulis proyek ini | ~2 baris/detik | jauh di bawah kapasitas |

Mode **WAL** (commit `ba42b1a`) adalah yang membuat dua penulis mungkin: pembaca
Node tidak memblokir penulis Python, dan sebaliknya. Tanpa WAL, halaman web
yang dimuat saat inferensi menulis akan mendapat `SQLITE_BUSY`.

**Batas yang harus diakui:** semuanya di satu mesin. Kalau kelak inferensi
pindah ke Raspberry Pi di lokasi sementara web di tempat lain, berkas ini tidak
lagi jadi titik temu dan lapisan sinkronisasi harus ada. `[BELUM]` dirancang.

---

## 3.7 Kegagalan tiap komponen dan akibatnya

Ini tabel yang paling layak ditanya penguji, karena sistem peringatan dinilai
dari perilakunya saat rusak, bukan saat mulus.

| Yang mati | Akibat langsung | Yang tetap jalan | Ditandai di UI? |
|---|---|---|---|
| Kamera | `accumulation_frac` berhenti | Tinggi air, hujan, SMS | Ya — "Belum ada pengukuran" |
| ESP32 | Tinggi air & hujan titik berhenti | Kamera, fisika, putusan | Ya — sumber ditandai sunyi >20 menit |
| WiFi di ESP32 | Unggah tertunda | **Semua** — SD terus mencatat, SMS terus terkirim | Tidak langsung; terlihat dari umur data |
| Ultrasonik | `tinggi_cm` hilang | Hujan, SMS, FSM **menahan** level | Ya — `valid=0` tersimpan |
| Server web mati | Unggah gagal | Firmware & inferensi jalan terus | — |
| `site_geometry.json` hilang | Kartu fisika kosong | Tinggi air & putusan penyumbatan | Ya — kartu "tidak tersedia" |
| Tabel `rainfall` belum ada | Kartu hujan regional kosong | Sisanya | Ya |

Dua pola yang berulang di tabel ini, dan keduanya disengaja:

1. **Kegagalan bersifat lokal.** Endpoint `/api/latest` membungkus blok fisika
   dan hujan dalam `try` masing-masing. Geometri lokasi yang hilang tidak boleh
   menjatuhkan tinggi air dan putusan penyumbatan — dua angka yang benar-benar
   ditindaklanjuti operator.
2. **Sunyi selalu tampak.** Tidak ada layar yang menampilkan angka lama seolah
   baru. `waktu.ts` menghitung "5 menit lalu" sungguhan, dan `notifikasi.ts`
   menandai sumber sebagai sunyi setelah `STALE_AFTER_MINUTES` = 20.

---

## 3.8 Penjadwalan — periode setiap gelung

| Gelung | Periode | Konstanta | Alasan angkanya |
|---|---|---|---|
| Baca sensor ESP32 | 5 detik | `SENSOR_PERIOD_MS` | Cukup rapat untuk median per menit |
| Catat ke SD | 60 detik | `LOG_PERIOD_MS` | Satu baris/menit, ~525 ribu baris/tahun |
| Unggah batch | 5 menit | `UPLOAD_PERIOD_MS` | Kompromi kesegaran vs daya radio |
| Sinkron NTP | 6 jam | `NTP_PERIOD_MS` | Deriva DS3231 jauh di bawah ini |
| Ulang SMS | 5 menit | `SMS_REPEAT_MS` | Jangan membanjiri operator |
| Segmentasi (bendungan) | 30 detik | `trash_interval_s` | Air terbendung bergerak dalam menit |
| Segmentasi (webcam uji) | tiap bingkai | `trash_interval_s: 0.0` | Cukup cepat: 28 ms/bingkai di RTX 5050 |
| Pratinjau JPEG | 0,1 detik | `preview.interval_s` | ~10 pasang/detik terbaca sebagai video |

Angka pratinjau punya sebab yang layak dicatat: bukan 30 pasang/detik, karena
tiap pasang ~70 KB — menyamai laju kamera berarti ~2 MB/detik gesekan cakram
terus-menerus untuk menggambar ulang bingkai yang toh tidak bisa ditampilkan
peramban lebih cepat daripada ia mengecat ulang.

---

## 3.9 Batas arsitektur yang diketahui

- **`[BELUM]` Semuanya satu mesin.** Lihat §3.6.
- **`[BELUM]` Tidak ada autentikasi.** Endpoint `/api/ingest` menerima POST dari
  siapa pun yang bisa mencapai port 8000. Di LAN terisolasi ini dapat diterima;
  begitu terekspos ke internet, **wajib** ada token perangkat. Lihat
  [05-database-api.md §5.8](05-database-api.md).
- **`[BELUM]` Tidak ada rotasi/retensi basis data.** `observations` sudah
  419.433 baris (72 MB) hanya dari pengujian meja. Di laju bendungan (30 detik)
  itu sekitar satu juta baris per tahun — masih wajar untuk SQLite, tapi tidak
  pernah diuji sampai ke sana.
- **`[ASUMSI]` Satu titik ukur tinggi air.** Satu ultrasonik mengukur satu
  tempat. Kemiringan muka air di sepanjang kolam hulu tidak terlihat sama sekali.

---

[← Daftar isi](README.md) · [Berikutnya: Spesifikasi →](04-spesifikasi.md)
