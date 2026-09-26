import { api } from "../api";
import { Async, Avatar } from "../components/common";
import { shortDate } from "../format";
import { useLoad } from "../hooks";
import type { Translator } from "../i18n";
import type { Mark, QueueCategory, QueueData } from "../types";

function statusChip(category: QueueCategory, i18n: Translator) {
  switch (category.status) {
    case "pending":
      return <span className="chip warn">⏳ {i18n.t("queue.status.pending")}</span>;
    case "accepted":
      return <span className="chip">🛒 {i18n.t("queue.status.accepted")}</span>;
    case "snoozed":
      return (
        <span className="chip">
          🔄 {i18n.t("queue.status.snoozed", { date: category.remind_on ? shortDate(category.remind_on) : "" })}
        </span>
      );
    default:
      return null;
  }
}

function markText(mark: Mark | undefined): string {
  if (!mark) return "";
  return "⚠️".repeat(Math.min(mark.skip_debt, 3)) + "⭐".repeat(Math.min(mark.credit, 3));
}

export function QueueList({ data, i18n }: { data: QueueData; i18n: Translator }) {
  if (data.categories.length === 0) {
    return <p className="center">{i18n.t("queue.empty")}</p>;
  }
  const hasMarks = data.categories.some((c) => c.marks.length > 0);
  return (
    <>
      {data.categories.map((category) => {
        const marks = new Map(category.marks.map((m) => [m.member_id, m]));
        const current = category.current;
        const mine = current?.member_id === data.me_member_id;
        return (
          <section className="card" key={category.id} aria-label={category.name}>
            <h2>
              <span aria-hidden>{category.emoji}</span> {category.name}
              <span className="meta">
                {category.mode === "fair" && `⚖️ ${i18n.t("queue.mode.fair")} · `}
                {i18n.t("queue.reminder", { time: category.reminder_time })}
              </span>
            </h2>
            {current ? (
              <div className="person">
                <Avatar name={current.name} />
                <div>
                  <div className="name">
                    {current.name} {markText(marks.get(current.member_id))}
                  </div>
                  <div className="sub">
                    {mine ? <span className="chip me">{i18n.t("queue.yourTurn")}</span> : i18n.t("queue.now")}{" "}
                    {statusChip(category, i18n)}
                  </div>
                </div>
              </div>
            ) : (
              <p className="hint">{i18n.t("queue.nobody")}</p>
            )}
            {category.upcoming.length > 0 && (
              <div className="next">
                {i18n.t("queue.next")}:{" "}
                {category.upcoming.map((person, index) => (
                  <span key={`${person.member_id}-${index}`}>
                    {index > 0 && " → "}
                    <b>{person.name}</b> {markText(marks.get(person.member_id))}
                  </span>
                ))}
              </div>
            )}
            {category.fair_counts && data.members.length > 0 && (
              <div className="marks">
                <span className="chip">
                  ⚖️ {i18n.t("queue.fairCounts")}:{" "}
                  {[...data.members]
                    .map((p) => ({ name: p.name, count: category.fair_counts?.[p.member_id] ?? 0 }))
                    .sort((a, b) => a.count - b.count)
                    .map((p) => `${p.name} ${p.count}`)
                    .join(" · ")}
                </span>
              </div>
            )}
          </section>
        );
      })}
      {data.away.length > 0 && (
        <section className="card">
          <h2>🏖 {i18n.t("queue.away")}</h2>
          {data.away.map((person) => (
            <div className="person" key={person.member_id} style={{ marginTop: 6 }}>
              <Avatar name={person.name} />
              <div>
                <div className="name">{person.name}</div>
                <div className="sub">{i18n.t("queue.awayUntil", { date: shortDate(person.until) })}</div>
              </div>
            </div>
          ))}
        </section>
      )}
      {hasMarks && <p className="hint">{i18n.t("queue.legend")}</p>}
    </>
  );
}

export default function QueueView({ roomId, i18n }: { roomId: number; i18n: Translator }) {
  const state = useLoad(() => api.queue(roomId), [roomId]);
  return <Async state={state} i18n={i18n}>{(data) => <QueueList data={data} i18n={i18n} />}</Async>;
}
