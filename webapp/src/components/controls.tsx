import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react";
import { ApiError } from "../api";
import { useLatest } from "../hooks";
import type { Key, Translator } from "../i18n";
import { confirmAction, hasNativeButtons, haptic, webApp } from "../telegram";
import type { ActionResult } from "../types";

// --- Telegram's bottom and back buttons -----------------------------------------------------

/**
 * The main action of the screen: Telegram's MainButton inside Telegram, a button at the
 * bottom of the page in a browser. Only one may be mounted at a time.
 */
export function MainButton({
  text,
  onClick,
  disabled = false,
  progress = false,
}: {
  text: string;
  onClick: () => void;
  disabled?: boolean;
  progress?: boolean;
}) {
  const native = hasNativeButtons();
  const handler = useLatest(onClick);
  const blocked = useLatest(disabled || progress);

  useEffect(() => {
    const button = native ? webApp()?.MainButton : undefined;
    if (!button) return;
    const click = () => {
      if (!blocked.current) handler.current();
    };
    button.onClick(click);
    return () => {
      button.offClick(click);
      button.hideProgress();
      button.hide();
    };
  }, [native, handler, blocked]);

  useEffect(() => {
    const button = native ? webApp()?.MainButton : undefined;
    if (!button) return;
    button.setParams({ text, is_active: !disabled && !progress, is_visible: true });
    if (progress) button.showProgress(false);
    else button.hideProgress();
  }, [native, text, disabled, progress]);

  if (native) return null;
  return (
    <div className="main-button-bar">
      <button type="button" className="main-button" disabled={disabled || progress} onClick={onClick}>
        {progress ? "…" : text}
      </button>
    </div>
  );
}

/** Telegram's back arrow in the header (nothing in a browser: the sheet draws its own). */
export function BackButton({ onClick }: { onClick: () => void }) {
  const handler = useLatest(onClick);
  useEffect(() => {
    const button = hasNativeButtons() ? webApp()?.BackButton : undefined;
    if (!button) return;
    const click = () => handler.current();
    button.onClick(click);
    button.show();
    return () => {
      button.offClick(click);
      button.hide();
    };
  }, [handler]);
  return null;
}

/** A full-screen form over the current tab, closed with the back button. */
export function Sheet({
  title,
  onClose,
  i18n,
  children,
}: {
  title: string;
  onClose: () => void;
  i18n: Translator;
  children: ReactNode;
}) {
  useEffect(() => {
    document.body.classList.add("sheet-open");
    return () => document.body.classList.remove("sheet-open");
  }, []);
  return (
    <div className="sheet" role="dialog" aria-modal="true" aria-label={title}>
      <BackButton onClick={onClose} />
      <div className="sheet-body">
        {!hasNativeButtons() && (
          <button type="button" className="link-button" onClick={onClose}>
            ‹ {i18n.t("common.back")}
          </button>
        )}
        <h2 className="sheet-title">{title}</h2>
        {children}
      </div>
    </div>
  );
}

// --- toasts -------------------------------------------------------------------------------

type Toast = (text: string, kind?: "ok" | "error") => void;

const ToastContext = createContext<Toast>(() => {});

export function useToast(): Toast {
  return useContext(ToastContext);
}

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toast, setToast] = useState<{ id: number; text: string; kind: "ok" | "error" } | null>(null);
  const counter = useRef(0);
  const show = useCallback<Toast>((text, kind = "ok") => {
    counter.current += 1;
    setToast({ id: counter.current, text, kind });
  }, []);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), toast.kind === "error" ? 4500 : 2500);
    return () => clearTimeout(timer);
  }, [toast]);
  return (
    <ToastContext.Provider value={show}>
      {children}
      <div className="toast-area" role="status" aria-live="polite">
        {toast && (
          <button type="button" key={toast.id} className={`toast ${toast.kind}`} onClick={() => setToast(null)}>
            {toast.text}
          </button>
        )}
      </div>
    </ToastContext.Provider>
  );
}

// --- actions ------------------------------------------------------------------------------

/** What to tell the user when an action failed. */
export function errorText(error: unknown, i18n: Translator): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return `${i18n.t("gate.auth.title")}. ${i18n.t("gate.auth.text")}`;
    if (error.status === 0) return i18n.t("errors.network");
    const own = `errors.${error.code}`;
    if (error.code && i18n.has(own)) return i18n.t(own as Key);
    if (error.text) return error.text;
    if (error.status === 404) return i18n.t("errors.notFound");
  }
  return i18n.t("errors.generic");
}

export interface Actions {
  /** Which action is running (to show progress on its button), or null. */
  busy: string | null;
  /**
   * Run an action once at a time: optional confirmation, haptics, a toast with the result,
   * then `after` (reload the data) whatever happened.
   */
  run: (id: string, request: () => Promise<ActionResult>, confirm?: string) => Promise<boolean>;
}

export function useActions(i18n: Translator, after?: () => void): Actions {
  const toast = useToast();
  const [busy, setBusy] = useState<string | null>(null);
  const running = useRef(false);
  const afterRef = useLatest(after);

  const run = useCallback<Actions["run"]>(
    async (id, request, confirm) => {
      if (running.current) return false; // a double tap
      running.current = true;
      let acted = false;
      try {
        if (confirm && !(await confirmAction(confirm))) return false;
        acted = true;
        setBusy(id);
        haptic.tap();
        const result = await request();
        haptic.success();
        toast(result.message);
        return true;
      } catch (error) {
        haptic.error();
        toast(errorText(error, i18n), "error");
        return false;
      } finally {
        running.current = false;
        setBusy(null);
        if (acted) afterRef.current?.();
      }
    },
    [i18n, toast, afterRef],
  );
  return { busy, run };
}
