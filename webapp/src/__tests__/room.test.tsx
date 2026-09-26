// @vitest-environment happy-dom
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App, { roomParam } from "../App";
import { ToastProvider } from "../components/controls";
import { translator } from "../i18n";
import type { Me, QueueData, SettingsData } from "../types";
import RoomView, { categoryPatch, daysText, RoomScreen } from "../views/RoomView";

const t = translator("ru");
const room = { id: 1, name: "906B", language: "ru", timezone: "Europe/Chisinau", currency: "MDL" };

function settings(overrides: Partial<SettingsData> = {}): SettingsData {
  return {
    room,
    me_member_id: 1,
    can_manage: true,
    quiet_hours: { start: "23:00", end: "08:00" },
    repeat_after_hours: 3,
    weekly_summary: true,
    categories: [
      {
        id: 10,
        name: "Хлеб",
        emoji: "🍞",
        kind: "bread",
        is_active: true,
        reminder_time: "18:00",
        reminder_days: [0, 1, 2, 3, 4, 5, 6],
        mode: "round_robin",
      },
      {
        id: 11,
        name: "Цветы",
        emoji: "🪴",
        kind: "custom",
        is_active: false,
        reminder_time: "09:00",
        reminder_days: [0, 3],
        mode: "fair",
      },
    ],
    members: [
      { member_id: 1, name: "Аня", username: null, is_creator: true, away_until: null, dm_available: true },
      { member_id: 2, name: "Боря", username: "borya", is_creator: false, away_until: "2026-10-01", dm_available: false },
    ],
    options: {
      languages: ["ru", "ro", "en"],
      timezones: ["Europe/Chisinau", "Europe/Bucharest", "UTC"],
      currencies: ["MDL", "EUR"],
      repeat_hours: [1, 2, 3],
      max_repeat_hours: 24,
      quiet_hours: [
        { start: "22:00", end: "08:00" },
        { start: "23:00", end: "08:00" },
      ],
      reminder_times: ["18:00", "20:00"],
      max_category_name: 32,
    },
    ...overrides,
  };
}

type Handler = (url: string, init: RequestInit) => Response | Promise<Response>;

/** A fake backend: GETs answer `read(url)`, everything else goes to `act`. */
function backend(read: (url: string) => unknown, act: Handler = () => ok("Сохранено ✅")) {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    if (init?.method) return act(url, init);
    return new Response(JSON.stringify(read(url)));
  });
  vi.stubGlobal("fetch", fetchMock);
  return {
    actions: () => fetchMock.mock.calls.filter(([, init]) => init?.method),
    gets: () => fetchMock.mock.calls.filter(([, init]) => !init?.method).map(([url]) => url),
  };
}

const ok = (message: string) => new Response(JSON.stringify({ message }));
const body = (call: [string, RequestInit?] | undefined) => JSON.parse(String(call?.[1]?.body));

beforeEach(() => {
  window.Telegram = {
    WebApp: {
      initData: "signed-init-data",
      platform: "unknown",
      isVersionAtLeast: () => true,
      onEvent: vi.fn(),
      offEvent: vi.fn(),
    } as never,
  };
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  delete window.Telegram;
  window.history.replaceState({}, "", "/");
});

describe("room screen", () => {
  it("lets admins change everything and shows the rest read-only", () => {
    const admin = renderToStaticMarkup(<RoomScreen data={settings()} i18n={t} />);
    expect(admin).toContain("Аня (ты)");
    expect(admin).toContain("👑 создатель");
    expect(admin).toContain("@borya");
    expect(admin).toContain("в отъезде до 01.10");
    expect(admin).toContain("⚠️ не открыл бота в личке");
    expect(admin.match(/aria-label="Убрать: /g)).toHaveLength(1); // not themselves
    expect(admin).toContain("23:00–08:00");
    expect(admin).toContain("через 3 ч");
    expect(admin).toContain("18:00 · каждый день");
    expect(admin).toContain("⏸ отключена");
    expect(admin.match(/class="chevron"/g)).toHaveLength(7); // 5 settings + 2 categories
    expect(admin).not.toContain("только админы");

    const roommate = renderToStaticMarkup(<RoomScreen data={settings({ can_manage: false })} i18n={t} />);
    expect(roommate).not.toContain("Убрать");
    expect(roommate).not.toContain('class="chevron"');
    expect(roommate).toContain("могут менять только админы чата и создатель комнаты");
    expect(roommate).toMatch(/role="switch"[^>]*disabled=""/);
    expect(roommate).toContain("➕ Добавить категорию"); // anybody may add one, as in the bot
    expect(roommate).toContain("🚪 Выйти из комнаты");
  });

  it("describes days and sends only what changed in a category", () => {
    expect(daysText([0, 2, 4], t)).toBe("Пн, Ср, Пт");
    expect(daysText([0, 1, 2, 3, 4, 5, 6], translator("en"))).toBe("every day");
    const [bread] = settings().categories;
    if (!bread) throw new Error("no category");
    const form = { name: "Хлеб", emoji: "🍞", time: "18:00", days: bread.reminder_days, mode: bread.mode };
    expect(categoryPatch(bread, form)).toBeNull();
    expect(categoryPatch(bread, { ...form, name: "  Свежий   хлеб ", days: [4, 0] })).toEqual({
      name: "Свежий хлеб",
      reminder_days: [0, 4],
    });
    expect(categoryPatch({ ...bread, emoji: "📌" }, { ...form, emoji: "" })).toBeNull(); // the default
    expect(categoryPatch(bread, { ...form, time: "07:30", mode: "fair" })).toEqual({
      reminder_time: "07:30",
      mode: "fair",
    });
    expect(roomParam("?room=5&tab=room")).toBe(5);
    expect(roomParam("?room=abc")).toBeUndefined();
  });
});

function renderRoom(data: SettingsData = settings(), act?: Handler) {
  const api = backend(() => data, act);
  const onRoomChange = vi.fn();
  render(
    <ToastProvider>
      <RoomView roomId={1} i18n={t} onRoomChange={onRoomChange} />
    </ToastProvider>,
  );
  return { api, onRoomChange };
}

describe("room actions", () => {
  it("changes a setting on its own screen", async () => {
    const { api, onRoomChange } = renderRoom();
    fireEvent.click(await screen.findByText("🌙 Тихие часы"));
    const sheet = screen.getByRole("dialog", { name: "🌙 Тихие часы" });
    const save = within(sheet).getByText("Сохранить") as HTMLButtonElement;
    expect(save.disabled).toBe(true); // nothing changed yet
    fireEvent.click(within(sheet).getByRole("radio", { name: "22:00–08:00" }));
    fireEvent.click(save);
    await screen.findByText("Сохранено ✅");
    const [url, init] = api.actions()[0] ?? ["", undefined];
    expect([url, init?.method]).toEqual(["/api/rooms/1/settings", "PATCH"]);
    expect(body(api.actions()[0])).toEqual({ quiet_hours: { start: "22:00", end: "08:00" } });
    expect((init?.headers as Record<string, string>)["Idempotency-Key"]).toBeTruthy();
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    expect(onRoomChange).toHaveBeenCalledOnce(); // e.g. the language: the app reloads the rooms

    fireEvent.click(screen.getByText("🌙 Тихие часы"));
    fireEvent.click(screen.getByRole("radio", { name: "🔔 Без тихих часов" }));
    fireEvent.click(screen.getByText("Сохранить"));
    await waitFor(() => expect(api.actions()).toHaveLength(2));
    expect(body(api.actions()[1])).toEqual({ quiet_hours: null });

    fireEvent.click(screen.getByRole("switch"));
    await waitFor(() => expect(api.actions()).toHaveLength(3));
    expect(body(api.actions()[2])).toEqual({ weekly_summary: false });
  });

  it("edits a category and asks before switching the queue mode", async () => {
    const confirm = vi.fn((_question: string) => false);
    vi.stubGlobal("confirm", confirm);
    const { api } = renderRoom();
    fireEvent.click(await screen.findByText("🍞 Хлеб"));
    const sheet = screen.getByRole("dialog", { name: "🍞 Хлеб" });
    fireEvent.change(within(sheet).getByLabelText("⏰ Время напоминания"), { target: { value: "07:30" } });
    fireEvent.click(within(sheet).getByText("Вс"));
    fireEvent.click(within(sheet).getByRole("radio", { name: "Справедливо — кто меньше сделал за 30 дней" }));
    fireEvent.click(within(sheet).getByText("Сохранить"));
    await waitFor(() => expect(confirm).toHaveBeenCalledOnce());
    expect(confirm).toHaveBeenCalledWith("Сменить режим очереди? Долги за пропуски и ⭐ в этой категории начнутся с нуля.");
    expect(api.actions()).toHaveLength(0);

    confirm.mockReturnValue(true);
    fireEvent.click(within(sheet).getByText("Сохранить"));
    await screen.findByText("Сохранено ✅");
    expect(api.actions()[0]?.[0]).toBe("/api/rooms/1/categories/10");
    expect(body(api.actions()[0])).toEqual({
      reminder_time: "07:30",
      reminder_days: [0, 1, 2, 3, 4, 5],
      mode: "fair",
    });
  });

  it("deletes a category only after confirmation", async () => {
    const confirm = vi.fn((_question: string) => true);
    vi.stubGlobal("confirm", confirm);
    const { api } = renderRoom(settings(), () => ok("Категория 🍞 Хлеб удалена"));
    fireEvent.click(await screen.findByText("🍞 Хлеб"));
    fireEvent.click(screen.getByText("🗑 Удалить"));
    await screen.findByText("Категория 🍞 Хлеб удалена");
    expect(confirm.mock.calls[0]?.[0]).toMatch(/^Удалить категорию 🍞 Хлеб\?/);
    const [url, init] = api.actions()[0] ?? ["", undefined];
    expect([url, init?.method, init?.body]).toEqual(["/api/rooms/1/categories/10", "DELETE", undefined]);
  });

  it("lets any roommate add a category but only admins open the settings", async () => {
    const { api } = renderRoom(settings({ can_manage: false }), () => ok("✅ Категория 🧽 Губки добавлена!"));
    fireEvent.click(await screen.findByText("🍞 Хлеб"));
    fireEvent.click(screen.getByText("🗣 Язык"));
    expect(screen.queryByRole("dialog")).toBeNull();

    fireEvent.click(screen.getByText("➕ Добавить категорию"));
    const sheet = screen.getByRole("dialog", { name: "➕ Новая категория" });
    fireEvent.change(within(sheet).getByLabelText("Эмодзи"), { target: { value: "🧽" } });
    fireEvent.change(within(sheet).getByLabelText("Название"), { target: { value: "Губки" } });
    fireEvent.click(within(sheet).getByText("Добавить категорию"));
    await screen.findByText("✅ Категория 🧽 Губки добавлена!");
    expect(api.actions()[0]?.[0]).toBe("/api/rooms/1/categories");
    expect(body(api.actions()[0])).toEqual({ name: "Губки", emoji: "🧽" });
  });

  it("removes a roommate, leaves the room and exports after the right questions", async () => {
    const confirm = vi.fn((_question: string) => true);
    vi.stubGlobal("confirm", confirm);
    const { api, onRoomChange } = renderRoom(settings(), (url) => ok(url.endsWith("/export") ? "📦 Отправил" : "Готово"));
    fireEvent.click(await screen.findByLabelText("Убрать: Боря"));
    await waitFor(() => expect(api.actions()).toHaveLength(1));
    expect(confirm).toHaveBeenLastCalledWith(
      "Убрать Боря из комнаты? Жилец пропадёт из всех очередей, история сохранится.",
    );
    expect(api.actions()[0]?.[0]).toBe("/api/rooms/1/members/2/remove");

    fireEvent.click(screen.getByText("🚪 Выйти из комнаты"));
    await waitFor(() => expect(onRoomChange).toHaveBeenCalledOnce());
    expect(confirm).toHaveBeenLastCalledWith(
      "Точно выйти из комнаты? Ты пропадёшь из всех очередей (история сохранится).",
    );
    expect(api.actions()[1]?.[0]).toBe("/api/rooms/1/leave");

    confirm.mockClear();
    fireEvent.click(screen.getByText("📦 Прислать CSV в личку"));
    await screen.findByText("📦 Отправил");
    expect(confirm).not.toHaveBeenCalled(); // nothing dangerous
    expect(api.actions()[2]?.[0]).toBe("/api/rooms/1/export");
  });

  it("explains why the settings can't be changed", async () => {
    const refusal = {
      detail: { code: "err-not-admin", message: "Настройки могут менять только админы чата и создатель комнаты." },
    };
    renderRoom(settings(), () => new Response(JSON.stringify(refusal), { status: 403 }));
    fireEvent.click(await screen.findByText("💱 Валюта"));
    fireEvent.click(screen.getByRole("radio", { name: "EUR" }));
    fireEvent.click(screen.getByText("Сохранить"));
    const toast = await screen.findByText("Настройки могут менять только админы чата и создатель комнаты.");
    expect(toast.className).toContain("error");
    expect(screen.getByRole("dialog")).toBeTruthy(); // stays open
  });
});

describe("rooms", () => {
  const queue = (id: number, name: string): QueueData => ({
    room: { ...room, id, name },
    me_member_id: 1,
    today: "2026-09-26",
    away_max_days: 365,
    members: [{ member_id: 1, name: "Аня" }],
    categories: [],
    away: [],
  });

  it("joins the room the bot's button opened", async () => {
    window.history.replaceState({}, "", "/?room=5");
    let joined = false;
    const other = { ...room, id: 5, name: "Комната 12" };
    const me = (): Me => ({
      user_id: 1,
      first_name: "Аня",
      language_code: "ru",
      rooms: joined ? [other] : [],
      initial_room_id: joined ? 5 : null,
      invite: joined ? null : other,
    });
    const api = backend(
      (url) => (url.startsWith("/api/me") ? me() : queue(5, "Комната 12")),
      () => {
        joined = true;
        return ok("Добро пожаловать! 🎉");
      },
    );
    render(<App />);
    expect(await screen.findByText("Вступить в «Комната 12»?")).toBeTruthy();
    expect(screen.queryByText("Не сейчас")).toBeNull(); // no other room to go to
    fireEvent.click(screen.getByText("🏠 Я живу здесь"));
    await screen.findByText("Добро пожаловать! 🎉");
    expect(await screen.findByText("🏠 Комната 12")).toBeTruthy();
    expect(api.actions()[0]?.[0]).toBe("/api/rooms/5/join");
    expect(api.gets().filter((url) => url.startsWith("/api/me"))).toEqual(["/api/me?room=5", "/api/me?room=5"]);
  });

  it("makes the room switched to the bot's active room", async () => {
    const me: Me = {
      user_id: 1,
      first_name: "Аня",
      language_code: "ru",
      rooms: [room, { ...room, id: 2, name: "Дача" }],
      initial_room_id: 1,
      invite: null,
    };
    const api = backend((url) => (url === "/api/me" ? me : url.includes("/2/") ? queue(2, "Дача") : queue(1, "906B")));
    render(<App />);
    fireEvent.change(await screen.findByLabelText("Комната"), { target: { value: "2" } });
    expect(await screen.findByText("🏠 Дача")).toBeTruthy();
    await waitFor(() => expect(api.actions()).toHaveLength(1));
    expect(api.actions()[0]?.[0]).toBe("/api/me/room");
    expect(body(api.actions()[0])).toEqual({ room_id: 2 });
    await waitFor(() => expect(api.gets()).toContain("/api/rooms/2/queue"));
  });
});
