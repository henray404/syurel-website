"use client";

import { useEffect, useRef, useState } from "react";
import { Icon, type IconName } from "./Icon";
import { PolygonEditor } from "./PolygonEditor";
import { formatCoverage } from "@/lib/verdict";
import { formatRelative } from "@/lib/waktu";

/**
 * The live half of /demo.
 *
 * REPLACES A `<meta http-equiv="refresh">`. A full page reload cannot feel live:
 * it tears down the document, refetches every asset, and blanks the screen
 * between paints. This swaps only the pixels and numbers that changed.
 *
 * IMAGES ARE DOUBLE-BUFFERED. Pointing an <img> at a new URL clears it while the
 * next one downloads, which at 10 fps is a continuous flicker. Each frame is
 * decoded into a detached Image() first and shown only once it has loaded, so
 * the visible <img> always holds a complete picture.
 */
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

export type LatestPayload = {
  esp: { ts_utc: string; tinggi_cm: number | null; mm_per_jam: number | null } | null;
  obs: { ts_utc: string; accumulation_frac: number | null } | null;
  verdict: { state: string; headline: string; detail: string; minutesToThreshold: number | null };
};

/** How often to ask for numbers. The images run on their own, faster, clock. */
const NUMBERS_MS = 500;
/** Matches preview.interval_s (0.1 s) in configs/inference/site_webcam.yaml. */
const FRAME_MS = 100;
/** Device list changes only when hardware is plugged in. No need to rush it. */
const CAMERA_MS = 2000;

export type CameraStatus = {
  active: string | null;
  devices: { index: number; width: number; height: number }[];
  error: string | null;
  running: boolean;
};

function useLiveImage(name: string, everyMs: number) {
  const [src, setSrc] = useState<string | null>(null);
  const busy = useRef(false);

  useEffect(() => {
    let alive = true;
    let timer: ReturnType<typeof setTimeout>;

    const tick = () => {
      // Skip if the previous frame is still downloading. Without this a slow
      // disk read stacks requests until the browser's per-host connection limit
      // is hit, and every image stalls behind the queue.
      if (busy.current) {
        timer = setTimeout(tick, everyMs);
        return;
      }
      busy.current = true;
      const next = `/api/live/${name}?t=${Date.now()}`;
      const img = new Image();
      img.onload = () => {
        busy.current = false;
        if (alive) setSrc(next);
        timer = setTimeout(tick, everyMs);
      };
      img.onerror = () => {
        busy.current = false;
        // Inference stopped. Keep the last good frame rather than blanking, and
        // back off so a dead source is not hammered.
        timer = setTimeout(tick, 2000);
      };
      img.src = next;
    };

    tick();
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [name, everyMs]);

  return src;
}

export function LiveDemo({
  initial,
  initialCamera,
}: {
  initial: LatestPayload;
  initialCamera: CameraStatus;
}) {
  const [data, setData] = useState<LatestPayload>(initial);
  const [now, setNow] = useState<Date | null>(null);
  // Seeded from the server so the first paint already lists the real cameras.
  // Starting from null made the picker flash "Tidak ada kamera" until the first
  // client fetch landed, which reads as a fault rather than as loading.
  const [cam, setCam] = useState<CameraStatus>(initialCamera);
  // What the user picked, before the loop has confirmed it. The <select> shows
  // this so it does not snap back to the old camera while the switch is in
  // flight; it is cleared once status.json agrees.
  const [pending, setPending] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);

  const frame = useLiveImage("frame", FRAME_MS);
  const mask = useLiveImage("mask", FRAME_MS);

  useEffect(() => {
    let alive = true;
    const pull = async () => {
      try {
        const res = await fetch("/api/camera", { cache: "no-store" });
        if (!res.ok || !alive) return;
        const next: CameraStatus = await res.json();
        setCam(next);
        // Drop the optimistic value once the loop reports the same camera, or
        // reports a failure -- either way the truth is now in status.json.
        setPending((p) => (p !== null && (next.active === p || next.error) ? null : p));
      } catch {
        // Server restarting. Keep the last known device list.
      }
    };
    pull();
    const id = setInterval(pull, CAMERA_MS);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  const chooseCamera = async (source: string) => {
    setPending(source);
    try {
      await fetch("/api/camera", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source }),
      });
    } catch {
      setPending(null);
    }
  };

  useEffect(() => {
    let alive = true;
    const pull = async () => {
      try {
        const res = await fetch("/api/latest", { cache: "no-store" });
        if (res.ok && alive) setData(await res.json());
      } catch {
        // Server restarting mid-poll. Keep the last good numbers on screen; the
        // "x detik lalu" line is what tells the operator they are stale.
      }
      if (alive) setNow(new Date());
    };
    pull();
    const id = setInterval(pull, NUMBERS_MS);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  const v = data.verdict;
  const b = BANNER[v.state] ?? BANNER.unknown;
  const frac = data.obs?.accumulation_frac ?? null;

  const panes: { title: string; src: string | null; note: string }[] = [
    { title: "Kamera", src: frame, note: "Frame apa adanya dari webcam." },
    {
      title: "Deteksi model",
      src: mask,
      note: "Merah = sampah, biru = air. Garis putih = ROI, kuning = zona pintu.",
    },
  ];

  return (
    <>
      <section className="banner" style={{ background: b.bg, color: b.fg }}>
        <Icon name={b.icon} size={34} color={b.dot} />
        <div>
          <div className="banner-title">{v.headline}</div>
          <div className="banner-message">{v.detail}</div>
        </div>
      </section>

      <div className="card">
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 12,
            flexWrap: "wrap",
          }}
        >
          <span className="card-title">Kamera</span>
          <select
            className="picker"
            value={pending ?? cam?.active ?? ""}
            disabled={!cam?.running || (cam?.devices.length ?? 0) === 0}
            onChange={(e) => chooseCamera(e.target.value)}
          >
            {cam?.devices.map((d) => (
              <option key={d.index} value={String(d.index)}>
                Kamera {d.index} — {d.width}×{d.height}
              </option>
            ))}
            {/* A camera that is running but was not in the startup probe still
                belongs in the list, or the <select> would show it as blank. */}
            {cam?.active !== null &&
              cam?.active !== undefined &&
              !cam.devices.some((d) => String(d.index) === cam.active) && (
                <option value={cam.active}>Sumber {cam.active}</option>
              )}
            {(cam?.devices.length ?? 0) === 0 && <option value="">Tidak ada kamera</option>}
          </select>

          <button className="picker" onClick={() => setEditing((v) => !v)}>
            {editing ? "Tutup editor" : "Gambar poligon"}
          </button>

          {pending !== null && <span className="hint">Mengganti…</span>}
          {cam?.running === false && <span className="hint">Inference tidak berjalan</span>}
          {cam?.error && (
            <span className="hint" style={{ color: "var(--blocked)" }}>
              {cam.error}
            </span>
          )}
        </div>
        <div className="foot">
          {(cam?.devices.length ?? 0) > 1
            ? "Ganti sumber tanpa menghentikan inference. Pengukuran di-reset karena adegannya berbeda."
            : "Hanya satu kamera terdeteksi saat inference mulai. Colok kamera lain lalu jalankan ulang untuk mendeteksinya."}
        </div>
      </div>

      {editing && <PolygonEditor onClose={() => setEditing(false)} />}

      <div className="grid2">
        {panes.map((p) => (
          <div className="card" key={p.title}>
            <div className="card-title" style={{ marginBottom: 12 }}>
              {p.title}
            </div>
            <div
              style={{
                position: "relative",
                borderRadius: 12,
                overflow: "hidden",
                background: "var(--ground)",
                // 4:3, the webcam's shape. Reserving the box stops the page
                // jumping when the first frame lands.
                aspectRatio: "4 / 3",
              }}
            >
              {p.src === null ? (
                <div
                  className="empty"
                  style={{
                    position: "absolute",
                    inset: 0,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                  }}
                >
                  Menunggu gambar…
                </div>
              ) : (
                // eslint-disable-next-line @next/next/no-img-element -- next/image
                // caches and optimises; this URL changes ten times a second.
                <img
                  src={p.src}
                  alt={p.title}
                  style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
                />
              )}
            </div>
            <div className="foot">{p.note}</div>
          </div>
        ))}
      </div>

      <div className="grid2">
        <div className="card">
          <div className="card-head">
            <div>
              <div className="card-title">Penumpukan</div>
              <div className={`card-value${frac === null ? " absent" : ""}`}>
                {formatCoverage(frac)}
              </div>
            </div>
            <Icon name="layers" size={30} color="var(--watch)" />
          </div>
          <div className="bar-track">
            {frac !== null && (
              <div
                className="bar-fill"
                style={{
                  width: `${Math.min(100, frac * 100)}%`,
                  background: b.dot,
                  transition: "width .3s ease-out",
                }}
              />
            )}
          </div>
          <div className="foot">
            Angka: {(now && formatRelative(data.obs?.ts_utc, now)) ?? "belum ada"}
          </div>
        </div>

        <div className="card">
          <div className="card-head">
            <div>
              <div className="card-title">Tinggi air</div>
              <div className={`card-value${data.esp?.tinggi_cm == null ? " absent" : ""}`}>
                {data.esp?.tinggi_cm == null
                  ? "Tidak terukur"
                  : `${data.esp.tinggi_cm.toFixed(1).replace(".", ",")} cm`}
              </div>
            </div>
            <Icon name="water" size={30} color="var(--blue)" />
          </div>
          <div className="foot">
            Dari ESP32, bukan dari kamera ·{" "}
            {(now && formatRelative(data.esp?.ts_utc, now)) ?? "belum ada"}
          </div>
        </div>
      </div>
    </>
  );
}
