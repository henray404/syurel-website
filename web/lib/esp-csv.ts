/**
 * Column order from firmware/esp32/include/logic_csv.h. The firmware writes
 * these positionally with snprintf, so order is the contract — not names.
 */
export const ESP_COLUMNS = [
  "ts_utc",
  "ts_epoch",
  "jarak_cm",
  "tinggi_cm",
  "valid",
  "n_sampel",
  "tip_total",
  "tip_menit",
  "mm_per_jam",
  "level",
  "pompa",
  "time_src",
  "rssi",
  "sms_status",
] as const;

export type EspRow = {
  ts_utc: string;
  ts_epoch: number;
  jarak_cm: number | null;
  tinggi_cm: number | null;
  valid: number | null;
  n_sampel: number | null;
  tip_total: number | null;
  tip_menit: number | null;
  mm_per_jam: number | null;
  level: string | null;
  pompa: number | null;
  time_src: string | null;
  rssi: number | null;
  sms_status: string | null;
};

/**
 * Empty stays null. A missing reading is not a reading of zero.
 *
 * "nan"/"-nan" also stays null: the firmware's snprintf("%.1f", ...) prints
 * that literally whenever a float field is NAN (e.g. jarak_cm on an invalid
 * ultrasonic read), and it means the same thing as an empty field -- no
 * reading. Without this, JS's `Number("nan")` also evaluates to NaN and
 * would throw here, rejecting the WHOLE batch over one expected invalid
 * row -- the firmware then never advances its upload cursor and retries the
 * same batch forever. Rejecting still applies to anything else unparseable.
 */
function num(raw: string, field: string): number | null {
  const s = raw.trim();
  if (s === "" || s.toLowerCase() === "nan" || s.toLowerCase() === "-nan") return null;
  const v = Number(s);
  if (!Number.isFinite(v)) throw new Error(`${field}: not a number: ${JSON.stringify(raw)}`);
  return v;
}

function str(raw: string): string | null {
  const s = raw.trim();
  return s === "" ? null : s;
}

/**
 * Parse one CSV line from the ESP32.
 *
 * Returns null for lines to skip (header, blank). Throws for a malformed row —
 * the caller must then reject the whole batch, because replying 2xx would make
 * the firmware drop these rows for good.
 */
export function parseEspCsv(line: string): EspRow | null {
  const trimmed = line.trim();
  if (trimmed === "") return null;
  if (trimmed.startsWith("ts_utc")) return null;

  const parts = trimmed.split(",");
  if (parts.length !== ESP_COLUMNS.length) {
    throw new Error(
      `expected ${ESP_COLUMNS.length} columns, got ${parts.length}: ${JSON.stringify(trimmed)}`,
    );
  }

  const ts_utc = parts[0].trim();
  if (ts_utc === "") throw new Error("ts_utc: empty");

  const ts_epoch = num(parts[1], "ts_epoch");
  if (ts_epoch === null) throw new Error("ts_epoch: empty");

  return {
    ts_utc,
    ts_epoch,
    jarak_cm: num(parts[2], "jarak_cm"),
    tinggi_cm: num(parts[3], "tinggi_cm"),
    valid: num(parts[4], "valid"),
    n_sampel: num(parts[5], "n_sampel"),
    tip_total: num(parts[6], "tip_total"),
    tip_menit: num(parts[7], "tip_menit"),
    mm_per_jam: num(parts[8], "mm_per_jam"),
    level: str(parts[9]),
    pompa: num(parts[10], "pompa"),
    time_src: str(parts[11]),
    rssi: num(parts[12], "rssi"),
    sms_status: str(parts[13]),
  };
}
