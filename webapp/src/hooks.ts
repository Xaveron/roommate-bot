import { type DependencyList, useCallback, useEffect, useRef, useState } from "react";
import { onReturn } from "./telegram";

export interface Loaded<T> {
  data: T | undefined;
  error: unknown;
  loading: boolean;
  reload: () => void;
}

/** How often the open tab asks for fresh data, so changes made in the bot show up. */
export const REFRESH_MS = 5000;
/** The same for data that rarely changes (the room's settings and roommates). */
export const SLOW_REFRESH_MS = 15000;

/**
 * Run an async loader whenever the dependencies change; ignores stale responses.
 *
 * With `refreshEvery`, the data is reloaded periodically while the page is visible and at once
 * when the user comes back to the app. Reloads keep showing the previous data, and a failed
 * background reload keeps it too (the error is still reported in `error`).
 */
export function useLoad<T>(
  load: () => Promise<T>,
  deps: DependencyList,
  { refreshEvery }: { refreshEvery?: number } = {},
): Loaded<T> {
  const [state, setState] = useState<{ data?: T; error?: unknown; loading: boolean }>({
    loading: true,
  });
  const [attempt, setAttempt] = useState(0);
  // `load` is a new closure on every render; `deps` decide when to reload.
  const run = useCallback(load, deps);
  const reload = useCallback(() => setAttempt((n) => n + 1), []);

  useEffect(() => {
    let current = true;
    setState((previous) => ({ data: previous.data, error: previous.error, loading: true }));
    run().then(
      (data) => current && setState({ data, loading: false }),
      (error: unknown) => current && setState((previous) => ({ data: previous.data, error, loading: false })),
    );
    return () => {
      current = false;
    };
  }, [run, attempt]);

  useEffect(() => {
    if (!refreshEvery) return;
    const timer = setInterval(() => {
      if (document.visibilityState === "visible") reload();
    }, refreshEvery);
    const stop = onReturn(reload);
    return () => {
      clearInterval(timer);
      stop();
    };
  }, [refreshEvery, reload]);

  return { ...state, reload } as Loaded<T>;
}

/** The latest value of something, for callbacks registered once (Telegram button handlers). */
export function useLatest<T>(value: T): { readonly current: T } {
  const ref = useRef(value);
  ref.current = value;
  return ref;
}
