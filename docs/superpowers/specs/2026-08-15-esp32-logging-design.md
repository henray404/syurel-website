# ESP32 flood station — logging and reliability redesign

Date: 2026-08-15
Status: design approved, not yet implemented
Scope: **firmware only**. The receiving server and the water-level prediction
model are separate projects with their own specs.

---

## 1. Why

`esp32.ino` v1.4 works as an alarm but stores nothing. Everything goes to
`Serial.print`, so when no laptop is attached the data is gone permanently.

That matters more than it looks. River stage and rainfall at *this* site are the
only inputs to the planned water-level model that **cannot be downloaded later** —
IMERG, ERA5 and BMKG all have archives; this river does not. Every day the
station runs without logging is a day of training data that can never be
recovered.

A review of the existing firmware also found six defects that would corrupt that
data or cause false alarms. They are fixed here, because logging bad data is not
much better than logging nothing.

## 2. Constraints

- Device is a **bench prototype**, so full restructuring is allowed.
- SD card module and RTC are **not yet purchased** (~Rp 40–60k total).
- Transport is **WiFi via a 4G MiFi at the site**, not GPRS. SIM800L is 2G-only
  and Indonesian 2G is being retired operator-by-operator with no fixed national
  date `[Low confidence — sources conflict; verify empirically with AT+CREG?]`.
  Betting both the data path and the alarm path on 2G is a single point of
  failure, so SIM800L is retained for **SMS alerts only**.
- No RTOS. The workload does not need it, and it adds race conditions and stack
  problems that are hard to debug on a device deployed by a riverbank.

## 3. Architecture

Non-blocking `millis()` scheduler replacing `delay(5000)`. Modules with one job
each:

| module | responsibility |
|---|---|
| `config.h` | pins, thresholds, credentials, calibration constants |
| `timekeeping` | DS3231 + NTP sync, UTC only |
| `sensors` | ultrasonic median read, rain-gauge ISR + rolling window |
| `logger` | SD card, one CSV per day |
| `uploader` | WiFi, batched POST, backlog pointer |
| `alerts` | level state machine with hysteresis, SMS with verification |

Schedule:

| task | period |
|---|---|
| read sensors | 5 s |
| write log row | 60 s |
| upload batch | 5 min |
| NTP resync | 6 h |

**Key consequence of the ISR fix:** once the rain ISR increments a counter
instead of setting a boolean, the 4.1 s blocking SMS send can no longer lose rain
tips. That removes the main argument for an RTOS.

## 4. Timekeeping

Wrong timestamps make the whole archive unjoinable with BMKG/IMERG rainfall, so
this is the foundation, not a detail.

- **DS3231 is the source of truth** — survives power loss.
- **NTP corrects RTC drift** whenever WiFi is available.
- Every row carries `time_src` in `rtc` | `ntp` | `none`.
- If both fail the station **still logs**, marked `time_src=none`. Not refusing to
  write, and not silently writing a fabricated time. Data with known-doubtful
  timestamps is still usable; data with silently-wrong ones is poison.
- **All times UTC.** Asia/Jakarta is UTC+7 with no DST, which makes local
  timestamps look harmless right up until they are joined against a UTC rainfall
  series and every correlation is quietly shifted seven hours. Same rule as the
  camera pipeline (`src/inference/sink.py`).

## 5. Sensors

### 5.1 Ultrasonic (JSN-SR04T)

Read every 5 s, **median of 5 samples**. Median not mean: one wild reflection off
a ripple drags a mean but barely moves a median.

Three outcomes kept distinct rather than collapsed into a number:

| condition | v1.4 behaviour | new behaviour |
|---|---|---|
| normal | height in cm | height, `valid=1` |
| echo timeout | returns `-1` | `valid=0`, reason `timeout` |
| water above sensor | **clamped to 0** | `valid=0`, reason `too_close` |

The third row is a dangerous inversion in v1.4: water rising past the sensor reads
as **0 cm = safe**, which is the worst possible failure direction.

**Physical limit to design around:** JSN-SR04T has a blind zone of roughly 25 cm.
`JARAK_DASAR` must be chosen so the BAHAYA threshold is crossed *before* water
enters that zone, otherwise the sensor goes blind exactly during a flood.

### 5.2 Rain gauge

```c
void IRAM_ATTR onTip() {
  uint32_t now = micros();
  if (now - lastTipUs > 250000) {   // 250 ms debounce
    tipCount++;
    lastTipUs = now;
  }
}
```

Fixes two defects at once:

- v1.4's ISR set `flag = true`, and `prosesRainGauge()` ran once per loop. With
  `delay(5000)` plus a 4.1 s blocking SMS, **every tip inside a ~9 s window was
  counted as one** — undercounting hardest during heavy rain and active alerts,
  precisely when accuracy matters most.
- No debounce meant reed-switch bounce could double-count.

**Intensity** uses a rolling 60-minute window (60 one-minute bins), replacing
`tip_per_menit * mm_per_tip * 60`. That extrapolation reports 36 mm/h for two tips
in a minute, so the 30 mm/h threshold fires on a splash.

## 6. Alerts and pump control

### Hysteresis

| state | enter | exit |
|---|---|---|
| WASPADA | > 30 cm | < 25 cm |
| BAHAYA | > 60 cm | < 55 cm |

v1.4 uses one threshold for both, so water rippling around 30 cm flips the state
repeatedly — relay chatter that damages the contactor and the pump.

**Minimum dwell 60 s before de-escalating.** Escalation is immediate;
de-escalation must be stable first. Deliberately asymmetric: safety must not wait.

### Pump

Driven on **state change**, not every loop iteration.

**Behaviour deliberately unchanged:** the pump still activates automatically at
WASPADA. Only hysteresis is added. Whether the pump should instead be manual or
require confirmation is the operator's call, not a decision to smuggle into a
refactor.

### SMS

- Rate limit applies to **all** states including the return to AMAN. v1.4 leaves
  AMAN unlimited, which combined with oscillation means repeated SMS and real
  airtime cost.
- SIM800L response is **checked** for `OK`/`ERROR`. v1.4 prints `[SMS] Terkirim`
  unconditionally — a false confirmation on a safety system when the SIM has no
  credit or no signal.
- Send result is recorded in the log, so silent failures are visible afterwards.

## 7. Logging

**SD is the source of truth; upload is a convenience.** Rows are never deleted
after sending — a pointer advances, the file stays.

**One file per day**, `/data/YYYY-MM-DD.csv`. A corrupt file costs one day, not
the archive.

**One row per minute** — standard hydrological resolution, and enough for the
5/10/30/60-minute lag features the prediction model needs.

```
ts_utc,ts_epoch,jarak_cm,tinggi_cm,valid,n_sampel,tip_total,tip_menit,mm_per_jam,level,pompa,time_src,rssi,sms_status
2026-08-15T07:04:00Z,1786518240,71.2,28.8,1,12,145,0,0.0,AMAN,0,rtc,-67,
```

`tinggi_cm` is the **median of the 12 readings** taken during that minute, and
`n_sampel` reports how many were valid — so "12 of 12 valid" is distinguishable
from "2 of 12", making data quality part of the record.

### Raw measurements only, no derived features

Rate of rise, acceleration, and distance-to-threshold are **not** logged. They are
all recomputable from the raw series, and if their definition later changes
(different window, different smoothing) they can be recomputed for the entire
history. Baked into firmware, changing them would break comparability with all
previously collected data. Firmware records what it measured; features are built
at training time.

### Storage

~100 bytes/row x 1440 rows/day = **144 KB/day, ~52 MB/year**. An 8 GB card holds
over a century.

## 8. Upload

- Batched JSON POST every 5 minutes to a single endpoint.
- A small state file records the last successfully-sent position.
- Server down or WiFi lost -> pointer does not advance, rows accumulate on SD, and
  they are sent later.
- **There is no path where a network failure loses data.**

Contract (server spec'd separately):

```json
POST /ingest
{"device": "esp32-01",
 "rows": [{"ts": "2026-08-15T07:04:00Z", "tinggi_cm": 28.8, "valid": 1,
           "tip_menit": 0, "mm_per_jam": 0.0, "level": "AMAN", "pompa": 0}]}
```

## 9. Hardware to buy

| item | why |
|---|---|
| Micro SD SPI module | storage |
| DS3231 RTC | without it, timestamps are meaningless after a power cycle |
| 4G MiFi / router at site | upload transport; also solves camera connectivity later |

DS3231 over DS1307: better accuracy for a negligible price difference.

## 10. Honest gaps

- **Thresholds are invented.** 30/60 cm and `JARAK_DASAR=100` are placeholders
  until surveyed at the site. Clean hysteresis over wrong numbers is still wrong.
- **2G status unverified.** Test `AT+CREG?` / `AT+CSQ` with the actual SIM at the
  actual location. If SMS cannot register, the alert path needs rethinking, and
  that is a bigger finding than anything in this document.
- **The phone number is hardcoded** in v1.4 line 27 and the file sits in a git
  repo. Move it to `config.h` and keep that file out of version control.
- **No power design here.** Mains? Battery? Solar? A logger that dies in a
  blackout misses exactly the flood it was installed for. Needs its own decision.
- **No enclosure / IP rating considered.** Riverbank, tropical humidity.
- Server and prediction model are out of scope by agreement.
