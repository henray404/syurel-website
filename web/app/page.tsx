import { getDb } from "@/lib/db";
import { readLatest } from "@/lib/latest";
import { buildNotifications } from "@/lib/notifikasi";
import { formatRelative, formatUntil } from "@/lib/waktu";
import { DEFAULT_AREA_THRESHOLD, formatCoverage, verdict } from "@/lib/verdict";
import { fisika, formatCm, loadSite, type Fisika } from "@/lib/fisika";
import { EMPTY_RAIN, readRainfall, sourceLabel, type RainSummary } from "@/lib/hujan";
import { Icon, type IconName } from "@/components/Icon";
import { Shell } from "@/components/Shell";

export const dynamic = "force-dynamic";
export const revalidate = 0;

const BANNER: Record<string, { icon: IconName; bg: string; fg: string; dot: string }> = {
  clear: { icon: "check", bg: "var(--clear-bg)", fg: "var(--clear-fg)", dot: "var(--clear)" },
  watch: { icon: "warning", bg: "var(--watch-bg)", fg: "var(--watch-fg)", dot: "var(--watch)" },
  blocked: {
    icon: "block",
    bg: "var(--blocked-bg)",
    fg: "var(--blocked-fg)",
    dot: "var(--blocked)",
  },
  unknown: {
    icon: "help",
    bg: "var(--unknown-bg)",
    fg: "var(--unknown-fg)",
    dot: "var(--unknown)",
  },
};

/**
 * A measurement, or the words for its absence -- never a zero.
 *
 * metrics.py returns None rather than 0.0 on purpose: 0.0 reads as "clean
 * river", which is exactly wrong during a flood.
 */
function reading(v: number | null | undefined, unit: string) {
  if (v === null || v === undefined || !Number.isFinite(v)) {
    return { text: "Tidak terukur", absent: true };
  }
  return { text: `${v.toFixed(1).replace(".", ",")} ${unit}`, absent: false };
}

function mm(v: number | null): string {
  return v === null || !Number.isFinite(v)
    ? "tidak terukur"
    : `${v.toFixed(1).replace(".", ",")} mm`;
}

export default function OperatorPage() {
  const db = getDb();
  const latest = readLatest(db);
  const v = verdict(latest.obs);
  const now = new Date();
  const b = BANNER[v.state];

  // Each optional block fails on its own. A missing site config or an absent
  // rainfall table must not take down the water level and the verdict.
  let fis: Fisika | null = null;
  try {
    fis = fisika(latest.obs?.accumulation_frac ?? null, loadSite());
  } catch {
    fis = null;
  }
  let rain: RainSummary = EMPTY_RAIN;
  try {
    rain = readRainfall(db, now);
  } catch {
    rain = EMPTY_RAIN;
  }

  const water = reading(latest.esp?.tinggi_cm, "cm");
  const hujanSensor = reading(latest.esp?.mm_per_jam, "mm/jam");
  const frac = latest.obs?.accumulation_frac ?? null;
  const espAge = formatRelative(latest.esp?.ts_utc, now) ?? "belum ada data";
  const camAge = formatRelative(latest.obs?.ts_utc, now) ?? "belum ada data";
  const notifications = buildNotifications(latest, v, now);

  return (
    <Shell
      active="operator"
      rail={
        <div className="card">
          <div className="rail-title">Notifikasi</div>
          {notifications.map((n, i) => (
            <div className="notif" key={i}>
              <span className="notif-dot" style={{ background: `var(--${n.color})` }} />
              <div>
                <div className="notif-text">{n.text}</div>
                <div className="notif-time">{n.time}</div>
              </div>
            </div>
          ))}
        </div>
      }
    >
      {/* The page refreshes itself: a gatehouse screen is left open for hours,
          and a stale number under a live clock is a trap. */}
      <meta httpEquiv="refresh" content="30" />

      <section className="banner" style={{ background: b.bg, color: b.fg }}>
        <Icon name={b.icon} size={34} color={b.dot} />
        <div>
          <div className="banner-title">{v.headline}</div>
          <div className="banner-message">{v.detail}</div>
          {v.minutesToThreshold !== null && (
            <div className="banner-message" style={{ opacity: 1, fontWeight: 700 }}>
              Perkiraan mencapai ambang dalam {Math.round(v.minutesToThreshold)} menit.
            </div>
          )}
        </div>
      </section>

      <div className="grid2">
        <div className="card">
          <div className="card-head">
            <div>
              <div className="card-title">Tinggi air</div>
              <div className={`card-value${water.absent ? " absent" : ""}`}>{water.text}</div>
            </div>
            <Icon name="water" size={30} color="var(--blue)" />
          </div>
          <div className="foot">Sensor ultrasonik · {espAge}</div>
        </div>

        <div className="card">
          <div className="card-head">
            <div>
              <div className="card-title">Curah hujan</div>
              <div className={`card-value${hujanSensor.absent ? " absent" : ""}`}>
                {hujanSensor.text}
              </div>
            </div>
            <Icon name="rain" size={30} color="#6fa8dc" />
          </div>
          <div className="foot">Tipping bucket di lokasi · {espAge}</div>
        </div>
      </div>

      <div className="card">
        <div className="card-head" style={{ alignItems: "center" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <Icon name="layers" size={22} color="var(--muted)" />
            <span className="card-title">Penumpukan</span>
          </div>
          <span
            style={{
              fontSize: 15,
              fontWeight: 800,
              color: frac === null ? "var(--faint)" : undefined,
              fontStyle: frac === null ? "italic" : undefined,
            }}
          >
            {formatCoverage(frac)}
          </span>
        </div>
        <div className="bar-track">
          {/* No bar at all when nothing was measured. A zero-width bar and a bar
              at 0% look identical, and one of them is a lie. */}
          {frac !== null && (
            <div
              className="bar-fill"
              style={{ width: `${Math.min(100, frac * 100)}%`, background: b.dot }}
            />
          )}
        </div>
        <div className="foot">
          Ambang {formatCoverage(DEFAULT_AREA_THRESHOLD)} · Kamera: {camAge} · disegarkan tiap 30
          detik
        </div>
      </div>

      {/* --- physics ------------------------------------------------------ */}
      {fis && (
        <div className="card">
          <div className="card-head" style={{ alignItems: "center" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <Icon name="monitoring" size={22} color="var(--muted)" />
              <span className="card-title">Perkiraan kenaikan muka air</span>
            </div>
            {!fis.calibrated && <span className="badge-warn">BELUM DIKALIBRASI</span>}
          </div>

          <div className="grid3" style={{ marginTop: 14 }}>
            <div>
              <div className="foot" style={{ marginTop: 0 }}>
                Afflux (batas atas)
              </div>
              <div className={`card-value${fis.affluxM === null ? " absent" : ""}`}>
                {fis.beyondModel ? "Di luar model" : formatCm(fis.affluxM)}
              </div>
            </div>
            <div>
              <div className="foot" style={{ marginTop: 0 }}>
                Sisa ke jalan
              </div>
              <div className={`card-value${fis.marginToRoadM === null ? " absent" : ""}`}>
                {formatCm(fis.marginToRoadM)}
              </div>
            </div>
            <div>
              <div className="foot" style={{ marginTop: 0 }}>
                Jalan tergenang di
              </div>
              <div className={`card-value${fis.criticalBf === null ? " absent" : ""}`}>
                {fis.criticalBf === null ? "tidak terhitung" : formatCoverage(fis.criticalBf)}
              </div>
            </div>
          </div>

          <div className="foot">
            {/* "Batas atas", not "kenaikan": this is ARR's Reduced Area Method,
                which ARR says overestimates head for blockage at the entrance
                -- 28% high in their worked 50% case. Conservative is the right
                side to err on for a flood warning, but it has to be said.
                docs/referensi_fisika.md */}
            h/h₀ = 1/(1−BF)² · orifis USBR (Cd 0,61) · metode luas-tereduksi ARR, condong
            berlebih · docs/referensi_fisika.md
            {!fis.calibrated && (
              <>
                {" · "}
                <strong>
                  Ukuran pintu masih tebakan. Isi configs/site_geometry.json setelah survei —
                  kesalahan BF dikuadratkan di sini.
                </strong>
              </>
            )}
          </div>
        </div>
      )}

      {/* --- external rainfall --------------------------------------------- */}
      <div className="card">
        <div className="card-head" style={{ alignItems: "center" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <Icon name="rain" size={22} color="var(--muted)" />
            <span className="card-title">Hujan regional (API eksternal)</span>
          </div>
          <span className="hint">{sourceLabel(rain.forecastSource)}</span>
        </div>

        {rain.available ? (
          <>
            <div className="grid3" style={{ marginTop: 14 }}>
              <div>
                <div className="foot" style={{ marginTop: 0 }}>
                  24 jam terakhir
                </div>
                <div className={`card-value${rain.mm24h === null ? " absent" : ""}`}>
                  {mm(rain.mm24h)}
                </div>
              </div>
              <div>
                <div className="foot" style={{ marginTop: 0 }}>
                  Prakiraan 24 jam
                </div>
                <div className={`card-value${rain.mmNext24h === null ? " absent" : ""}`}>
                  {mm(rain.mmNext24h)}
                </div>
              </div>
              <div>
                <div className="foot" style={{ marginTop: 0 }}>
                  Hujan berikutnya
                </div>
                <div className={`card-value${rain.nextRainTs === null ? " absent" : ""}`}>
                  {/* formatUntil, not formatRelative: this timestamp is in the
                      future by design, and formatRelative clamps the future to
                      "baru saja" to absorb device clock skew. */}
                  {rain.nextRainTs
                    ? (formatUntil(rain.nextRainTs, now) ?? "—")
                    : "tak ada dalam prakiraan"}
                </div>
              </div>
            </div>
            <div className="foot">
              {/* Not a courtesy: BMKG requires attribution to be displayed, and
                  the grid caveat is what stops these numbers being read as the
                  rainfall at the gate. */}
              Sumber: BMKG dan Open-Meteo (ERA5). Petak 9–25 km, sedangkan sel hujan tropis 2–5 km —
              ini <strong>sinyal regional</strong>, bukan hujan di bendungan. Angka lokal yang sahih
              datang dari tipping bucket di kartu atas.
            </div>
          </>
        ) : (
          <p className="empty">
            Belum ada data. Isi <code>site.lat</code>, <code>site.lon</code>, dan{" "}
            <code>site.adm4</code> di <code>configs/site_geometry.json</code>, lalu jalankan:
            <br />
            <code>PYTHONPATH=src python -m external.rainfall --db out/webcam/timeseries.sqlite</code>
          </p>
        )}
      </div>
    </Shell>
  );
}
