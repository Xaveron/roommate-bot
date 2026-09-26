// Minimal typing of the Telegram Mini App API (loaded from telegram-web-app.js).

interface TelegramWebApp {
  initData: string;
  colorScheme: "light" | "dark";
  ready(): void;
  expand(): void;
  onEvent(event: "themeChanged", handler: () => void): void;
  HapticFeedback?: { selectionChanged(): void };
}

declare global {
  interface Window {
    Telegram?: { WebApp?: TelegramWebApp };
  }
}

export function webApp(): TelegramWebApp | undefined {
  return typeof window === "undefined" ? undefined : window.Telegram?.WebApp;
}

/** Signed launch data; empty when the page is opened outside Telegram. */
export function initData(): string {
  return webApp()?.initData ?? "";
}

export function colorScheme(): "light" | "dark" {
  return webApp()?.colorScheme ?? "light";
}

export function haptic(): void {
  webApp()?.HapticFeedback?.selectionChanged();
}
