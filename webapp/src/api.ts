import { initData } from "./telegram";
import type {
  ActionResult,
  BalanceData,
  CategoryPatch,
  HistoryData,
  Me,
  QueueData,
  RoomSettingsPatch,
  SettingsData,
  ShoppingData,
  StatsData,
  Transfer,
} from "./types";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
    /** The backend's error code (e.g. "err-turn-changed"); 0 status = no connection. */
    readonly code?: string,
    /** Human-readable explanation in the room's language, when the backend gave one. */
    readonly text?: string,
  ) {
    super(message);
  }
}

type Fetch = typeof fetch;

function authHeaders(auth: string): Record<string, string> {
  return { Authorization: `tma ${auth}` };
}

async function failure(response: Response): Promise<ApiError> {
  let code: string | undefined;
  let text: string | undefined;
  try {
    const body = (await response.json()) as { detail?: unknown };
    const detail = body.detail;
    if (detail && typeof detail === "object" && "message" in detail) {
      ({ code, message: text } = detail as { code?: string; message?: string });
    }
  } catch {
    // Not JSON (e.g. a proxy error page).
  }
  return new ApiError(response.status, `${response.status} ${response.statusText}`, code, text);
}

/** GET a JSON endpoint, authorized with Telegram initData (checked by the backend). */
export async function getJson<T>(
  path: string,
  params: Record<string, string | number | undefined> = {},
  fetchImpl: Fetch = fetch,
  auth: string = initData(),
): Promise<T> {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined) query.set(key, String(value));
  }
  const url = query.size ? `${path}?${query}` : path;
  const response = await fetchImpl(url, { headers: authHeaders(auth) });
  if (!response.ok) throw await failure(response);
  return (await response.json()) as T;
}

export function newKey(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) return crypto.randomUUID();
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
}

const RETRY_DELAY_MS = 800;

type Method = "POST" | "PATCH" | "DELETE";

/**
 * Send an action. Every call carries a fresh Idempotency-Key; when the connection drops, the
 * request is repeated once with the same key, so the backend never does the action twice.
 */
export async function sendJson<T>(
  method: Method,
  path: string,
  body: unknown = undefined,
  fetchImpl: Fetch = fetch,
  auth: string = initData(),
  key: string = newKey(),
): Promise<T> {
  const init: RequestInit = {
    method,
    headers: {
      ...authHeaders(auth),
      "Content-Type": "application/json",
      "Idempotency-Key": key,
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  };
  let response: Response;
  try {
    response = await fetchImpl(path, init);
  } catch {
    await new Promise((resolve) => setTimeout(resolve, RETRY_DELAY_MS));
    try {
      response = await fetchImpl(path, init);
    } catch {
      throw new ApiError(0, "network error", "network");
    }
  }
  if (!response.ok) throw await failure(response);
  return (await response.json()) as T;
}

/** POST an action (see `sendJson`). */
export function postJson<T>(
  path: string,
  body: unknown = undefined,
  fetchImpl: Fetch = fetch,
  auth: string = initData(),
  key: string = newKey(),
): Promise<T> {
  return sendJson<T>("POST", path, body, fetchImpl, auth, key);
}

const room = (id: number) => `/api/rooms/${id}`;

export const api = {
  /** `roomId`: the room the app was opened for (to be invited if the caller hasn't joined). */
  me: (roomId?: number) => getJson<Me>("/api/me", { room: roomId }),
  queue: (id: number) => getJson<QueueData>(`${room(id)}/queue`),
  history: (id: number, categoryId?: number) =>
    getJson<HistoryData>(`${room(id)}/history`, { category_id: categoryId, limit: 100 }),
  balance: (id: number) => getJson<BalanceData>(`${room(id)}/balance`),
  shopping: (id: number) => getJson<ShoppingData>(`${room(id)}/shopping`),
  stats: (id: number, year?: number, month?: number) =>
    getJson<StatsData>(`${room(id)}/stats`, { year, month }),

  // Turns: "I'll buy it" / "We still have some" / "Can't today" answer an issued turn.
  turn: (id: number, assignmentId: number, action: "accept" | "still" | "decline") =>
    postJson<ActionResult>(`${room(id)}/turns/${assignmentId}/${action}`),
  done: (id: number, categoryId: number, inTurn: boolean, amount?: string) =>
    postJson<ActionResult>(`${room(id)}/categories/${categoryId}/done`, {
      in_turn: inTurn,
      amount: amount?.trim() || null,
    }),
  vote: (id: number, dutyId: number, vote: "up" | "down") =>
    postJson<ActionResult>(`${room(id)}/duties/${dutyId}/vote`, { vote }),

  addExpense: (id: number, expense: { amount: string; description: string; member_ids: number[] }) =>
    postJson<ActionResult>(`${room(id)}/expenses`, expense),
  settle: (id: number, transfer: Transfer) =>
    postJson<ActionResult>(`${room(id)}/settle`, {
      debtor_id: transfer.debtor_id,
      creditor_id: transfer.creditor_id,
      cents: transfer.cents,
    }),

  addItems: (id: number, text: string) => postJson<ActionResult>(`${room(id)}/shopping`, { text }),
  bought: (id: number, itemId: number) => postJson<ActionResult>(`${room(id)}/shopping/${itemId}/bought`),
  goingShopping: (id: number) => postJson<ActionResult>(`${room(id)}/shopping/going`),

  away: (id: number, period: { days: number } | { until: string }) =>
    postJson<ActionResult>(`${room(id)}/away`, period),
  back: (id: number) => postJson<ActionResult>(`${room(id)}/back`),

  // The room itself: settings and categories (admins), roommates, export, joining.
  settings: (id: number) => getJson<SettingsData>(`${room(id)}/settings`),
  updateSettings: (id: number, patch: RoomSettingsPatch) =>
    sendJson<ActionResult>("PATCH", `${room(id)}/settings`, patch),
  addCategory: (id: number, category: { name: string; emoji: string }) =>
    postJson<ActionResult>(`${room(id)}/categories`, category),
  updateCategory: (id: number, categoryId: number, patch: CategoryPatch) =>
    sendJson<ActionResult>("PATCH", `${room(id)}/categories/${categoryId}`, patch),
  deleteCategory: (id: number, categoryId: number) =>
    sendJson<ActionResult>("DELETE", `${room(id)}/categories/${categoryId}`),
  removeMember: (id: number, memberId: number) =>
    postJson<ActionResult>(`${room(id)}/members/${memberId}/remove`),
  leave: (id: number) => postJson<ActionResult>(`${room(id)}/leave`),
  join: (id: number) => postJson<ActionResult>(`${room(id)}/join`),
  exportCsv: (id: number) => postJson<ActionResult>(`${room(id)}/export`),
  /** The room the bot's private chat works with (like /room). */
  chooseRoom: (id: number) => postJson<ActionResult>("/api/me/room", { room_id: id }),
};
