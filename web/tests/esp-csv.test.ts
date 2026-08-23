import { describe, it, expect } from "vitest";
import { parseEspCsv } from "../lib/esp-csv";

const GOOD = "2026-08-20T10:30:00Z,1787654321,45.2,154.8,1,12,340,2,4.8,NORMAL,0,ntp,-67,ok";

describe("parseEspCsv", () => {
  it("parses a real row with the right types", () => {
    const row = parseEspCsv(GOOD);
    expect(row).not.toBeNull();
    expect(row!.ts_utc).toBe("2026-08-20T10:30:00Z");
    expect(row!.ts_epoch).toBe(1787654321);
    expect(row!.jarak_cm).toBeCloseTo(45.2);
    expect(row!.tinggi_cm).toBeCloseTo(154.8);
    expect(row!.valid).toBe(1);
    expect(row!.mm_per_jam).toBeCloseTo(4.8);
    expect(row!.level).toBe("NORMAL");
    expect(row!.rssi).toBe(-67);
    expect(row!.sms_status).toBe("ok");
  });

  it("skips the header line", () => {
    const header =
      "ts_utc,ts_epoch,jarak_cm,tinggi_cm,valid,n_sampel,tip_total,tip_menit,mm_per_jam,level,pompa,time_src,rssi,sms_status";
    expect(parseEspCsv(header)).toBeNull();
  });

  it("skips blank and whitespace-only lines", () => {
    expect(parseEspCsv("")).toBeNull();
    expect(parseEspCsv("   ")).toBeNull();
  });

  it("throws on the wrong number of columns", () => {
    expect(() => parseEspCsv("2026-08-20T10:30:00Z,1787654321,45.2")).toThrow(/14 columns/);
  });

  it("throws when ts_epoch is not a number", () => {
    const bad = GOOD.replace("1787654321", "notanumber");
    expect(() => parseEspCsv(bad)).toThrow(/ts_epoch/);
  });

  it("keeps an empty numeric field as null rather than 0", () => {
    const gap = "2026-08-20T10:30:00Z,1787654321,,154.8,1,12,340,2,4.8,NORMAL,0,ntp,-67,ok";
    expect(parseEspCsv(gap)!.jarak_cm).toBeNull();
  });
});
