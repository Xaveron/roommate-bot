import { useState } from "react";
import { api } from "../api";
import { Async, Avatar } from "../components/common";
import { type Actions, MainButton, Sheet, useActions } from "../components/controls";
import { dateTime, money, previewCents } from "../format";
import { REFRESH_MS, useLoad } from "../hooks";
import type { Translator } from "../i18n";
import { haptic } from "../telegram";
import type { BalanceData, Transfer } from "../types";

export function BalanceSummary({
  data,
  i18n,
  busy = null,
  onSettle = () => {},
}: {
  data: BalanceData;
  i18n: Translator;
  busy?: string | null;
  onSettle?: (transfer: Transfer) => void;
}) {
  const { currency, timezone } = data.room;
  const me = data.me_member_id;
  const mine = data.balances.find((b) => b.member_id === me)?.cents ?? 0;
  return (
    <>
      <section className="card hero">
        {mine === 0 ? (
          <div className="value">{i18n.t("balance.square")}</div>
        ) : (
          <>
            <div className="label">{i18n.t(mine > 0 ? "balance.youGet" : "balance.youOwe")}</div>
            <div className={`value ${mine > 0 ? "pos" : "neg"}`}>{money(Math.abs(mine), currency)}</div>
          </>
        )}
      </section>

      {data.balances.length > 0 && (
        <>
          <h3 className="section-title">{i18n.t("balance.transfers")}</h3>
          <section className="card">
            <table>
              <tbody>
                {data.transfers.map((transfer) => {
                  const id = `settle-${transfer.debtor_id}-${transfer.creditor_id}`;
                  const party = transfer.debtor_id === me || transfer.creditor_id === me;
                  return (
                    <tr key={id}>
                      <td>
                        {transfer.debtor_name} → <b>{transfer.creditor_name}</b>
                        <div className="sub">{money(transfer.cents, currency)}</div>
                      </td>
                      <td className="num">
                        {party && (
                          <button
                            type="button"
                            className="button small"
                            disabled={busy !== null}
                            onClick={() => onSettle(transfer)}
                          >
                            {busy === id
                              ? "…"
                              : i18n.t(transfer.debtor_id === me ? "balance.iPaid" : "balance.paidMe")}
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </section>
          <h3 className="section-title">{i18n.t("balance.balances")}</h3>
          <section className="card">
            <table>
              <tbody>
                {data.balances.map((line) => (
                  <tr key={line.member_id}>
                    <td>
                      <span className="person">
                        <Avatar name={line.name} />
                        <span className="name">
                          {line.name}
                          {line.member_id === me && ` (${i18n.t("common.you")})`}
                        </span>
                      </span>
                    </td>
                    <td className={`num ${line.cents > 0 ? "pos" : "neg"}`}>{money(line.cents, currency, true)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </>
      )}

      <h3 className="section-title">{i18n.t("balance.expenses")}</h3>
      <section className="card">
        {data.expenses.length === 0 ? (
          <p className="center">{i18n.t("balance.noExpenses")}</p>
        ) : (
          <div className="table-wrap">
            <table>
              <tbody>
                {data.expenses.map((expense) => (
                  <tr key={expense.id}>
                    <td>
                      <div className="name">
                        {expense.is_settlement ? `🤝 ${i18n.t("balance.settlement")}` : expense.description || "—"}
                      </div>
                      <div className="sub hint" style={{ margin: 0 }}>
                        {dateTime(expense.created_at, timezone, i18n.language)} · {expense.payer_name}
                        {!expense.is_settlement &&
                          ` · ${i18n.t("balance.split", { names: expense.shares.map((s) => s.name).join(", ") })}`}
                      </div>
                    </td>
                    <td className="num">{money(expense.amount_cents, currency)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}

export function ExpenseForm({
  data,
  i18n,
  busy,
  onSave,
}: {
  data: BalanceData;
  i18n: Translator;
  busy: boolean;
  onSave: (expense: { amount: string; description: string; member_ids: number[] }) => void;
}) {
  const home = data.members.filter((m) => m.at_home).map((m) => m.member_id);
  const [amount, setAmount] = useState("");
  const [description, setDescription] = useState("");
  const [selected, setSelected] = useState<number[]>(home.length ? home : [data.me_member_id]);
  const toggle = (id: number) => {
    haptic.select();
    setSelected((now) => (now.includes(id) ? now.filter((m) => m !== id) : [...now, id]));
  };
  const cents = previewCents(amount);
  const all = data.members.every((m) => selected.includes(m.member_id));
  const save = () =>
    onSave({
      amount,
      description,
      member_ids: data.members.map((m) => m.member_id).filter((id) => selected.includes(id)),
    });
  return (
    <form
      onSubmit={(event) => {
        event.preventDefault();
        save();
      }}
    >
      <label className="field">
        <span>{i18n.t("expense.amount", { currency: data.room.currency })}</span>
        <input
          inputMode="decimal"
          autoComplete="off"
          placeholder="120"
          maxLength={16}
          value={amount}
          onChange={(event) => setAmount(event.target.value)}
        />
      </label>
      <label className="field">
        <span>{i18n.t("expense.description")}</span>
        <input
          placeholder={i18n.t("expense.descriptionHint")}
          maxLength={64}
          value={description}
          onChange={(event) => setDescription(event.target.value)}
        />
      </label>
      <div className="field">
        <span>{i18n.t("expense.split")}</span>
        <div className="chips">
          <button
            type="button"
            aria-pressed={all}
            onClick={() => {
              haptic.select();
              setSelected(all ? [] : data.members.map((m) => m.member_id));
            }}
          >
            👥 {i18n.t("expense.everybody")}
          </button>
          {data.members.map((member) => (
            <button
              type="button"
              key={member.member_id}
              aria-pressed={selected.includes(member.member_id)}
              onClick={() => toggle(member.member_id)}
            >
              {member.name}
              {!member.at_home && " 🏖"}
            </button>
          ))}
        </div>
      </div>
      {cents !== null && selected.length > 0 && (
        <p className="hint">
          {i18n.t("expense.share", { amount: money(Math.floor(cents / selected.length), data.room.currency) })}
        </p>
      )}
      <MainButton
        text={i18n.t("expense.save")}
        disabled={!amount.trim() || selected.length === 0}
        progress={busy}
        onClick={save}
      />
    </form>
  );
}

function ExpenseSheet({
  data,
  i18n,
  actions,
  onClose,
}: {
  data: BalanceData;
  i18n: Translator;
  actions: Actions;
  onClose: () => void;
}) {
  return (
    <Sheet title={i18n.t("expense.title")} onClose={onClose} i18n={i18n}>
      <ExpenseForm
        data={data}
        i18n={i18n}
        busy={actions.busy === "expense"}
        onSave={async (expense) => {
          if (await actions.run("expense", () => api.addExpense(data.room.id, expense))) onClose();
        }}
      />
    </Sheet>
  );
}

export default function BalanceView({ roomId, i18n }: { roomId: number; i18n: Translator }) {
  const state = useLoad(() => api.balance(roomId), [roomId], { refreshEvery: REFRESH_MS });
  const actions = useActions(i18n, state.reload);
  const [adding, setAdding] = useState(false);
  return (
    <Async state={state} i18n={i18n}>
      {(data) => (
        <>
          <BalanceSummary
            data={data}
            i18n={i18n}
            busy={actions.busy}
            onSettle={(transfer) =>
              void actions.run(
                `settle-${transfer.debtor_id}-${transfer.creditor_id}`,
                () => api.settle(roomId, transfer),
                i18n.t("confirm.settle", {
                  debtor: transfer.debtor_name,
                  creditor: transfer.creditor_name,
                  amount: money(transfer.cents, data.room.currency),
                }),
              )
            }
          />
          {adding ? (
            <ExpenseSheet data={data} i18n={i18n} actions={actions} onClose={() => setAdding(false)} />
          ) : (
            <MainButton text={i18n.t("expense.add")} onClick={() => setAdding(true)} />
          )}
        </>
      )}
    </Async>
  );
}
