import { useState } from "react";
import { api } from "../api";
import { Async, Avatar } from "../components/common";
import { type Actions, MainButton, Sheet, useActions } from "../components/controls";
import { addDays, shortDate } from "../format";
import { REFRESH_MS, useLoad } from "../hooks";
import type { Key, Translator } from "../i18n";
import type { Mark, QueueCategory, QueueData } from "../types";

export type TurnAction = "accept" | "done" | "still" | "decline" | "outOfTurn";

/** What the caller may do in a category: the same choices as under the bot's reminder. */
export function turnActions(category: QueueCategory, me: number): TurnAction[] {
  if (category.current?.member_id !== me) return ["outOfTurn"];
  if (category.assignment_id === null) return ["done"]; // no reminder yet: only /done
  switch (category.status) {
    case "pending":
      return ["accept", "done", "still", "decline"];
    case "accepted":
      return ["done", "decline"];
    default:
      return ["done"]; // snoozed until tomorrow
  }
}

/** Chores that cost money ask what they cost (not the trash, as in the bot). */
export const asksAmount = (category: QueueCategory) => category.kind !== "trash";

const kindOf = (kind: string) => (kind === "bread" || kind === "water" || kind === "trash" ? kind : "custom");

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

function actionLabel(action: TurnAction, category: QueueCategory, i18n: Translator): string {
  switch (action) {
    case "accept":
      return i18n.t(`turn.accept.${kindOf(category.kind)}` as Key);
    case "still":
      return i18n.t(`turn.still.${kindOf(category.kind)}` as Key);
    default:
      return i18n.t(`turn.${action}` as Key);
  }
}

const BUTTON_CLASS: Record<TurnAction, string> = {
  done: "button primary",
  accept: "button",
  still: "button",
  decline: "button",
  outOfTurn: "button ghost",
};

export function QueueList({
  data,
  i18n,
  busy = null,
  onAction = () => {},
  onAway = () => {},
  onBack = () => {},
}: {
  data: QueueData;
  i18n: Translator;
  busy?: string | null;
  onAction?: (action: TurnAction, category: QueueCategory) => void;
  onAway?: () => void;
  onBack?: () => void;
}) {
  const hasMarks = data.categories.some((c) => c.marks.length > 0);
  const meAway = data.away.find((person) => person.member_id === data.me_member_id);
  return (
    <>
      {data.categories.length === 0 && <p className="center">{i18n.t("queue.empty")}</p>}
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
            <div className="actions">
              {turnActions(category, data.me_member_id).map((action) => {
                const id = `${action}-${category.id}`;
                return (
                  <button
                    type="button"
                    key={action}
                    className={BUTTON_CLASS[action]}
                    disabled={busy !== null}
                    aria-busy={busy === id}
                    onClick={() => onAction(action, category)}
                  >
                    {busy === id ? "…" : actionLabel(action, category, i18n)}
                  </button>
                );
              })}
            </div>
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

      <section className="card row-card">
        <div>{meAway ? `🏖 ${i18n.t("away.youAreAway", { date: shortDate(meAway.until) })}` : `🏠 ${i18n.t("away.youAreHome")}`}</div>
        {meAway ? (
          <button type="button" className="button" disabled={busy !== null} onClick={onBack}>
            {busy === "back" ? "…" : i18n.t("away.back")}
          </button>
        ) : (
          <button type="button" className="button" disabled={busy !== null} onClick={onAway}>
            {i18n.t("away.leave")}
          </button>
        )}
      </section>
      {hasMarks && <p className="hint">{i18n.t("queue.legend")}</p>}
    </>
  );
}

function DoneSheet({
  roomId,
  category,
  inTurn,
  currency,
  i18n,
  actions,
  onClose,
}: {
  roomId: number;
  category: QueueCategory;
  inTurn: boolean;
  currency: string;
  i18n: Translator;
  actions: Actions;
  onClose: () => void;
}) {
  const [amount, setAmount] = useState("");
  const submit = async () => {
    if (await actions.run("done", () => api.done(roomId, category.id, inTurn, amount))) onClose();
  };
  return (
    <Sheet title={i18n.t(inTurn ? "done.title" : "done.outOfTurnTitle")} onClose={onClose} i18n={i18n}>
      <p className="lead">
        {category.emoji} {category.name}
      </p>
      <form
        onSubmit={(event) => {
          event.preventDefault();
          void submit();
        }}
      >
        <label className="field">
          <span>{i18n.t("done.amount", { currency })}</span>
          <input
            inputMode="decimal"
            enterKeyHint="done"
            autoComplete="off"
            placeholder="23.50"
            maxLength={16}
            value={amount}
            onChange={(event) => setAmount(event.target.value)}
          />
        </label>
      </form>
      <p className="hint">{i18n.t("done.amountHint")}</p>
      <MainButton
        text={i18n.t(amount.trim() ? "done.save" : "done.noAmount")}
        onClick={() => void submit()}
        progress={actions.busy === "done"}
      />
    </Sheet>
  );
}

const AWAY_PRESETS = [1, 3, 7, 14];

function AwaySheet({
  roomId,
  data,
  i18n,
  actions,
  onClose,
}: {
  roomId: number;
  data: QueueData;
  i18n: Translator;
  actions: Actions;
  onClose: () => void;
}) {
  const [days, setDays] = useState<number | null>(1);
  const [until, setUntil] = useState(data.today);
  const last = days === null ? until : addDays(data.today, days - 1);
  const submit = async () => {
    const period = days === null ? { until } : { days };
    if (await actions.run("away", () => api.away(roomId, period))) onClose();
  };
  return (
    <Sheet title={i18n.t("away.title")} onClose={onClose} i18n={i18n}>
      <p className="hint">{i18n.t("away.explain")}</p>
      <div className="chips" role="radiogroup" aria-label={i18n.t("away.title")}>
        {AWAY_PRESETS.map((preset) => (
          <button
            type="button"
            role="radio"
            key={preset}
            aria-checked={days === preset}
            onClick={() => setDays(preset)}
          >
            {i18n.t(`away.preset.${preset}` as Key)}
          </button>
        ))}
      </div>
      <label className="field">
        <span>{i18n.t("away.until")}</span>
        <input
          type="date"
          min={data.today}
          max={addDays(data.today, data.away_max_days)}
          value={last}
          onChange={(event) => {
            setDays(null);
            setUntil(event.target.value);
          }}
        />
      </label>
      <MainButton
        text={i18n.t("away.save", { date: last ? shortDate(last) : "…" })}
        disabled={!last}
        onClick={() => void submit()}
        progress={actions.busy === "away"}
      />
    </Sheet>
  );
}

type Screen = { kind: "done"; category: QueueCategory; inTurn: boolean } | { kind: "away" } | null;

export default function QueueView({ roomId, i18n }: { roomId: number; i18n: Translator }) {
  const state = useLoad(() => api.queue(roomId), [roomId], { refreshEvery: REFRESH_MS });
  const actions = useActions(i18n, state.reload);
  const [screen, setScreen] = useState<Screen>(null);
  const close = () => setScreen(null);

  const onAction = (action: TurnAction, category: QueueCategory) => {
    const turn = category.assignment_id;
    switch (action) {
      case "accept":
      case "still":
        if (turn !== null) void actions.run(`${action}-${category.id}`, () => api.turn(roomId, turn, action));
        return;
      case "decline":
        if (turn !== null)
          void actions.run(`decline-${category.id}`, () => api.turn(roomId, turn, "decline"), i18n.t("confirm.decline"));
        return;
      case "done":
      case "outOfTurn": {
        const inTurn = action === "done";
        if (asksAmount(category)) {
          setScreen({ kind: "done", category, inTurn });
          return;
        }
        const question = inTurn ? undefined : i18n.t("confirm.outOfTurn", { category: category.name });
        void actions.run(`${action}-${category.id}`, () => api.done(roomId, category.id, inTurn), question);
      }
    }
  };

  return (
    <Async state={state} i18n={i18n}>
      {(data) => (
        <>
          <QueueList
            data={data}
            i18n={i18n}
            busy={actions.busy}
            onAction={onAction}
            onAway={() => setScreen({ kind: "away" })}
            onBack={() => void actions.run("back", () => api.back(roomId))}
          />
          {screen?.kind === "done" && (
            <DoneSheet
              roomId={roomId}
              category={screen.category}
              inTurn={screen.inTurn}
              currency={data.room.currency}
              i18n={i18n}
              actions={actions}
              onClose={close}
            />
          )}
          {screen?.kind === "away" && (
            <AwaySheet roomId={roomId} data={data} i18n={i18n} actions={actions} onClose={close} />
          )}
        </>
      )}
    </Async>
  );
}
