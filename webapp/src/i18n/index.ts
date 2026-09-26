import { locale } from "../format";
import { en } from "./en";
import { ro } from "./ro";
import { type Dictionary, ru } from "./ru";

export type Key = keyof Dictionary;
export type Language = "ru" | "ro" | "en";

const DICTIONARIES: Record<Language, Dictionary> = { ru, ro, en };

// Order of the "|"-separated plural forms in each dictionary.
const PLURAL_ORDER: Record<Language, Intl.LDMLPluralRule[]> = {
  ru: ["one", "few", "many"],
  ro: ["one", "few", "other"],
  en: ["one", "other"],
};

export function pickLanguage(...candidates: (string | null | undefined)[]): Language {
  for (const candidate of candidates) {
    const short = candidate?.slice(0, 2).toLowerCase();
    if (short === "ru" || short === "ro" || short === "en") return short;
  }
  return "ru";
}

function fill(template: string, params: Record<string, string | number>): string {
  return template.replace(/\{(\w+)\}/g, (match, name: string) =>
    name in params ? String(params[name]) : match,
  );
}

export interface Translator {
  language: Language;
  t(key: Key, params?: Record<string, string | number>): string;
  /** Plural-aware: `tn("stats.chores", 5)` -> "5 дел". */
  tn(key: Key, n: number, params?: Record<string, string | number>): string;
}

export function translator(language: Language): Translator {
  const dictionary = DICTIONARIES[language];
  const rules = new Intl.PluralRules(locale(language));
  const order = PLURAL_ORDER[language];
  return {
    language,
    t: (key, params = {}) => fill(dictionary[key], params),
    tn: (key, n, params = {}) => {
      const forms = dictionary[key].split("|");
      const index = order.indexOf(rules.select(n));
      const form = forms[index >= 0 ? index : forms.length - 1] ?? forms[0] ?? "";
      return fill(form, { n, ...params });
    },
  };
}

export const dictionaries = DICTIONARIES;
