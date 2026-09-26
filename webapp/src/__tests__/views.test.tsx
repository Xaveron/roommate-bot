import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { chooseRoom, chooseTab } from "../App";
import { translator } from "../i18n";
import type { BalanceData, HistoryData, Me, QueueData, StatsData } from "../types";
import { BalanceSummary } from "../views/BalanceView";
import { HistoryTable } from "../views/HistoryView";
import { QueueList } from "../views/QueueView";
import { StatsReport } from "../views/StatsView";

const t = translator("ru");
const room = { id: 1, name: "906B", language: "ru", timezone: "Europe/Chisinau", currency: "MDL" };
const bread = { id: 10, name: "Хлеб", emoji: "🍞", kind: "bread", is_active: true };

describe("views", () => {
  it("renders the queue with statuses, marks and away roommates", () => {
    const data: QueueData = {
      room,
      me_member_id: 2,
      members: [
        { member_id: 1, name: "Аня" },
        { member_id: 2, name: "Боря" },
        { member_id: 4, name: "Гриша" },
      ],
      categories: [
        {
          id: 10,
          name: "Хлеб",
          emoji: "🍞",
          kind: "bread",
          mode: "fair",
          reminder_time: "18:00",
          current: { member_id: 2, name: "Боря" },
          status: "pending",
          remind_on: null,
          upcoming: [{ member_id: 1, name: "Аня" }],
          marks: [{ member_id: 2, skip_debt: 1, credit: 0 }],
          fair_counts: { "1": 3, "2": 1 },
        },
      ],
      away: [{ member_id: 3, name: "Вика", until: "2026-10-15" }],
    };
    const html = renderToStaticMarkup(<QueueList data={data} i18n={t} />);
    expect(html).toContain("Твоя очередь!");
    expect(html).toContain("ждём ответа");
    expect(html).toContain("Боря ⚠️");
    expect(html).toContain("Гриша 0 · Боря 1 · Аня 3");
    expect(html).toContain("справедливо");
    expect(html).toContain("до 15.10");
  });

  it("renders history rows in the room timezone and marks disputed ones", () => {
    const data: HistoryData = {
      room,
      categories: [bread],
      items: [
        {
          id: 1,
          category_id: 10,
          member_id: 1,
          member_name: "Аня",
          status: "done",
          review: "disputed",
          amount_cents: 2350,
          created_at: "2026-09-26T15:30:00Z",
        },
      ],
    };
    const html = renderToStaticMarkup(
      <HistoryTable data={data} i18n={t} selected={undefined} onSelect={() => {}} />,
    );
    expect(html).toContain("26.09<div class=\"sub\">18:30</div>");
    expect(html).toContain("🍞 ✅ сделано");
    expect(html).toContain("спорно");
    expect(html).toContain("23.50 MDL");
    expect(html).toContain('class="disputed"');
  });

  it("renders the balance from the caller's point of view", () => {
    const data: BalanceData = {
      room,
      me_member_id: 2,
      balances: [
        { member_id: 1, name: "Аня", cents: 3000 },
        { member_id: 2, name: "Боря", cents: -3000 },
      ],
      transfers: [{ debtor_id: 2, debtor_name: "Боря", creditor_id: 1, creditor_name: "Аня", cents: 3000 }],
      expenses: [
        {
          id: 1,
          payer_name: "Аня",
          amount_cents: 6000,
          description: "пицца",
          is_settlement: false,
          created_at: "2026-09-26T15:30:00Z",
          shares: [
            { name: "Аня", cents: 3000 },
            { name: "Боря", cents: 3000 },
          ],
        },
      ],
    };
    const html = renderToStaticMarkup(<BalanceSummary data={data} i18n={t} />);
    expect(html).toContain("Твой долг");
    expect(html).toContain("30 MDL");
    expect(html).toContain("+30 MDL");
    expect(html).toContain("Делим на: Аня, Боря");
  });

  it("renders statistics with the leaderboard", () => {
    const warn = vi.spyOn(console, "warn").mockImplementation(() => {});
    const data: StatsData = {
      room,
      year: 2026,
      month: 9,
      has_next: false,
      categories: [bread],
      members: [
        {
          member_id: 1,
          name: "Аня",
          done: 3,
          skipped: 0,
          out_of_turn: 1,
          spent_cents: 2350,
          by_category: { "10": 3 },
          badges: ["first_duty"],
        },
      ],
      done: 3,
      skipped: 0,
      disputed: 1,
      spent_cents: 2350,
      daily: [{ day: "2026-09-01", done: 3 }],
    };
    const html = renderToStaticMarkup(<StatsReport data={data} i18n={t} scheme="light" onMonth={() => {}} />);
    expect(html).toContain("Сентябрь 2026");
    expect(html).toContain("🥇 Аня");
    expect(html).toContain('title="🌱 Первый шаг"');
    expect(html).toContain('<div class="badges" title="🌱 Первый шаг">🌱</div>');
    expect(html).toMatch(/disabled=""[^>]*>▶/);
    warn.mockRestore();
  });

  it("opens the room from the button, else the suggested one", () => {
    const me: Me = {
      user_id: 1,
      first_name: "Аня",
      language_code: "ru",
      rooms: [room, { ...room, id: 2, name: "Другая" }],
      initial_room_id: 1,
    };
    expect(chooseRoom(me, "?room=2")).toBe(2);
    expect(chooseRoom(me, "?room=99")).toBe(1);
    expect(chooseRoom({ ...me, initial_room_id: null }, "")).toBe(1);
    expect(chooseRoom({ ...me, rooms: [], initial_room_id: null }, "")).toBeUndefined();
    expect(chooseTab("?tab=balance")).toBe("balance");
    expect(chooseTab("?tab=nope")).toBe("queue");
  });
});
