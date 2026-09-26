import { describe, expect, it } from "vitest";
import { dictionaries, pickLanguage, translator } from "../i18n";

const placeholders = (text: string) => [...new Set([...text.matchAll(/\{(\w+)\}/g)].map((m) => m[1]))].sort();

describe("i18n", () => {
  it("has the same placeholders in every language", () => {
    const { ru, ro, en } = dictionaries;
    for (const key of Object.keys(ru) as (keyof typeof ru)[]) {
      expect(placeholders(ro[key]), `ro ${key}`).toEqual(placeholders(ru[key]));
      expect(placeholders(en[key]), `en ${key}`).toEqual(placeholders(ru[key]));
    }
  });

  it("uses the right plural forms", () => {
    const ru = translator("ru");
    expect([1, 2, 5, 21, 22, 25].map((n) => ru.tn("stats.chores", n))).toEqual([
      "1 дело",
      "2 дела",
      "5 дел",
      "21 дело",
      "22 дела",
      "25 дел",
    ]);
    const ro = translator("ro");
    expect([1, 2, 20].map((n) => ro.tn("stats.chores", n))).toEqual([
      "1 sarcină",
      "2 sarcini",
      "20 de sarcini",
    ]);
    expect(translator("en").tn("stats.chores", 1)).toBe("1 chore");
  });

  it("fills parameters and picks a supported language", () => {
    expect(translator("en").t("queue.awayUntil", { date: "15.10" })).toBe("until 15.10");
    expect(pickLanguage(undefined, "ro-RO")).toBe("ro");
    expect(pickLanguage("de", null)).toBe("ru");
  });
});
