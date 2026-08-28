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
        CAM["Insta360 Link<br/>kamera USB"]
        PI["Raspberry Pi 5<br/>unit kamera"]
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
    CAM -->|"USB"| PI
    PI -->|"MJPEG 640x360<br/>TBCare.local:81/stream"| INF
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

**Dua hal yang perlu diperhatikan dari gambar ini.**

Pertama, tidak ada satu pun panah dari web ke proses inferensi selain lewat
berkas. Itu disengaja, dan alasannya di §3.5.

Kedua, **kamera tidak menempel pada komputer pemantau.** Ia menempel pada
Raspberry Pi di lokasi, yang mengalirkan MJPEG lewat jaringan. Batas itu adalah
satu-satunya tempat citra menyeberangi kabel, dan menaruhnya di sana membuat
mesin bergpu boleh berada di mana saja — termasuk jauh dari sungai. Pi tidak
menjalankan model; rinciannya di [04 §4.7](04-spesifikasi.md).

---

### 3.1b Penempatan fisik — apa yang di lapangan, apa yang di server

Diagram §3.1 menunjukkan aliran data. Diagram ini menunjukkan **di mana tiap
bagian benar-benar berada**, karena batas fisik itulah yang menentukan apa yang
selamat saat sesuatu mati.

```mermaid
flowchart TB
    subgraph SUNGAI["Di tepi sungai — bertenaga terbatas"]
        direction TB
        subgraph U1["Unit sensor"]
            ESP["ESP32<br/>+ microSD"]
            S1["Ultrasonik<br/>JSN-SR04T"]
            S2["Tipping bucket"]
            S3["RTC DS3231"]
            S4["SIM800L"]
            S1 -.-> ESP
            S2 -.-> ESP
            S3 -.-> ESP
            ESP -.-> S4
        end
        subgraph U2["Unit kamera"]
            PI["Raspberry Pi 5<br/>16 GB"]
            CAM["Insta360 Link"]
            CAM -.USB.-> PI
        end
    end

    subgraph RUANG["Di ruang kendali — listrik tetap"]
        GPU["Laptop bergpu<br/>RTX 5050"]
        DB[("timeseries.sqlite")]
        GPU --- DB
    end

    OPR(["Operator"])

    ESP ==>|"WiFi · POST tiap 5 menit"| GPU
    PI  ==>|"WiFi · MJPEG kontinu"| GPU
    S4  -.->|"SMS"| OPR
    GPU ==>|"HTTP :8000"| OPR
```

**Yang menentukan pembagian ini:** perangkat di tepi sungai harus murah, tahan
cuaca, dan hemat daya. GPU tidak memenuhi satu pun dari ketiganya. Karena itu
tidak ada model yang berjalan di lapangan — yang ada di sana hanya pembaca sensor
dan pengalir video.

**Konsekuensi yang harus diakui, dan berbeda untuk tiap unit:**

| Kalau server mati | Unit sensor | Unit kamera |
|---|---|---|
| Data saat itu | **Selamat** — ditulis ke microSD dulu | **Hilang** — tidak disimpan di Pi |
| Setelah server hidup | Baris tertunda terkirim menyusul | Mulai dari bingkai baru |
| Peringatan ke operator | **Tetap jalan** — SMS lewat SIM800L | Tidak ada |

Baris terakhir itu yang paling berarti untuk sistem peringatan banjir: **jalur SMS
tidak melewati server sama sekali.** ESP32 mengirimnya langsung lewat SIM800L, jadi
peringatan tingkat BAHAYA tetap sampai meski seluruh sisi komputer padam.

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
        A5["ISR tip<br/>debounce 250 ms"] --> A6["10 bin 1 menit<br/>logic_rain"]
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

    subgraph C["Gabungan"]
        C1["verdict()<br/>web/lib/verdict.ts"]
        C2["physics.py<br/>1/(1−BF)²"]
    end

    A9 --> C1
    B8 --> C1
    B5 -.-> C2
    C1 --> D(["Putusan operator"])
    C2 -.->|"tidak ditampilkan"| D
```

> **Garis putus-putus itu bukan hiasan.** Rantai afflux tetap dihitung di
> `src/physics.py`, tetapi **tidak lagi sampai ke layar** — kartu "Perkiraan
> kenaikan muka air" dihapus dari halaman operator, dan kembaran TypeScript-nya
> (`web/lib/fisika.ts`) ikut terhapus. Yang menentukan apa yang dibaca operator
> sekarang hanyalah `verdict()`.
>
> Ini layak disebut karena operator justru meminta **debit air** sebagai
> informasi utama (bagian G2 wawancara), dan perhitungannya sudah ada — hanya
> jalur tampilnya yang belum.

### 3.3b Alur keputusan per bingkai — apa yang benar-benar terjadi tiap putaran

Diagram §3.3 menunjukkan ke mana data mengalir. Diagram ini menunjukkan
**percabangannya**: apa yang diperiksa gelung inferensi pada setiap putaran, dan
kapan sebuah bingkai dilewati tanpa menghasilkan baris.

```mermaid
flowchart TD
    START(["Putaran gelung"]) --> CTRL{"Sudah 0,5 detik<br/>sejak cek kendali?"}
    CTRL -->|ya| POLY["Baca polygons.json<br/>+ control.json"]
    CTRL -->|belum| READ
    POLY --> PCHG{"Poligon<br/>berubah?"}
    PCHG -->|ya| PRESET["masks = None<br/>deret TIDAK direset"]
    PCHG -->|tidak| CSW
    PRESET --> CSW{"Diminta ganti<br/>kamera?"}
    CSW -->|ya| COPEN{"Sumber baru<br/>bisa dibuka?"}
    CSW -->|tidak| READ
    COPEN -->|ya| CRESET["Ganti sumber<br/>reset SELURUH deret"]
    COPEN -->|tidak| CKEEP["Tolak, tetap di kamera lama<br/>catat error ke status.json"]
    CRESET --> READ
    CKEEP --> READ

    READ["cap.read()"] --> OK{"Bingkai<br/>terbaca?"}
    OK -->|tidak| LIVE{"Sumber<br/>langsung?"}
    LIVE -->|tidak — berkas| DONE(["Selesai — video habis"])
    LIVE -->|ya — aliran| RECON["Sambung ulang<br/>jeda 1-2-4-8-16-30 detik"]
    RECON --> RRESET["prev_ts = None<br/>estimator kecepatan direset<br/>masks = None"]
    RRESET --> READ

    OK -->|ya| MASK{"masks<br/>sudah ada?"}
    MASK -->|belum| BUILD["Bangun mask ROI + zona pintu<br/>dari poligon ternormalisasi"]
    MASK -->|sudah| FLOW
    BUILD --> FLOW["Aliran optik<br/>-> kecepatan permukaan"]

    FLOW --> TTHR{"Sudah lewat<br/>trash_interval?"}
    TTHR -->|ya| INFER["SegFormer-B0<br/>segmentasi 640 px"]
    TTHR -->|belum| CACHE["Pakai mask sampah<br/>yang di-cache"]
    INFER --> WTHR{"Sudah lewat<br/>water_interval?"}
    CACHE --> WTHR
    WTHR -->|ya| WUP["Perbarui mask air"]
    WTHR -->|belum| WCACHE["Pakai mask air<br/>yang di-cache"]

    WUP --> HAVE
    WCACHE --> HAVE{"Kedua mask<br/>sudah ada?"}
    HAVE -->|belum| SKIP["Lewati bingkai ini<br/>TIDAK menulis baris"]
    SKIP --> START
    HAVE -->|ya| METRIC["frame_metrics()<br/>coverage, accumulation_frac"]

    METRIC --> MON["BlockageMonitor<br/>ambang + laju tumbuh"]
    MON --> WRITE["Tulis baris observations"]
    WRITE --> PREV["Tulis frame.jpg + mask.jpg<br/>throttle 0,1 detik"]
    PREV --> FLUSH{"Sudah 0,5 detik<br/>sejak commit?"}
    FLUSH -->|ya| COMMIT["sink.flush()"]
    FLUSH -->|belum| START
    COMMIT --> START
```

**Empat keputusan di diagram ini yang tidak terlihat dari kode sepintas:**

**Poligon berubah tidak mereset deret, ganti kamera mereset.** Menggambar ulang
zona pintu hanya memindahkan wilayah yang dihitung pada adegan yang sama, jadi
riwayat penghalusan tetap sebanding. Ganti kamera berarti adegannya benar-benar
lain — seluruh pengukuran terkumpul menjadi tidak berlaku.

**Kamera yang gagal dibuka tidak menjatuhkan gelung.** Permintaan ditolak,
alasannya ditulis ke `status.json`, dan sistem tetap mengukur dengan kamera lama.
Padam karena seseorang salah pilih perangkat adalah kegagalan yang lebih buruk
daripada permintaan yang ditolak.

**Bingkai tanpa mask lengkap dilewati, bukan ditulis nol.** Ini penerapan langsung
aturan "tidak ada pengukuran ≠ nol" pada tingkat gelung.

**Sumber langsung menyambung ulang, berkas berakhir.** Batas waktu baca FFmpeg
tiba di titik yang sama persis dengan akhir video, sehingga keduanya harus
dibedakan dari jenis sumbernya, bukan dari gejalanya.

---

### 3.3c Mesin keadaan level — histeresis dan dwell

`LevelFsm` di firmware bukan sekadar perbandingan ambang. Ia mesin keadaan dengan
dua sifat yang mencegah alarm berkedip.

```mermaid
stateDiagram-v2
    direction LR
    [*] --> AMAN

    AMAN --> WASPADA: h > WASPADA_ENTER (3,0 cm)<br/>atau hujan > 10 mm/jam
    AMAN --> BAHAYA: h > BAHAYA_ENTER (4,5 cm)<br/>atau hujan > 30 mm/jam
    WASPADA --> BAHAYA: h > BAHAYA_ENTER
    BAHAYA --> WASPADA: h < BAHAYA_EXIT (3,5 cm)<br/>DAN bertahan 60 detik
    WASPADA --> AMAN: h < WASPADA_EXIT (2,0 cm)<br/>DAN bertahan 60 detik

    note right of BAHAYA
        Bacaan tidak sah TIDAK PERNAH
        menurunkan status - data hilang
        bukan bukti keadaan aman
    end note
```

| Sifat | Nilai | Kenapa |
|---|---|---|
| Naik | **seketika** | Menunda peringatan banjir tidak bisa dibenarkan |
| Turun — ambang | `EXIT` ≠ `ENTER` | Selisih 1 cm lebih lebar daripada sebaran ±0,5 cm antar-ping, jadi riak di sekitar ambang tidak membalik keadaan |
| Turun — waktu | `DWELL_DOWN_MS` 60 detik | Harus stabil di bawah ambang keluar selama satu menit penuh |
| Bacaan tidak sah | **menahan keadaan** | De-eskalasi saat sensor gagal akan mematikan pompa di tengah banjir |

**Ambang masuk memakai `>` (tegas), ambang keluar memakai `>=`.** Perbedaan satu
karakter itu diuji langsung: nilai tepat di `WASPADA_ENTER` tidak boleh naik
status, dan nilai tepat di `WASPADA_EXIT` masih terhitung WASPADA. Mutasi `>`
menjadi `>=` disuntikkan sengaja dan tertangkap oleh uji batas
([08 §8.4](08-protokol-uji.md)).

---

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

### 3.4b Alur keputusan `/api/ingest` — semua atau tidak sama sekali

Endpoint ini punya aturan yang tidak biasa dan wajib digambarkan, karena
melanggarnya berarti kehilangan data secara permanen: **2xx adalah janji bahwa
setiap baris sudah tersimpan.** Firmware memajukan kursor SD-nya hanya pada 2xx
dan tidak pernah mengirim ulang baris itu.

```mermaid
flowchart TD
    IN(["POST /api/ingest"]) --> J{"Badan berupa<br/>JSON sah?"}
    J -->|tidak| E400A["400 — body is not valid JSON"]
    J -->|ya| DEV{"device ada<br/>dan bukan kosong?"}
    DEV -->|tidak| E400B["400 — device is required"]
    DEV -->|ya| ARR{"rows berupa<br/>larik?"}
    ARR -->|tidak| E400C["400 — rows must be an array"]
    ARR -->|ya| PARSE["Urai SELURUH baris<br/>SEBELUM menyentuh basis data"]

    PARSE --> BAD{"Ada baris<br/>yang gagal urai?"}
    BAD -->|ya| E400D["400 — rows[i]: alasan<br/>NOL baris disimpan"]
    BAD -->|tidak| EMPTY{"Ada baris<br/>yang sah?"}

    EMPTY -->|tidak| OK200A["200 inserted: 0<br/>batch kosong bukan galat"]
    EMPTY -->|ya| TX["Satu transaksi<br/>INSERT OR IGNORE"]
    TX --> LOCK{"Basis data<br/>terkunci?"}
    LOCK -->|ya, >5 detik| E503["503 — firmware mencoba lagi<br/>kursor SD TIDAK maju"]
    LOCK -->|tidak| OK200B["200 inserted: n<br/>kursor SD boleh maju"]

    style E400D fill:#f8d7da,stroke:#842029
    style OK200B fill:#d1e7dd,stroke:#0f5132
```

**Tiga keputusan di diagram ini, semuanya berakar pada satu janji itu:**

**Penguraian selesai sebelum penulisan dimulai.** Satu baris rusak menolak seluruh
batch. Menerima sebagiannya lalu menjawab 2xx akan membuang sisanya selamanya,
karena firmware menganggap seluruh batch sudah aman.

**Batch kosong menjawab 200, bukan 400.** Berkas hanya berisi header bukan
kegagalan — tidak ada yang perlu disimpan, dan tidak ada yang salah.

**Kunci basis data menjawab 503, bukan menunggu selamanya.** Batas tunggu 5 detik
jauh lebih lama daripada penulisan apa pun yang nyata (di bawah satu milidetik),
sehingga penulis yang benar-benar macet muncul sebagai galat yang bisa dicoba
ulang firmware — bukan sebagai permintaan yang menggantung.

**Kirim ulang aman.** Kunci utama `(device, ts_epoch)` membuat `INSERT OR IGNORE`
pada baris yang sudah ada tidak melakukan apa pun; kiriman kedua menjawab
`inserted: 0` dengan status 200. Ini penting karena tanggapan yang hilang di
jaringan tidak bisa dibedakan dari permintaan yang tidak pernah sampai.

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
| Raspberry Pi mati | Aliran video berhenti; tidak ada citra yang tersimpan di Pi | Tinggi air, hujan, SMS | Ya — kartu Penumpukan menua |
| Jaringan Pi → server terputus | Sama; `run.py` menyambung ulang sendiri | Sisanya | Ya, lewat umur data |
| ESP32 | Tinggi air & hujan titik berhenti | Kamera, fisika, putusan | Ya — sumber ditandai sunyi >20 menit |
| WiFi di ESP32 | Unggah tertunda | **Semua** — SD terus mencatat, SMS terus terkirim | Tidak langsung; terlihat dari umur data |
| Ultrasonik | `tinggi_cm` hilang | Hujan, SMS, FSM **menahan** level | Ya — `valid=0` tersimpan |
| Server web mati | Unggah gagal | Firmware & inferensi jalan terus | — |
| `site_geometry.json` hilang | `src/physics.py` tidak bisa dijalankan | Seluruh tampilan web | Hanya di keluaran skrip |
| Tabel `rainfall` belum ada | `src/external/rainfall.py` belum pernah dijalankan | Seluruh tampilan web | Hanya di keluaran skrip |

Dua baris terakhir dulu mengosongkan kartu di halaman operator. Sejak kartu
"Perkiraan kenaikan muka air" dan "Hujan regional" dihapus, keduanya tidak lagi
punya jalur ke layar — fisika afflux dan curah hujan eksternal sekarang murni
sisi Python.

Dua pola yang berulang di tabel ini, dan keduanya disengaja:

1. **Kegagalan bersifat lokal.** Kamera mati tidak menjatuhkan tinggi air, dan
   ESP32 yang sunyi tidak menjatuhkan putusan penyumbatan. Tiap sumber membawa
   umurnya sendiri ke layar, jadi satu yang diam tidak menyeret yang lain.
   **Sumber langsung menyambung ulang, berkas tidak.** `run.py` membedakan
   keduanya lewat `is_live_source()`: berkas video yang habis memang berakhir,
   tetapi aliran MJPEG yang berhenti 30 detik hanyalah tautan yang putus — batas
   waktu baca FFmpeg tiba di titik yang sama persis dengan akhir video. Gelungnya
   kini menyambung ulang dengan jeda menaik 1→2→4→8→16→30 detik alih-alih keluar.
   `[TERUKUR]` 2026-08-28: sumber diputus sengaja, tersambung kembali pada
   percobaan ke-3.

   Yang di-atur ulang saat pulih hanyalah yang dirusak jeda: `prev_ts` (tanpa itu
   `dt` menjadi selama durasi putus, dan kecepatan permukaan runtuh ke ~0 px/detik
   sehingga `area_flux` ikut salah) dan estimator kecepatan (bingkai acuannya dari
   sebelum putus, jadi aliran optik lintas jeda tak bermakna). Penghalus dan
   monitor penyumbatan **dipertahankan** — adegannya sama.

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
