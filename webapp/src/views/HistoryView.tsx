import { useState } from "react";
import { api } from "../api";
import { Async } from "../components/common";
import { dateAndTime, money } from "../format";
import { useLoad } from "../hooks";
import type { Key, Translator } from "../i18n";
import type { HistoryData } from "../types";

export function HistoryTable({
  data,
  i18n,
  selected,
  onSelect,
}: {
  data: HistoryData;
  i18n: Translator;
  selected: number | undefined;
  onSelect: (categoryId: number | undefined) => void;
}) {
  const categories = new Map(data.categories.map((c) => [c.id, c]));
  const { timezone, currency } = data.room;
  return (
    <>
      <div className="filters" role="toolbar">
        <button type="button" aria-pressed={selected === undefined} onClick={() => onSelect(undefined)}>
          {i18n.t("history.all")}
        </button>
        {data.categories.map((category) => (
          <button
            type="button"
            key={category.id}
            aria-pressed={selected === category.id}
            onClick={() => onSelect(category.id)}
          >
            {category.emoji} {category.name}
          </button>
        ))}
      </div>
      <section className="card">
        {data.items.length === 0 ? (
          <p className="center">{i18n.t("history.empty")}</p>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>{i18n.t("history.date")}</th>
                  <th>{i18n.t("history.who")}</th>
                  <th>{i18n.t("history.what")}</th>
                  <th className="num">{i18n.t("history.amount")}</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((duty) => {
                  const category = categories.get(duty.category_id);
                  const disputed = duty.review === "disputed";
                  const [day, clock] = dateAndTime(duty.created_at, timezone);
                  return (
                    <tr key={duty.id} className={disputed ? "disputed" : undefined}>
                      <td className="when">
                        {day}
                        <div className="sub">{clock}</div>
                      </td>
                      <td>{duty.member_name}</td>
                      <td className="status">
                        {selected === undefined && category ? `${category.emoji} ` : ""}
                        {i18n.t(`status.${duty.status}` as Key)}
                        {disputed && (
                          <div>
                            <span className="chip bad">🤨 {i18n.t("history.disputed")}</span>
                          </div>
                        )}
                      </td>
                      <td className="num">{duty.amount_cents ? money(duty.amount_cents, currency) : ""}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}

export default function HistoryView({ roomId, i18n }: { roomId: number; i18n: Translator }) {
  const [selected, setSelected] = useState<number | undefined>();
  const state = useLoad(() => api.history(roomId, selected), [roomId, selected]);
  return (
    <Async state={state} i18n={i18n}>
      {(data) => <HistoryTable data={data} i18n={i18n} selected={selected} onSelect={setSelected} />}
    </Async>
  );
}
