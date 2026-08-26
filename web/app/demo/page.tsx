import { readFile, stat } from "node:fs/promises";
import path from "node:path";
import { getDb } from "@/lib/db";
import { readLatest } from "@/lib/latest";
import { verdict } from "@/lib/verdict";
import { LIVE_DIR } from "@/lib/live";
import { Shell } from "@/components/Shell";
import { LiveDemo, type CameraStatus, type LatestPayload } from "@/components/LiveDemo";

export const dynamic = "force-dynamic";
export const revalidate = 0;

async function hasPreview(): Promise<boolean> {
  try {
    await stat(path.join(LIVE_DIR, "frame.jpg"));
    return true;
  } catch {
    return false;
  }
}

/** Read here rather than letting the client fetch it, so the picker is already
 *  populated on the first paint instead of flashing "Tidak ada kamera". */
async function cameraStatus(): Promise<CameraStatus> {
  try {
    const raw = await readFile(path.join(LIVE_DIR, "status.json"), "utf-8");
    return { ...JSON.parse(raw), running: true } as CameraStatus;
  } catch {
    return { active: null, devices: [], error: null, running: false };
  }
}

export default async function DemoPage() {
  const latest = readLatest(getDb());
  const [ready, camera] = await Promise.all([hasPreview(), cameraStatus()]);

  // Rendered once on the server so the first paint already carries real numbers;
  // LiveDemo takes over from there and keeps them moving without a reload.
  const initial: LatestPayload = {
    esp: latest.esp
      ? {
          ts_utc: latest.esp.ts_utc,
          tinggi_cm: latest.esp.tinggi_cm,
          mm_per_jam: latest.esp.mm_per_jam,
        }
      : null,
    obs: latest.obs
      ? { ts_utc: latest.obs.ts_utc, accumulation_frac: latest.obs.accumulation_frac }
      : null,
    verdict: verdict(latest.obs),
  };

  return (
    <Shell active="demo">
      {ready ? (
        <LiveDemo initial={initial} initialCamera={camera} />
      ) : (
        <div className="card">
          <div className="card-title">Belum ada gambar</div>
          <p className="empty">
            Preview ditulis oleh proses inference, bukan oleh browser. Jalankan:
          </p>
          <pre
            style={{
              background: "var(--ground)",
              padding: "12px 14px",
              borderRadius: 10,
              overflowX: "auto",
              fontSize: 13,
            }}
          >
            {"PYTHONPATH=src ./.venv/Scripts/python.exe -m inference.run \\\n" +
              "    --config configs/inference/site_webcam.yaml --source 0"}
          </pre>
          <p className="empty">
            Config itu punya <code>preview.enabled: true</code>. Tanpa itu angka tetap tersimpan,
            tapi tidak ada gambar yang ditulis.
          </p>
        </div>
      )}
    </Shell>
  );
}
