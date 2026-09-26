import { ApiError } from "../api";
import { initials } from "../format";
import type { Translator } from "../i18n";
import type { Loaded } from "../hooks";
import type { ReactNode } from "react";

export function Gate({ emoji, title, text }: { emoji: string; title: string; text: string }) {
  return (
    <div className="gate" role="alert">
      <div className="emoji" aria-hidden>
        {emoji}
      </div>
      <h1>{title}</h1>
      <p>{text}</p>
    </div>
  );
}

export function Avatar({ name }: { name: string }) {
  return (
    <span className="avatar" aria-hidden>
      {initials(name)}
    </span>
  );
}

/** Loading / error states around a loaded value. */
export function Async<T>({
  state,
  i18n,
  children,
}: {
  state: Loaded<T>;
  i18n: Translator;
  children: (data: T) => ReactNode;
}) {
  if (state.error) {
    if (state.error instanceof ApiError && state.error.status === 401) {
      return <Gate emoji="🔒" title={i18n.t("gate.auth.title")} text={i18n.t("gate.auth.text")} />;
    }
    return (
      <div className="center">
        {i18n.t("common.error")}
        <br />
        <button type="button" className="retry" onClick={state.reload}>
          {i18n.t("common.retry")}
        </button>
      </div>
    );
  }
  if (state.data === undefined) {
    return <div className="center">{i18n.t("common.loading")}</div>;
  }
  return <>{children(state.data)}</>;
}
