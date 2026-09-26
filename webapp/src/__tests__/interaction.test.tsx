// @vitest-environment happy-dom
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { BackButton, MainButton, ToastProvider } from "../components/controls";
import { REFRESH_MS } from "../hooks";
import { translator } from "../i18n";
import type { BalanceData, HistoryData, QueueData, ShoppingData } from "../types";
import BalanceView from "../views/BalanceView";
import HistoryView from "../views/HistoryView";
import QueueView from "../views/QueueView";
import ShoppingView from "../views/ShoppingView";

const t = translator("ru");
const room = { id: 1, name: "906B", language: "ru", timezone: "Europe/Chisinau", currency: "MDL" };

function queue(overrides: Partial<QueueData["categories"][number]> = {}): QueueData {
  return {
    room,
    me_member_id: 2,
    today: "2026-09-26",
    away_max_days: 365,
    members: [
      { member_id: 1, name: "Аня" },
      { member_id: 2, name: "Боря" },
    ],
    categories: [
      {
        id: 10,
        name: "Хлеб",
        emoji: "🍞",
        kind: "bread",
        mode: "round_robin",
        reminder_time: "18:00",
        current: { member_id: 2, name: "Боря" },
        assignment_id: 7,
        status: "pending",
        remind_on: null,
        upcoming: [{ member_id: 1, name: "Аня" }],
        marks: [],
        fair_counts: null,
        ...overrides,
      },
    ],
    away: [],
  };
}

type Handler = (url: string, init?: RequestInit) => Response | Promise<Response>;

/** A fake backend: every GET answers `data`, POSTs go to `onPost`. */
function backend(data: unknown, onPost: Handler) {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method === "POST") return onPost(url, init);
    return new Response(JSON.stringify(data));
  });
  vi.stubGlobal("fetch", fetchMock);
  return {
    fetchMock,
    posts: () => fetchMock.mock.calls.filter(([, init]) => init?.method === "POST"),
    gets: () => fetchMock.mock.calls.filter(([, init]) => init?.method !== "POST"),
  };
}

const ok = (message: string) => new Response(JSON.stringify({ message }));

function telegram(platform: string, extra: Record<string, unknown> = {}) {
  window.Telegram = {
    WebApp: {
      initData: "signed-init-data",
      platform,
      isVersionAtLeast: () => true,
      onEvent: vi.fn(),
      offEvent: vi.fn(),
      ...extra,
    } as never,
  };
}

function renderQueue() {
  return render(
    <ToastProvider>
      <QueueView roomId={1} i18n={t} />
    </ToastProvider>,
  );
}

beforeEach(() => telegram("unknown")); // a browser: the page draws its own buttons
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.useRealTimers();
  delete window.Telegram;
});

describe("queue actions", () => {
  it("marks the turn done with what it cost", async () => {
    const api = backend(queue(), () => ok("✅ Записал: 30 MDL за 🍞 Хлеб"));
    renderQueue();
    fireEvent.click(await screen.findByText("✅ Готово"));

    const sheet = screen.getByRole("dialog", { name: "✅ Готово" });
    expect(sheet).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Сколько стоило, MDL"), { target: { value: "30" } });
    fireEvent.click(screen.getByText("Сохранить"));

    expect(await screen.findByText("✅ Записал: 30 MDL за 🍞 Хлеб")).toBeTruthy();
    const [url, init] = api.posts()[0] ?? [];
    expect(url).toBe("/api/rooms/1/categories/10/done");
    expect(JSON.parse(String(init?.body))).toEqual({ in_turn: true, amount: "30" });
    const sent = init?.headers as Record<string, string>;
    expect(sent.Authorization).toBe("tma signed-init-data");
    expect(sent["Idempotency-Key"]).toBeTruthy();
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    await waitFor(() => expect(api.gets().length).toBe(2)); // reloaded after the action
  });

  it("asks before passing the turn on", async () => {
    const api = backend(queue(), () => ok("⏭ Передаю очередь дальше"));
    const confirm = vi.fn(() => false);
    vi.stubGlobal("confirm", confirm);
    renderQueue();
    fireEvent.click(await screen.findByText("⏭ Не могу сегодня"));
    await waitFor(() => expect(confirm).toHaveBeenCalledOnce());
    expect(api.posts()).toHaveLength(0);

    confirm.mockReturnValue(true);
    fireEvent.click(screen.getByText("⏭ Не могу сегодня"));
    expect(await screen.findByText("⏭ Передаю очередь дальше")).toBeTruthy();
    expect(api.posts()[0]?.[0]).toBe("/api/rooms/1/turns/7/decline");
  });

  it("sends a double tap once", async () => {
    let answer: (response: Response) => void = () => {};
    const api = backend(queue(), () => new Promise<Response>((resolve) => (answer = resolve)));
    renderQueue();
    const accept = await screen.findByText("🛒 Куплю");
    fireEvent.click(accept);
    fireEvent.click(accept);
    await waitFor(() => expect(api.posts()).toHaveLength(1));
    expect(api.posts()[0]?.[0]).toBe("/api/rooms/1/turns/7/accept");
    await act(async () => answer(ok("👍 Жду «Готово»")));
    expect(await screen.findByText("👍 Жду «Готово»")).toBeTruthy();
    expect(api.posts()).toHaveLength(1);
  });

  it("explains a refusal in plain words", async () => {
    const refusal = { detail: { code: "err-turn-changed", message: "Очередь только что изменилась — проверь ещё раз 🙂" } };
    backend(queue({ kind: "trash", name: "Мусор", emoji: "🗑" }), () =>
      new Response(JSON.stringify(refusal), { status: 409 }),
    );
    renderQueue();
    fireEvent.click(await screen.findByText("✅ Готово")); // trash: no amount to ask
    const toast = await screen.findByText("Очередь только что изменилась — проверь ещё раз 🙂");
    expect(toast.className).toContain("error");
  });

  it("offers roommates the out-of-turn mark", async () => {
    const api = backend(queue({ current: { member_id: 1, name: "Аня" } }), () => ok("✅ Засчитано!"));
    renderQueue();
    fireEvent.click(await screen.findByText("🦸 Сделал(а) вне очереди"));
    screen.getByRole("dialog", { name: "🦸 Вне очереди" });
    fireEvent.click(screen.getByText("Отметить без суммы"));
    await screen.findByText("✅ Засчитано!");
    expect(JSON.parse(String(api.posts()[0]?.[1]?.body))).toEqual({ in_turn: false, amount: null });
  });

  it("goes away for a week", async () => {
    const api = backend(queue(), () => ok("🏖 Готово"));
    renderQueue();
    fireEvent.click(await screen.findByText("🏖 Уезжаю"));
    fireEvent.click(screen.getByRole("radio", { name: "Неделю" }));
    fireEvent.click(screen.getByText("Уезжаю до 02.10"));
    await screen.findByText("🏖 Готово");
    expect(api.posts()[0]?.[0]).toBe("/api/rooms/1/away");
    expect(JSON.parse(String(api.posts()[0]?.[1]?.body))).toEqual({ days: 7 });
  });

  it("picks up changes made in the bot by itself", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const api = backend(queue(), () => ok(""));
    renderQueue();
    await screen.findByText("✅ Готово");
    expect(api.gets()).toHaveLength(1);
    await act(async () => {
      vi.advanceTimersByTime(REFRESH_MS);
    });
    await waitFor(() => expect(api.gets()).toHaveLength(2));
    await act(async () => {
      document.dispatchEvent(new Event("visibilitychange")); // back from another app
    });
    await waitFor(() => expect(api.gets()).toHaveLength(3));
  });
});

function renderView(view: React.ReactElement) {
  return render(<ToastProvider>{view}</ToastProvider>);
}

describe("shopping, money and votes", () => {
  it("adds to the shopping list and tells everybody about the trip", async () => {
    const list: ShoppingData = {
      room,
      items: [{ id: 5, text: "соль", added_by: "Аня", created_at: "2026-09-26T10:00:00Z" }],
    };
    const api = backend(list, (url) =>
      ok(url.endsWith("/going") ? "📣 Сообщил всем!" : url.endsWith("/bought") ? "Отмечено ✅" : "🛒 Добавлено"),
    );
    vi.stubGlobal("confirm", vi.fn(() => true));
    renderView(<ShoppingView roomId={1} i18n={t} />);
    const input = await screen.findByLabelText("Что купить? Можно через запятую");
    fireEvent.change(input, { target: { value: "молоко, хлеб" } });
    fireEvent.click(screen.getByText("Добавить"));
    await screen.findByText("🛒 Добавлено");
    expect(JSON.parse(String(api.posts()[0]?.[1]?.body))).toEqual({ text: "молоко, хлеб" });
    await waitFor(() => expect((input as HTMLInputElement).value).toBe(""));

    fireEvent.click(screen.getByLabelText("Купили: соль"));
    await screen.findByText("Отмечено ✅");
    expect(api.posts()[1]?.[0]).toBe("/api/rooms/1/shopping/5/bought");

    fireEvent.click(screen.getByText("🛒 Иду в магазин")); // the MainButton
    await screen.findByText("📣 Сообщил всем!");
    expect(api.posts()[2]?.[0]).toBe("/api/rooms/1/shopping/going");
  });

  it("adds an expense and settles a debt", async () => {
    const balance: BalanceData = {
      room,
      me_member_id: 2,
      members: [
        { member_id: 1, name: "Аня", at_home: true },
        { member_id: 2, name: "Боря", at_home: true },
        { member_id: 3, name: "Вика", at_home: false },
      ],
      balances: [
        { member_id: 1, name: "Аня", cents: 3000 },
        { member_id: 2, name: "Боря", cents: -3000 },
      ],
      transfers: [{ debtor_id: 2, debtor_name: "Боря", creditor_id: 1, creditor_name: "Аня", cents: 3000 }],
      expenses: [],
    };
    const api = backend(balance, () => ok("Сохранено ✅"));
    const confirm = vi.fn(() => true);
    vi.stubGlobal("confirm", confirm);
    renderView(<BalanceView roomId={1} i18n={t} />);

    fireEvent.click(await screen.findByText("Я вернул(а)"));
    await screen.findByText("Сохранено ✅");
    expect(confirm).toHaveBeenCalledWith("Отметить возврат долга: Боря → Аня, 30 MDL?");
    expect(JSON.parse(String(api.posts()[0]?.[1]?.body))).toEqual({ debtor_id: 2, creditor_id: 1, cents: 3000 });

    fireEvent.click(screen.getByText("➕ Добавить трату"));
    screen.getByRole("dialog", { name: "💸 Новая трата" });
    fireEvent.change(screen.getByLabelText("Сумма, MDL"), { target: { value: "90" } });
    fireEvent.change(screen.getByLabelText("На что"), { target: { value: "пицца" } });
    expect(screen.getByText("Каждому ≈ 45 MDL")).toBeTruthy(); // Anya and Borya are at home
    fireEvent.click(screen.getByText("Вика 🏖"));
    expect(screen.getByText("Каждому ≈ 30 MDL")).toBeTruthy();
    fireEvent.click(screen.getByText("Сохранить трату"));
    await waitFor(() => expect(api.posts()).toHaveLength(2));
    expect(JSON.parse(String(api.posts()[1]?.[1]?.body))).toEqual({
      amount: "90",
      description: "пицца",
      member_ids: [1, 2, 3],
    });
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
  });

  it("votes on a roommate's record", async () => {
    const history: HistoryData = {
      room,
      me_member_id: 1,
      categories: [{ id: 10, name: "Хлеб", emoji: "🍞", kind: "bread", is_active: true }],
      items: [
        {
          id: 3,
          category_id: 10,
          member_id: 2,
          member_name: "Боря",
          status: "done",
          review: "open",
          amount_cents: null,
          created_at: "2026-09-26T15:00:00Z",
          votes_up: 0,
          votes_down: 0,
          my_vote: null,
          can_vote: true,
        },
      ],
    };
    const api = backend(history, () => ok("Голос учтён 👌"));
    renderView(<HistoryView roomId={1} i18n={t} />);
    fireEvent.click(await screen.findByLabelText("Оспорить"));
    await screen.findByText("Голос учтён 👌");
    expect(api.posts()[0]?.[0]).toBe("/api/rooms/1/duties/3/vote");
    expect(JSON.parse(String(api.posts()[0]?.[1]?.body))).toEqual({ vote: "down" });
  });
});

describe("Telegram buttons", () => {
  function nativeTelegram() {
    const handlers: Record<string, () => void> = {};
    const mainButton = {
      setParams: vi.fn(),
      show: vi.fn(),
      hide: vi.fn(),
      showProgress: vi.fn(),
      hideProgress: vi.fn(),
      onClick: vi.fn((h: () => void) => (handlers.main = h)),
      offClick: vi.fn(),
    };
    const backButton = {
      show: vi.fn(),
      hide: vi.fn(),
      onClick: vi.fn((h: () => void) => (handlers.back = h)),
      offClick: vi.fn(),
    };
    telegram("ios", { MainButton: mainButton, BackButton: backButton });
    return { handlers, mainButton, backButton };
  }

  it("drives Telegram's MainButton instead of drawing one", () => {
    const { handlers, mainButton } = nativeTelegram();
    const onClick = vi.fn();
    const view = render(<MainButton text="Сохранить" onClick={onClick} />);
    expect(view.container.innerHTML).toBe("");
    expect(mainButton.setParams).toHaveBeenLastCalledWith({ text: "Сохранить", is_active: true, is_visible: true });
    handlers.main?.();
    expect(onClick).toHaveBeenCalledOnce();

    view.rerender(<MainButton text="Сохранить" onClick={onClick} progress />);
    expect(mainButton.showProgress).toHaveBeenCalled();
    handlers.main?.();
    expect(onClick).toHaveBeenCalledOnce(); // ignored while the action runs

    view.unmount();
    expect(mainButton.offClick).toHaveBeenCalled();
    expect(mainButton.hide).toHaveBeenCalled();
  });

  it("shows Telegram's back arrow while a form is open", () => {
    const { handlers, backButton } = nativeTelegram();
    const onClose = vi.fn();
    const view = render(<BackButton onClick={onClose} />);
    expect(backButton.show).toHaveBeenCalled();
    handlers.back?.();
    expect(onClose).toHaveBeenCalledOnce();
    view.unmount();
    expect(backButton.hide).toHaveBeenCalled();
  });
});
