import { useState } from "react";
import { api } from "../api";
import { Async } from "../components/common";
import { type Actions, MainButton, useActions } from "../components/controls";
import { dateAndTime } from "../format";
import { REFRESH_MS, useLoad } from "../hooks";
import type { Translator } from "../i18n";
import type { ShoppingData } from "../types";

export function ShoppingList({
  data,
  i18n,
  actions,
  onAdd = async () => false,
}: {
  data: ShoppingData;
  i18n: Translator;
  actions: Pick<Actions, "busy" | "run"> | null;
  onAdd?: (text: string) => Promise<boolean>;
}) {
  const [text, setText] = useState("");
  const busy = actions?.busy ?? null;
  const add = async () => {
    if (text.trim() && (await onAdd(text))) setText("");
  };
  return (
    <>
      <form
        className="add-form"
        onSubmit={(event) => {
          event.preventDefault();
          void add();
        }}
      >
        <input
          aria-label={i18n.t("shopping.placeholder")}
          placeholder={i18n.t("shopping.example")}
          enterKeyHint="send"
          maxLength={500}
          value={text}
          onChange={(event) => setText(event.target.value)}
        />
        <button type="submit" className="button primary" disabled={!text.trim() || busy !== null}>
          {busy === "add" ? "…" : i18n.t("shopping.add")}
        </button>
      </form>
      <section className="card">
        {data.items.length === 0 ? (
          <p className="center">{i18n.t("shopping.empty")}</p>
        ) : (
          <ul className="items">
            {data.items.map((item) => (
              <li key={item.id}>
                <button
                  type="button"
                  className="check"
                  aria-label={i18n.t("shopping.bought", { item: item.text })}
                  disabled={busy !== null}
                  onClick={() => void actions?.run(`bought-${item.id}`, () => api.bought(data.room.id, item.id))}
                >
                  {busy === `bought-${item.id}` ? "…" : ""}
                </button>
                <div>
                  <div className="name">{item.text}</div>
                  <div className="sub">
                    {item.added_by ?? "—"} · {dateAndTime(item.created_at, data.room.timezone)[0]}
                  </div>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
      <p className="hint">{i18n.t("shopping.hint")}</p>
    </>
  );
}

export default function ShoppingView({ roomId, i18n }: { roomId: number; i18n: Translator }) {
  const state = useLoad(() => api.shopping(roomId), [roomId], { refreshEvery: REFRESH_MS });
  const actions = useActions(i18n, state.reload);
  return (
    <Async state={state} i18n={i18n}>
      {(data) => (
        <>
          <ShoppingList
            data={data}
            i18n={i18n}
            actions={actions}
            onAdd={(text) => actions.run("add", () => api.addItems(roomId, text))}
          />
          <MainButton
            text={i18n.t("shopping.going")}
            progress={actions.busy === "going"}
            onClick={() => void actions.run("going", () => api.goingShopping(roomId), i18n.t("confirm.going"))}
          />
        </>
      )}
    </Async>
  );
}
