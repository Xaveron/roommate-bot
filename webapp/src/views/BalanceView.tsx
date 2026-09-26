import { api } from "../api";
import { Async, Avatar } from "../components/common";
import { dateTime, money } from "../format";
import { useLoad } from "../hooks";
import type { Translator } from "../i18n";
import type { BalanceData } from "../types";

export function BalanceSummary({ data, i18n }: { data: BalanceData; i18n: Translator }) {
  const { currency, timezone } = data.room;
  const mine = data.balances.find((b) => b.member_id === data.me_member_id)?.cents ?? 0;
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
                          {line.member_id === data.me_member_id && ` (${i18n.t("common.you")})`}
                        </span>
                      </span>
                    </td>
                    <td className={`num ${line.cents > 0 ? "pos" : "neg"}`}>{money(line.cents, currency, true)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
          <h3 className="section-title">{i18n.t("balance.transfers")}</h3>
          <section className="card">
            <table>
              <tbody>
                {data.transfers.map((transfer) => (
                  <tr key={`${transfer.debtor_id}-${transfer.creditor_id}`}>
                    <td>
                      {transfer.debtor_name} → <b>{transfer.creditor_name}</b>
                    </td>
                    <td className="num">{money(transfer.cents, currency)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="hint">{i18n.t("balance.settleHint")}</p>
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

export default function BalanceView({ roomId, i18n }: { roomId: number; i18n: Translator }) {
  const state = useLoad(() => api.balance(roomId), [roomId]);
  return <Async state={state} i18n={i18n}>{(data) => <BalanceSummary data={data} i18n={i18n} />}</Async>;
}
