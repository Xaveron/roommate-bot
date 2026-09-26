import { type DependencyList, useCallback, useEffect, useState } from "react";

export interface Loaded<T> {
  data: T | undefined;
  error: unknown;
  loading: boolean;
  reload: () => void;
}

/** Run an async loader whenever the dependencies change; ignores stale responses. */
export function useLoad<T>(load: () => Promise<T>, deps: DependencyList): Loaded<T> {
  const [state, setState] = useState<{ data?: T; error?: unknown; loading: boolean }>({
    loading: true,
  });
  const [attempt, setAttempt] = useState(0);
  // `load` is a new closure on every render; `deps` decide when to reload.
  const run = useCallback(load, deps);

  useEffect(() => {
    let current = true;
    setState((previous) => ({ data: previous.data, loading: true }));
    run().then(
      (data) => current && setState({ data, loading: false }),
      (error: unknown) => current && setState({ error, loading: false }),
    );
    return () => {
      current = false;
    };
  }, [run, attempt]);

  return { ...state, reload: () => setAttempt((n) => n + 1) } as Loaded<T>;
}
