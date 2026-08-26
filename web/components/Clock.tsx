"use client";

import { useEffect, useState } from "react";
import { formatJam, formatTanggal } from "@/lib/waktu";

/**
 * The header clock from the design.
 *
 * Client-only, and deliberately blank on the server: the server's second and
 * the browser's second are never the same, and React treats that as a
 * hydration error. This clock is the laptop's own wall time -- the timestamps
 * beside each reading come from the devices, and are rendered separately.
 */
export function Clock() {
  const [now, setNow] = useState<Date | null>(null);

  useEffect(() => {
    setNow(new Date());
    const id = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(id);
  }, []);

  if (now === null) {
    // Reserve the space so the header does not jump on hydration.
    return (
      <>
        <span className="clock" style={{ visibility: "hidden" }}>
          00:00:00
        </span>
        <span className="clock-date" style={{ visibility: "hidden" }}>
          &nbsp;
        </span>
      </>
    );
  }

  return (
    <>
      <span className="clock">{formatJam(now)}</span>
      <span className="clock-date">{formatTanggal(now)}</span>
    </>
  );
}
