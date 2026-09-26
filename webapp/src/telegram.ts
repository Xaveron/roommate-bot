// Minimal typing of the Telegram Mini App API (loaded from telegram-web-app.js) and
// helpers that degrade gracefully in a plain browser and in old Telegram clients.

interface BottomButton {
  setParams(params: { text?: string; is_active?: boolean; is_visible?: boolean }): void;
  show(): void;
  hide(): void;
  showProgress(leaveActive?: boolean): void;
  hideProgress(): void;
  onClick(handler: () => void): void;
  offClick(handler: () => void): void;
}

interface BackButton {
  show(): void;
  hide(): void;
  onClick(handler: () => void): void;
  offClick(handler: () => void): void;
}

type WebAppEvent = "themeChanged" | "activated";

interface TelegramWebApp {
  initData: string;
  colorScheme: "light" | "dark";
  platform: string;
  version: string;
  isVersionAtLeast(version: string): boolean;
  ready(): void;
  expand(): void;
  disableVerticalSwipes(): void;
  onEvent(event: WebAppEvent, handler: () => void): void;
  offEvent(event: WebAppEvent, handler: () => void): void;
  showConfirm(message: string, callback: (ok: boolean) => void): void;
  MainButton: BottomButton;
  BackButton: BackButton;
  HapticFeedback?: {
    impactOccurred(style: "light" | "medium" | "heavy" | "rigid" | "soft"): void;
    notificationOccurred(type: "error" | "success" | "warning"): void;
    selectionChanged(): void;
  };
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

function supports(version: string): boolean {
  const app = webApp();
  return !!app && app.isVersionAtLeast?.(version) === true;
}

/**
 * Inside a Telegram client: the MainButton and BackButton are drawn by Telegram.
 * In a browser (development, screenshots) the page draws its own.
 */
export function hasNativeButtons(): boolean {
  const app = webApp();
  return !!app && app.platform !== "unknown" && supports("6.1");
}

export const haptic = {
  /** A tab or a chip was switched. */
  select(): void {
    if (supports("6.1")) webApp()?.HapticFeedback?.selectionChanged();
  },
  /** A button was pressed. */
  tap(): void {
    if (supports("6.1")) webApp()?.HapticFeedback?.impactOccurred("light");
  },
  success(): void {
    if (supports("6.1")) webApp()?.HapticFeedback?.notificationOccurred("success");
  },
  error(): void {
    if (supports("6.1")) webApp()?.HapticFeedback?.notificationOccurred("error");
  },
  warning(): void {
    if (supports("6.1")) webApp()?.HapticFeedback?.notificationOccurred("warning");
  },
};

/** Telegram's own confirmation popup (a plain `confirm()` outside Telegram). */
export function confirmAction(message: string): Promise<boolean> {
  const app = webApp();
  if (app && app.platform !== "unknown" && supports("6.2")) {
    haptic.warning();
    return new Promise((resolve) => app.showConfirm(message, resolve));
  }
  return Promise.resolve(typeof window !== "undefined" && window.confirm(message));
}

/** Call `handler` when the user comes back to the app (another app, a closed sheet, a chat). */
export function onReturn(handler: () => void): () => void {
  const visible = () => {
    if (document.visibilityState === "visible") handler();
  };
  document.addEventListener("visibilitychange", visible);
  const app = webApp();
  const native = supports("8.0");
  if (native) app?.onEvent("activated", handler);
  return () => {
    document.removeEventListener("visibilitychange", visible);
    if (native) app?.offEvent("activated", handler);
  };
}
