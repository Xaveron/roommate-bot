const LOCALES: Record<string, string> = { ru: "ru-RU", ro: "ro-RO", en: "en-GB" };

export function locale(language: string): string {
  return LOCALES[language] ?? "en-GB";
}

/** 12345 -> "123.45 MDL", 4000 -> "40 MDL" (same rules as the bot). */
export function money(cents: number, currency: string, signed = false): string {
  const sign = cents < 0 ? "−" : signed && cents > 0 ? "+" : "";
  const abs = Math.abs(cents);
  const units = Math.floor(abs / 100)
    .toString()
    .replace(/\B(?=(\d{3})+(?!\d))/g, " ");
  const rest = abs % 100;
  return `${sign}${units}${rest ? `.${String(rest).padStart(2, "0")}` : ""} ${currency}`;
}

/** "26.09, 18:30" in the room's timezone. */
export function dateTime(iso: string, timeZone: string, language: string): string {
  return new Intl.DateTimeFormat(locale(language), {
    timeZone,
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(iso));
}

/** ["26.09", "18:30"] in the room's timezone, for two-line table cells. */
export function dateAndTime(iso: string, timeZone: string): [string, string] {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone,
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).formatToParts(new Date(iso));
  const get = (type: string) => parts.find((p) => p.type === type)?.value ?? "";
  return [`${get("day")}.${get("month")}`, `${get("hour")}:${get("minute")}`];
}

/** "2026-10-15" -> "15.10". */
export function shortDate(day: string): string {
  const [, month, date] = day.split("-");
  return `${date}.${month}`;
}

export function initials(name: string): string {
  const letters = name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => [...part][0] ?? "");
  return letters.join("").toUpperCase() || "?";
}

/** "2026-09-26" + 6 days -> "2026-10-02" (calendar days, no timezone involved). */
export function addDays(day: string, days: number): string {
  const date = new Date(`${day}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

/**
 * "23,50" -> 2350, for previews only: the backend parses amounts itself (and more leniently,
 * e.g. "120 лей"), so an unparsed value is still sent as typed.
 */
export function previewCents(text: string): number | null {
  const cleaned = text.replace(/[\s ]/g, "").replace(",", ".");
  if (!/^\d+(\.\d{1,2})?$/.test(cleaned)) return null;
  const cents = Math.round(Number.parseFloat(cleaned) * 100);
  return cents > 0 ? cents : null;
}
