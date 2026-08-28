import { describe, expect, it } from "vitest";
import { AMBANG_MM, kapan, ringkas } from "../lib/bmkg";

const NOW = new Date("2026-08-27T12:00:00Z");

/** Format persis seperti balasan BMKG: spasi, tanpa "T", tanpa "Z". */
const blok = (jam: number, tp: number | null, desc = "Hujan Ringan") => ({
  utc_datetime: new Date(NOW.getTime() + jam * 3_600_000)
    .toISOString()
    .replace("T", " ")
    .replace(".000Z", ""),
  tp,
  weather_desc: desc,
});

describe("ringkas", () => {
  it("finds the earliest block carrying real rain, not drizzle", () => {
    const { hujan } = ringkas(
      [blok(1, AMBANG_MM - 0.1, "Berawan"), blok(4, 3.2, "Hujan Sedang"), blok(7, 9)],
      NOW,
    );
    expect(hujan?.desc).toBe("Hujan Sedang");
    expect(hujan?.jam).toBeCloseTo(4);
  });

  it("keeps a running 3-hour block, drops what is already past", () => {
    expect(ringkas([blok(-1, 5)], NOW).hujan?.jam).toBeCloseTo(-1);
    expect(ringkas([blok(-5, 5)], NOW).hujan).toBeNull();
    expect(ringkas([blok(30, 5)], NOW).hujan).toBeNull();
  });

  it("separates a dry forecast from no forecast at all", () => {
    // 0 mm means BMKG says dry; null means nothing was read. Rendering both as
    // "0 mm" would let the page claim a dry day while the API is down.
    expect(ringkas([blok(3, 0)], NOW).mm24).toBe(0);
    expect(ringkas([blok(3, null)], NOW).mm24).toBeNull();
    expect(ringkas([], NOW).mm24).toBeNull();
  });

  it("survives junk timestamps", () => {
    expect(ringkas([{ utc_datetime: "bukan tanggal", tp: 9 }], NOW).hujan).toBeNull();
    expect(ringkas([{ tp: 9 }], NOW).mm24).toBeNull();
  });
});

describe("kapan", () => {
  it("reads as a warning an operator can act on", () => {
    expect(kapan(-1)).toBe("sedang berlangsung");
    expect(kapan(0.5)).toBe("30 menit lagi");
    expect(kapan(4)).toBe("4 jam lagi");
  });
});
