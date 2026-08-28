import { getDb } from "@/lib/db";
import { kapan, prakiraan, WARN_JAM } from "@/lib/bmkg";
import { readLatest } from "@/lib/latest";
import { buildNotifications } from "@/lib/notifikasi";
import { formatRelative } from "@/lib/waktu";
import { DEFAULT_AREA_THRESHOLD, formatCoverage, verdict } from "@/lib/verdict";
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

/** Satu baris prakiraan BMKG. warn = hujan cukup dekat untuk bersiap. */
function garisHujan(p: Awaited<ReturnType<typeof prakiraan>>) {
  if (p.status === "mati") return { teks: "Wilayah belum diatur", warn: false };
  if (p.status === "gagal") return { teks: "BMKG tidak terhubung", warn: false };
  if (p.hujan === null) {
    return { teks: p.mm24 === null ? "Tidak ada data" : "Tidak ada hujan", warn: false };
  }
  return { teks: `${p.hujan.desc} ${kapan(p.hujan.jam)}`, warn: p.hujan.jam <= WARN_JAM };
}

export default async function OperatorPage() {
  const db = getDb();
  const latest = readLatest(db);
  const v = verdict(latest.obs);
  const now = new Date();
  const b = BANNER[v.state];
  const hujanBMKG = garisHujan(await prakiraan(now));

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

      {/* Prakiraan, bukan pengukuran: dipisah dari kartu sensor supaya operator
          tidak pernah membacanya sebagai hujan yang sedang turun di bendungan. */}
      <div
        className="card"
        style={
          hujanBMKG.warn
            ? { background: "var(--watch-bg)", color: "var(--watch-fg)" }
            : undefined
        }
      >
        <div className="card-head" style={{ alignItems: "center" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <Icon name="rain" size={22} color={hujanBMKG.warn ? "var(--watch)" : "var(--muted)"} />
            <span className="card-title">
              {hujanBMKG.warn ? "Hujan diperkirakan turun" : "Prakiraan hujan"}
            </span>
          </div>
          <span style={{ fontSize: 15, fontWeight: 800 }}>{hujanBMKG.teks}</span>
        </div>
        {/* Atribusi BMKG syarat pakai, bukan sopan santun -- ini tidak boleh
            ikut dipangkas selama angka BMKG tampil di layar. */}
        <div className="foot" style={hujanBMKG.warn ? { color: "inherit", opacity: 0.85 } : undefined}>
          Sumber: BMKG
        </div>
      </div>

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
    </Shell>
  );
}
