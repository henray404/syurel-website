import { getDb } from "@/lib/db";
import { readLatest } from "@/lib/latest";
import { verdict, formatCoverage } from "@/lib/verdict";

export const dynamic = "force-dynamic";
export const revalidate = 0;

const STATE_COLOR: Record<string, string> = {
  clear: "var(--clear)",
  watch: "var(--watch)",
  blocked: "var(--blocked)",
  unknown: "var(--unknown)",
};

function num(v: number | null | undefined, unit: string): string {
  return v === null || v === undefined || !Number.isFinite(v)
    ? "tidak terukur"
    : `${v.toFixed(1)} ${unit}`;
}

export default function OperatorPage() {
  const latest = readLatest(getDb());
  const v = verdict(latest.obs);

  const cards = [
    { label: "Tinggi air", value: num(latest.esp?.tinggi_cm, "cm") },
    { label: "Curah hujan", value: num(latest.esp?.mm_per_jam, "mm/jam") },
    { label: "Penumpukan", value: formatCoverage(latest.obs?.accumulation_frac ?? null) },
  ];

  return (
    <main style={{ maxWidth: "60rem", margin: "0 auto", padding: "2rem 1.5rem" }}>
      {/* Plain markup on purpose: the visual design is done separately in
          Claude Design, and lib/verdict.ts owns what is actually said. */}
      <meta httpEquiv="refresh" content="30" />

      <h1 style={{ fontSize: "1.1rem", fontWeight: 600, color: "var(--soft)" }}>
        Pemantauan pintu air
      </h1>

      <section
        style={{
          background: "var(--surface)",
          border: "1px solid var(--rule)",
          borderTop: `4px solid ${STATE_COLOR[v.state]}`,
          padding: "1.5rem",
          marginBottom: "1.5rem",
        }}
      >
        <div style={{ fontSize: "2rem", fontWeight: 700, lineHeight: 1.2 }}>{v.headline}</div>
        <p style={{ color: "var(--soft)", margin: "0.5rem 0 0" }}>{v.detail}</p>
        {v.minutesToThreshold !== null && (
          <p style={{ color: "var(--watch)", fontWeight: 600, margin: "0.5rem 0 0" }}>
            Perkiraan mencapai ambang dalam {Math.round(v.minutesToThreshold)} menit.
          </p>
        )}
      </section>

      <section style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "1rem" }}>
        {cards.map((c) => (
          <div
            key={c.label}
            style={{
              background: "var(--surface)",
              border: "1px solid var(--rule)",
              padding: "1rem",
            }}
          >
            <div style={{ fontSize: "0.8rem", color: "var(--soft)" }}>{c.label}</div>
            <div style={{ fontSize: "1.6rem", fontWeight: 700 }}>{c.value}</div>
          </div>
        ))}
      </section>

      <p style={{ color: "var(--soft)", fontSize: "0.85rem", marginTop: "1.5rem" }}>
        Sensor: {latest.esp?.ts_utc ?? "belum ada data"} · Kamera:{" "}
        {latest.obs?.ts_utc ?? "belum ada data"}
      </p>
    </main>
  );
}
