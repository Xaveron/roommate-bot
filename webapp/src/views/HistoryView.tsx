import { useState } from "react";
import { api } from "../api";
import { Async } from "../components/common";
import { useActions } from "../components/controls";
import { dateAndTime, money } from "../format";
import { REFRESH_MS, useLoad } from "../hooks";
import type { Key, Translator } from "../i18n";
import type { Duty, HistoryData } from "../types";

type OnVote = (duty: Duty, vote: "up" | "down") => void;

/** 👍 / 🤨 like under the bot's announcement: buttons while voting is open, counters after. */
function Votes({ duty, i18n, busy, onVote }: { duty: Duty; i18n: Translator; busy: string | null; onVote: OnVote }) {
  if (duty.status !== "done" && duty.status !== "out_of_turn") return null;
  if (!duty.can_vote) {
    if (!duty.votes_up && !duty.votes_down) return null;
    return (
      <div className="votes">
        <span className="chip">👍 {duty.votes_up}</span> <span className="chip">🤨 {duty.votes_down}</span>
      </div>
    );
  }
  return (
    <div className="votes">
      {(["up", "down"] as const).map((vote) => {
        const id = `vote-${duty.id}-${vote}`;
        return (
          <button
            type="button"
            key={vote}
            className="vote"
            aria-pressed={duty.my_vote === vote}
            aria-label={i18n.t(vote === "up" ? "history.voteUp" : "history.voteDown")}
            disabled={busy !== null || duty.my_vote === vote}
            onClick={() => onVote(duty, vote)}
          >
            {busy === id ? "…" : `${vote === "up" ? "👍" : "🤨"} ${vote === "up" ? duty.votes_up : duty.votes_down}`}
          </button>
        );
      })}
    </div>
  );
}

export function HistoryTable({
  data,
  i18n,
  selected,
  onSelect,
  busy = null,
  onVote = () => {},
}: {
  data: HistoryData;
  i18n: Translator;
  selected: number | undefined;
  onSelect: (categoryId: number | undefined) => void;
  busy?: string | null;
  onVote?: OnVote;
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
                        {!disputed && <Votes duty={duty} i18n={i18n} busy={busy} onVote={onVote} />}
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
  const state = useLoad(() => api.history(roomId, selected), [roomId, selected], { refreshEvery: REFRESH_MS });
  const actions = useActions(i18n, state.reload);
  return (
    <Async state={state} i18n={i18n}>
      {(data) => (
        <HistoryTable
          data={data}
          i18n={i18n}
          selected={selected}
          onSelect={setSelected}
          busy={actions.busy}
          onVote={(duty, vote) => void actions.run(`vote-${duty.id}-${vote}`, () => api.vote(roomId, duty.id, vote))}
        />
      )}
    </Async>
  );
}
