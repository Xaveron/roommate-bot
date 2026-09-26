import { useState } from "react";
import { api } from "../api";
import { DailyChart, MemberChart } from "../components/charts";
import { Async } from "../components/common";
import { money } from "../format";
import { useLoad } from "../hooks";
import type { Key, Translator } from "../i18n";
import { haptic } from "../telegram";
import type { StatsData } from "../types";

const MEDALS = ["🥇", "🥈", "🥉"];

const badgeName = (i18n: Translator, code: string) => i18n.t(`badge.${code}` as Key);
/** Localized names start with the badge's emoji: "👑 Хлебный король" -> "👑". */
const badgeIcon = (i18n: Translator, code: string) => badgeName(i18n, code).split(" ")[0] ?? "";

export function StatsReport({
  data,
  i18n,
  scheme,
  onMonth,
}: {
  data: StatsData;
  i18n: Translator;
  scheme: "light" | "dark";
  onMonth: (year: number, month: number) => void;
}) {
  const shift = (delta: number) => {
    const index = data.year * 12 + (data.month - 1) + delta;
    haptic.select();
    onMonth(Math.floor(index / 12), (index % 12) + 1);
  };
  const title = `${i18n.t(`month.${data.month}` as Key)} ${data.year}`;
  const earned = [...new Set(data.members.flatMap((m) => m.badges))];
  const currency = data.room.currency;
  return (
    <>
      <div className="month-nav">
        <button type="button" className="icon-button" aria-label={i18n.t("stats.prev")} onClick={() => shift(-1)}>
          ◀
        </button>
        <h2>{title}</h2>
        <button
          type="button"
          className="icon-button"
          aria-label={i18n.t("stats.next")}
          disabled={!data.has_next}
          onClick={() => shift(1)}
        >
          ▶
        </button>
      </div>

      <div className="tiles">
        <div className="tile">
          <div className="label">✅ {i18n.t("stats.done")}</div>
          <div className="value">{data.done}</div>
        </div>
        <div className="tile">
          <div className="label">⏭ {i18n.t("stats.skipped")}</div>
          <div className="value">{data.skipped}</div>
        </div>
        <div className="tile">
          <div className="label">🤨 {i18n.t("stats.disputed")}</div>
          <div className="value">{data.disputed}</div>
        </div>
        <div className="tile">
          <div className="label">💸 {i18n.t("stats.spent")}</div>
          <div className="value">{money(data.spent_cents, currency)}</div>
        </div>
      </div>

      {data.done === 0 ? (
        <p className="center">{i18n.t("stats.empty")}</p>
      ) : (
        <>
          <section className="card">
            <h2>{i18n.t("stats.byMember")}</h2>
            <MemberChart members={data.members} categories={data.categories} scheme={scheme} />
          </section>
          <section className="card">
            <h2>{i18n.t("stats.daily")}</h2>
            <DailyChart daily={data.daily} label={i18n.t("stats.done")} scheme={scheme} />
          </section>
        </>
      )}

      <h3 className="section-title">{i18n.t("stats.leaderboard")}</h3>
      <section className="card">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>{i18n.t("stats.who")}</th>
                <th className="num">{i18n.t("stats.done")}</th>
                <th className="num">{i18n.t("stats.skipped")}</th>
                <th className="num">{i18n.t("stats.spent")}</th>
              </tr>
            </thead>
            <tbody>
              {data.members.map((member, index) => (
                <tr key={member.member_id}>
                  <td>
                    <div className="name">
                      {member.done > 0 && index < MEDALS.length ? `${MEDALS[index]} ` : `${index + 1}. `}
                      {member.name}
                    </div>
                    {member.badges.length > 0 && (
                      <div className="badges" title={member.badges.map((b) => badgeName(i18n, b)).join(", ")}>
                        {member.badges.map((b) => badgeIcon(i18n, b)).join("")}
                      </div>
                    )}
                  </td>
                  <td className="num">{member.done}</td>
                  <td className="num">{member.skipped}</td>
                  <td className="num">{member.spent_cents ? money(member.spent_cents, currency) : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {earned.length > 0 && <p className="hint">{earned.map((b) => badgeName(i18n, b)).join(" · ")}</p>}
      </section>
    </>
  );
}

export default function StatsView({
  roomId,
  i18n,
  scheme,
}: {
  roomId: number;
  i18n: Translator;
  scheme: "light" | "dark";
}) {
  const [period, setPeriod] = useState<{ year?: number; month?: number }>({});
  const state = useLoad(() => api.stats(roomId, period.year, period.month), [roomId, period.year, period.month]);
  return (
    <Async state={state} i18n={i18n}>
      {(data) => (
        <StatsReport data={data} i18n={i18n} scheme={scheme} onMonth={(year, month) => setPeriod({ year, month })} />
      )}
    </Async>
  );
}
