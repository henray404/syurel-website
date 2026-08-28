# Web monitoring

Dashboard, and the ingest endpoint the ESP32 firmware posts to.

- Kebutuhan produk: [`../docs/prd_web_monitoring.md`](../docs/prd_web_monitoring.md)
- Arsitektur dan kontrak: [`../docs/laporan/03-arsitektur.md`](../docs/laporan/03-arsitektur.md)

## Running

```bash
cd web
npm install
npm run dev        # http://127.0.0.1:8000
```

Reads `../out/timeseries.sqlite`, the same file `src/inference/sink.py` writes.
Override with `SYURELL_DB`.

The camera half of the dashboard stays empty until inference has run:

```bash
PYTHONPATH=src ./.venv/Scripts/python.exe -m inference.run \
    --config configs/inference/site_bendungan.yaml --source <video>
```

Until then the page reads "tidak terukur" — which is correct, not a bug. See
"The rules" below.

## Pointing the ESP32 at it

Set `INGEST_URL` in `firmware/esp32/include/config_secrets.h` to the host
machine's LAN address — `http://<host-ip>:8000/api/ingest`. Not `localhost`:
the ESP32 resolves that name itself, where it means the ESP32.

Check it end to end:

```bash
curl -s -X POST http://127.0.0.1:8000/api/ingest \
  -H "Content-Type: application/json" \
  -d '{"device":"esp32-01","rows":[{"csv":"2026-08-20T10:30:00Z,1787654321,45.2,154.8,1,12,340,2,4.8,NORMAL,0,ntp,-67,ok"}]}'
```

Send it twice: the second call returns `"inserted":0` and still 200. That is the
idempotency the firmware relies on.

## The rules

Two things that make this dangerous rather than merely imperfect if broken.

**`/api/ingest` replies 2xx only when every row is stored.** The firmware
advances its SD cursor on 2xx and never re-sends those rows. On any failure it
must return non-2xx so the firmware retries. One malformed row rejects the whole
batch — accepting part of it and replying 2xx would discard the rest for good.

**A value that could not be measured is never rendered as 0.**
`src/inference/metrics.py` returns `None` rather than `0.0` on purpose: `0.0`
reads as "clean river", which is exactly wrong during a flood. The web shows
"tidak terukur".

## Layout

```
lib/          framework-free logic, unit-tested
  db.ts         opens the SQLite file, owns esp_readings
  esp-csv.ts    parses the firmware's CSV rows
  ingest.ts     inserts a batch, idempotently
  join.ts       pairs ESP and camera rows on a time window
  verdict.ts    turns the latest observation into what the operator is told
  latest.ts     newest row from each side
app/          Next.js routes and pages
  api/ingest    POST — the only write endpoint
  api/latest    GET  — newest state plus the verdict
  page.tsx      the operator page
```

The page's markup is deliberately plain: the visual design is done separately,
and `lib/verdict.ts` owns what is actually said, so restyling cannot change the
message.

## Tests

```bash
npm test
```
