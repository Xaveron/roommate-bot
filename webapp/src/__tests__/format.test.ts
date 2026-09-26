import { describe, expect, it } from "vitest";
import { dateTime, initials, money, shortDate } from "../format";
import { seriesColor } from "../palette";

describe("format", () => {
  it("formats money like the bot", () => {
    expect(money(4000, "MDL")).toBe("40 MDL");
    expect(money(12345, "MDL")).toBe("123.45 MDL");
    expect(money(-4005, "EUR")).toBe("−40.05 EUR");
    expect(money(1500, "MDL", true)).toBe("+15 MDL");
    expect(money(123456700, "RON")).toBe("1 234 567 RON");
  });

  it("shows times in the room's timezone", () => {
    expect(dateTime("2026-09-26T15:30:00Z", "Europe/Chisinau", "ru")).toBe("26.09, 18:30");
    expect(dateTime("2026-09-26T15:30:00Z", "UTC", "en")).toContain("15:30");
  });

  it("formats dates and initials", () => {
    expect(shortDate("2026-10-15")).toBe("15.10");
    expect(initials("Аня Петрова")).toBe("АП");
    expect(initials("")).toBe("?");
  });

  it("keeps category colors in fixed slots", () => {
    expect(seriesColor(0, "light")).toBe("#2a78d6");
    expect(seriesColor(0, "dark")).toBe("#3987e5");
    expect(seriesColor(99, "light")).toBe("#898781");
  });
});
