"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { MAX_POINTS, MIN_POINTS, validatePolygons, type Polygon } from "@/lib/polygons";

/**
 * Click-to-draw editor for the ROI and gate-zone polygons.
 *
 * WHY THIS EXISTS. Both polygons ship as placeholders drawn for a 1280x720
 * frame nobody has checked against a real camera, and `structure` is the single
 * polygon that decides whether an alert fires. Editing YAML by hand and
 * restarting to see the result is a loop slow enough that it does not get done.
 *
 * EVERY COORDINATE HERE IS A FRACTION OF THE FRAME. The <img> is fitted to its
 * column by CSS, so its on-screen size matches neither the JPEG nor the camera.
 * Converting a click to a fraction of the element's own box is the only step
 * that stays correct across preview downscaling, browser zoom, and a camera
 * switch mid-draw.
 */
type Which = "roi" | "structure";

const STYLE: Record<Which, { stroke: string; fill: string; label: string; help: string }> = {
  roi: {
    stroke: "#ffffff",
    fill: "rgba(255,255,255,0.12)",
    label: "ROI — permukaan air yang diamati",
    help: "Kelilingi permukaan air. Jangan masukkan langit atau tanggul: pantulan di situ mode kegagalan nomor satu.",
  },
  structure: {
    stroke: "#e8a33d",
    fill: "rgba(232,163,61,0.18)",
    label: "Zona pintu — penentu alarm",
    help: "Gambar permukaan air tepat di depan bukaan pintu, bukan beton pintunya. Hanya poligon inilah yang memicu alarm.",
  },
};

export function PolygonEditor({ onClose }: { onClose: () => void }) {
  const [which, setWhich] = useState<Which>("structure");
  const [roi, setRoi] = useState<Polygon>([]);
  const [structure, setStructure] = useState<Polygon>([]);
  const [status, setStatus] = useState<string | null>("Memuat…");
  const [saving, setSaving] = useState(false);
  const [frameSrc, setFrameSrc] = useState<string | null>(null);
  const boxRef = useRef<HTMLDivElement>(null);

  const current = which === "roi" ? roi : structure;
  const setCurrent = which === "roi" ? setRoi : setStructure;

  // One still frame, grabbed once. A live-updating picture is impossible to
  // trace on -- the thing you are outlining moves under the cursor.
  useEffect(() => {
    setFrameSrc(`/api/live/frame?t=${Date.now()}`);
  }, []);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const res = await fetch("/api/polygons", { cache: "no-store" });
        const data = await res.json();
        if (!alive) return;
        if (data.saved) {
          setRoi(data.roi);
          setStructure(data.structure);
          setStatus("Memuat gambar tersimpan.");
        } else if (data.error) {
          setStatus(`File tersimpan tidak sah: ${data.error}`);
        } else {
          setStatus("Belum ada gambar tersimpan — memakai poligon dari config.");
        }
      } catch {
        if (alive) setStatus("Tidak bisa membaca poligon tersimpan.");
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  const addPoint = useCallback(
    (e: React.MouseEvent<HTMLDivElement>) => {
      const box = boxRef.current;
      if (!box) return;
      const r = box.getBoundingClientRect();
      // Fraction of the element, not of the image's natural size: the element
      // is what the click happened in, and object-fit makes the two differ.
      const x = (e.clientX - r.left) / r.width;
      const y = (e.clientY - r.top) / r.height;
      if (x < 0 || x > 1 || y < 0 || y > 1) return;

      setCurrent((pts) => (pts.length >= MAX_POINTS ? pts : [...pts, [x, y]]));
      setStatus(null);
    },
    [setCurrent],
  );

  const save = async () => {
    const check = validatePolygons({ roi, structure });
    if (!check.ok) {
      // Checked here so the operator gets the reason immediately, and again on
      // the server so a stale tab cannot bypass it.
      setStatus(`Belum bisa disimpan — ${check.error}`);
      return;
    }
    setSaving(true);
    try {
      const res = await fetch("/api/polygons", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(check.polygons),
      });
      const data = await res.json();
      setStatus(
        res.ok
          ? "Tersimpan. Inference memakainya dalam ~1 detik, tanpa restart."
          : `Ditolak server: ${data.error}`,
      );
    } catch (err) {
      setStatus(`Gagal mengirim: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setSaving(false);
    }
  };

  const toPath = (pts: Polygon) =>
    pts.map(([x, y], i) => `${i === 0 ? "M" : "L"} ${x * 100} ${y * 100}`).join(" ");

  return (
    <div className="card">
      <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <span className="card-title">Gambar poligon</span>
        <select className="picker" value={which} onChange={(e) => setWhich(e.target.value as Which)}>
          <option value="structure">Zona pintu</option>
          <option value="roi">ROI</option>
        </select>
        <button className="picker" onClick={() => setCurrent((p) => p.slice(0, -1))}>
          Batal 1 titik
        </button>
        <button className="picker" onClick={() => setCurrent([])}>
          Hapus
        </button>
        <div className="spacer" />
        <button className="picker" onClick={save} disabled={saving}>
          {saving ? "Menyimpan…" : "Simpan"}
        </button>
        <button className="picker" onClick={onClose}>
          Tutup
        </button>
      </div>

      {/* Beside the button that causes it, not under the picture.
          The frame is 4/3 at full card width -- around 850 px tall -- so a status
          line below it sits off-screen from where Simpan was clicked. A refusal
          nobody can see reads exactly like a save that silently failed, and
          "roi: minimal 3 titik" is the common one: BOTH polygons must be valid
          before either can be stored. */}
      {status && (
        <div className="foot" style={{ marginTop: 8, color: "var(--ink)", fontWeight: 600 }}>
          {status}
        </div>
      )}

      <div className="foot" style={{ marginTop: 8, marginBottom: 12 }}>
        {STYLE[which].help}
      </div>

      <div
        ref={boxRef}
        onClick={addPoint}
        style={{
          position: "relative",
          borderRadius: 12,
          overflow: "hidden",
          background: "var(--ground)",
          aspectRatio: "4 / 3",
          cursor: "crosshair",
        }}
      >
        {frameSrc && (
          // eslint-disable-next-line @next/next/no-img-element -- one still frame
          <img
            src={frameSrc}
            alt="Frame untuk digambar"
            style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
          />
        )}

        {/* viewBox 0..100 so the same fractions drive the SVG without knowing the
            element's pixel size. preserveAspectRatio="none" makes the overlay
            stretch exactly like the image under it. */}
        <svg
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
          style={{ position: "absolute", inset: 0, width: "100%", height: "100%" }}
        >
          {(["roi", "structure"] as Which[]).map((key) => {
            const pts = key === "roi" ? roi : structure;
            if (pts.length === 0) return null;
            const active = key === which;
            return (
              <g key={key} opacity={active ? 1 : 0.45}>
                <path
                  d={`${toPath(pts)}${pts.length >= MIN_POINTS ? " Z" : ""}`}
                  fill={pts.length >= MIN_POINTS ? STYLE[key].fill : "none"}
                  stroke={STYLE[key].stroke}
                  strokeWidth={active ? 0.5 : 0.35}
                  vectorEffect="non-scaling-stroke"
                />
                {active &&
                  pts.map(([x, y], i) => (
                    <circle key={i} cx={x * 100} cy={y * 100} r={0.8} fill={STYLE[key].stroke} />
                  ))}
              </g>
            );
          })}
        </svg>
      </div>

      <div className="foot">
        {STYLE[which].label} · {current.length} titik
        {current.length > 0 && current.length < MIN_POINTS && ` (butuh ${MIN_POINTS})`}
        {" · ROI "}
        {roi.length} titik · Zona pintu {structure.length} titik
      </div>
    </div>
  );
}
