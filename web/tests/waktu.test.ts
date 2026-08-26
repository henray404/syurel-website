import { describe, expect, it } from "vitest";
import { formatJam, formatRelative, formatTanggal, formatUntil, parseUtc } from "../lib/waktu";

const NOW = new Date("2026-08-23T12:00:00Z");

describe("formatRelative", () => {
  it("returns null without a timestamp, so callers can say 'belum ada data'", () => {
    expect(formatRelative(null, NOW)).toBeNull();
    expect(formatRelative(undefined, NOW)).toBeNull();
    expect(formatRelative("", NOW)).toBeNull();
    expect(formatRelative("bukan tanggal", NOW)).toBeNull();
  });

  it("scales the unit with the gap", () => {
    expect(formatRelative("2026-08-23T11:59:58Z", NOW)).toBe("baru saja");
    expect(formatRelative("2026-08-23T11:59:18Z", NOW)).toBe("42 detik lalu");
    expect(formatRelative("2026-08-23T11:55:00Z", NOW)).toBe("5 menit lalu");
    expect(formatRelative("2026-08-23T10:00:00Z", NOW)).toBe("2 jam lalu");
    expect(formatRelative("2026-08-20T12:00:00Z", NOW)).toBe("3 hari lalu");
  });

  it("does not render a negative age when the device clock runs fast", () => {
    // The ESP32 sets its clock over NTP and can land ahead of this laptop.
    // "-3 detik lalu" would read as a bug in the dashboard.
    expect(formatRelative("2026-08-23T12:00:03Z", NOW)).toBe("baru saja");
  });
});

describe("formatUntil", () => {
  it("counts forward for a forecast", () => {
    // Regression: a forecast run through formatRelative rendered as "baru
    // saja", which reads as if tomorrow's rain were already falling.
    expect(formatUntil("2026-08-23T17:00:00Z", NOW)).toBe("dalam 5 jam");
    expect(formatUntil("2026-08-23T12:30:00Z", NOW)).toBe("dalam 30 menit");
    expect(formatUntil("2026-08-25T12:00:00Z", NOW)).toBe("dalam 2 hari");
  });

  it("says a past forecast window is happening now, not negative", () => {
    expect(formatUntil("2026-08-23T11:00:00Z", NOW)).toBe("sedang berlangsung");
  });

  it("returns null without a timestamp", () => {
    expect(formatUntil(null, NOW)).toBeNull();
    expect(formatUntil("bukan tanggal", NOW)).toBeNull();
  });
});

describe("parseUtc", () => {
  it("reads the format sink.py writes", () => {
    expect(parseUtc("2026-08-23T08:36:26Z")?.toISOString()).toBe("2026-08-23T08:36:26.000Z");
  });
});

describe("Indonesian date and time", () => {
  it("names the day and month in Indonesian", () => {
    // Constructed in local time so the weekday cannot flip on a UTC offset.
    expect(formatTanggal(new Date(2026, 7, 23))).toBe("Minggu, 23 Agustus 2026");
  });

  it("zero-pads the clock", () => {
    expect(formatJam(new Date(2026, 7, 23, 9, 5, 3))).toBe("09:05:03");
  });
});
